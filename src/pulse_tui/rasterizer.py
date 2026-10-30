"""Portable triangle depth masking and visible wireframe line sampling."""
from __future__ import annotations

import numpy as np

def depth_mask(px, py, depth, faces, width, height):
    """Rasterize the actual mesh, rather than a different sampled surface.

    Bounded batches cap intermediate allocations. Perspective-correct depth
    lets front-facing wire edges survive their own surface's depth test.
    """
    result = np.full(width * height, np.inf)
    valid = np.all(depth[faces] > .7, axis=1)
    faces = faces[valid]
    for offset in range(0, len(faces), 2048):
        face = faces[offset:offset + 2048]
        x, y, d = px[face], py[face], depth[face]
        minx = np.maximum(0, np.floor(x.min(axis=1))).astype(int)
        maxx = np.minimum(width - 1, np.ceil(x.max(axis=1))).astype(int)
        miny = np.maximum(0, np.floor(y.min(axis=1))).astype(int)
        maxy = np.minimum(height - 1, np.ceil(y.max(axis=1))).astype(int)
        denominator = (y[:, 1] - y[:, 2]) * (x[:, 0] - x[:, 2]) + (x[:, 2] - x[:, 1]) * (y[:, 0] - y[:, 2])
        boxwidth, boxheight = maxx - minx + 1, maxy - miny + 1
        keep = (boxwidth > 0) & (boxheight > 0) & (np.abs(denominator) > 1e-8)
        if not keep.any():
            continue
        x, y, d, denominator = x[keep], y[keep], d[keep], denominator[keep]
        minx, miny, boxwidth, boxheight = minx[keep], miny[keep], boxwidth[keep], boxheight[keep]
        sizes = boxwidth * boxheight
        which = np.repeat(np.arange(len(sizes)), sizes)
        local = np.arange(sizes.sum()) - np.repeat(np.cumsum(sizes) - sizes, sizes)
        sx = minx[which] + local % boxwidth[which]
        sy = miny[which] + local // boxwidth[which]
        u = ((y[which, 1] - y[which, 2]) * (sx - x[which, 2]) +
             (x[which, 2] - x[which, 1]) * (sy - y[which, 2])) / denominator[which]
        v = ((y[which, 2] - y[which, 0]) * (sx - x[which, 2]) +
             (x[which, 0] - x[which, 2]) * (sy - y[which, 2])) / denominator[which]
        inside = (u >= -1e-5) & (v >= -1e-5) & (u + v <= 1.00001)
        ii = which[inside]
        zz = 1 / (u[inside] / d[ii, 0] + v[inside] / d[ii, 1] + (1 - u[inside] - v[inside]) / d[ii, 2])
        np.minimum.at(result, sy[inside] * width + sx[inside], zz)
    return result



def rasterize(px, py, depth, heat, faces, edges, width, height):
    """Return visible line samples, using NumPy instead of the C library."""
    heatmap = np.full(width * height, -1.0)
    depthmap = depth_mask(px, py, depth, faces, width, height)
    a, b = edges.T
    # Skip edges behind the near plane before interpolating screen positions.
    valid = (depth[a] > .7) & (depth[b] > .7)
    a, b = a[valid], b[valid]
    lengths = np.ceil(np.maximum(np.abs(px[b] - px[a]), np.abs(py[b] - py[a]))).astype(int)
    lengths = np.clip(lengths, 1, max(width, height) * 2)
    repetitions = lengths + 1
    starts = np.repeat(np.cumsum(repetitions) - repetitions, repetitions)
    fractions = (np.arange(repetitions.sum()) - starts) / np.repeat(lengths, repetitions)
    aa, bb = np.repeat(a, repetitions), np.repeat(b, repetitions)
    xx = np.rint(px[aa] + (px[bb] - px[aa]) * fractions).astype(int)
    yy = np.rint(py[aa] + (py[bb] - py[aa]) * fractions).astype(int)
    dd = 1 / ((1 - fractions) / depth[aa] + fractions / depth[bb])
    valid = (xx >= 0) & (xx < width) & (yy >= 0) & (yy < height)
    keys = yy[valid] * width + xx[valid]
    visible = dd[valid] <= depthmap[keys] + .25
    values = heat[aa] * (1 - fractions) + heat[bb] * fractions
    np.maximum.at(heatmap, keys[visible], values[valid][visible])
    return heatmap.reshape(height, width)
