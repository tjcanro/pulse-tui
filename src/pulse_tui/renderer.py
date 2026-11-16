"""Build the mesh, select a rasterizer, and encode colored Braille frames."""
from __future__ import annotations

import sys

import numpy as np

from .camera import camera, project
from .native import NativeRasterizer
from .rasterizer import rasterize
from .looks import LOOKS


class Renderer:
    def __init__(self, use_native=True):
        self.native = None
        if use_native:
            try:
                self.native = NativeRasterizer()
            except (OSError, AttributeError, RuntimeError):
                pass
        self.mesh_n = 0
        self.mesh_x = self.mesh_z = None
        self.edges = self.faces = None

    def mesh(self, density):
        """Cache horizontal vertices, triangle triples, and wire-edge pairs."""
        # Density scales edge count per axis. 1x matches the original 39x39 grid.
        n = round(38 * density) + 1
        if n == self.mesh_n:
            return
        self.mesh_n = n
        v = np.linspace(-18, 18, n)
        xx, zz = np.meshgrid(v, v)
        self.mesh_x, self.mesh_z = xx.ravel(), zz.ravel()
        a = np.arange(n * n).reshape(n, n)
        self.edges = np.concatenate((np.column_stack((a[:, :-1].ravel(), a[:, 1:].ravel())),
                                     np.column_stack((a[:-1].ravel(), a[1:].ravel())),
                                     np.column_stack((a[:-1, 1:].ravel(), a[1:, :-1].ravel()))))
        aa, bb, cc, dd = a[:-1, :-1].ravel(), a[:-1, 1:].ravel(), a[1:, :-1].ravel(), a[1:, 1:].ravel()
        self.faces = np.concatenate((np.column_stack((aa, cc, bb)), np.column_stack((bb, cc, dd))))

    def dots(self, scene, now, options, cols, rows):
        """Project the animated mesh and rasterize it at Braille-dot resolution."""
        width, height = cols * 2, rows * 4
        aspect = cols / max(1, rows * 2)  # Typical terminal cell is twice as tall as wide.
        cam = camera(now, options, scene.director)
        self.mesh(options.density)
        x, y, z, heat, _ = scene.surface(self.mesh_x, self.mesh_z, now, options.gain, options)
        style = LOOKS[options.look]
        if style.crests and options.highlights:
            grid = y.reshape(self.mesh_n, self.mesh_n)
            padded = np.pad(grid, 1, mode="edge")
            curvature = np.maximum(0, 4 * grid - padded[1:-1, :-2] - padded[1:-1, 2:]
                                   - padded[:-2, 1:-1] - padded[2:, 1:-1])
            # Normalize for mesh spacing so changing density keeps crest brightness.
            curvature /= (36 / (self.mesh_n - 1)) ** 2
            crest = np.clip(curvature.ravel() * .22, 0, 1) * np.clip((y - .15) / .8, 0, 1)
            heat = np.minimum(1.45, heat + crest * .65 * style.crests)
        px, py, depth = project(x, y, z, cam, width, height, aspect)
        if self.native:
            heatmap = np.full(width * height, -1.0)
            depthmap = np.empty(width * height)
            self.native.render(np.ascontiguousarray(px), np.ascontiguousarray(py),
                               np.ascontiguousarray(depth), np.ascontiguousarray(heat),
                               self.faces, len(self.faces), self.edges, len(self.edges),
                               width, height, depthmap, heatmap)
            return heatmap.reshape(height, width)
        return rasterize(px, py, depth, heat, self.faces, self.edges, width, height)

    @staticmethod
    def cells(dots):
        """Pack each 2-by-4 dot block into one glyph and a palette heat index."""
        rows, cols = dots.shape[0] // 4, dots.shape[1] // 2
        codes = np.zeros((rows, cols), dtype=np.uint16)
        heat = np.zeros((rows, cols))
        bits = ((1, 8), (2, 16), (4, 32), (64, 128))
        for y in range(4):
            for x in range(2):
                sample = dots[y::4, x::2]
                codes |= (sample >= 0).astype(np.uint16) * bits[y][x]
                heat = np.maximum(heat, sample)
        # Twelve base indices plus four tinted-white crest accents.
        levels = np.clip((heat * 11).astype(int), 0, 15)
        return codes, levels

    def frame(self, scene, now, options, cols, rows, source, fps):
        if cols < 28 or rows < 12:
            return ["Resize terminal to at least 28 x 12"[:max(1, cols)]] + [" " * cols] * max(0, rows - 1)
        top = 2 if options.hud else 0
        bottom = 2 if options.hud else 0
        dots = self.dots(scene, now, options, cols, rows - top - bottom)
        codes, levels = self.cells(dots)
        palette = self.palette(scene, options, now)
        escapes = [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in palette]
        color_label = f"auto:{scene.colors.name}" if options.palette == "auto" else options.palette
        if options.palette == 'auto' and scene.colors.character.family != scene.colors.name:
            color_label += '>' + scene.colors.character.family
        lines = []
        if options.hud:
            state = "PAUSED" if options.paused else source
            lines.append(escapes[10] + f" PULSE WIREFRAME | {options.look} | {state} | {color_label} | {scene.director.section} | {fps:.0f}fps | {'native' if self.native else 'python'}"[:cols].ljust(cols))
            meters = []
            for label, v in zip(("BASS", "MIDS", "HIGH"), scene.levels):
                n = min(8, int(v * 10))
                meters.append(label + " " + "█" * n + "·" * (8 - n))
            bass_label = f"   Style: {scene.colors.character.label}"
            lines.append(escapes[4] + (" " + "   ".join(meters) + bass_label)[:cols].ljust(cols))
        # Construct Unicode rows in C, then emit runs of the same color. Avoid
        # a Python loop, integer conversion and string append for every cell.
        codepoints = np.where(codes == 0, 32, codes + 0x2800).astype(np.uint32)
        encoding = "utf-32-le" if sys.byteorder == "little" else "utf-32-be"
        text = codepoints.tobytes().decode(encoding)
        last_ink = np.maximum.accumulate(np.where(codes != 0, np.arange(cols), 0), axis=1)
        colors = np.take_along_axis(levels, last_ink, axis=1)
        for i, rowcolors in enumerate(colors):
            row = text[i * cols:(i + 1) * cols]
            if not codes[i].any():
                lines.append(row)
                continue
            boundaries = [0, *(np.flatnonzero(rowcolors[1:] != rowcolors[:-1]) + 1), cols]
            lines.append("".join(escapes[rowcolors[start]] + row[start:end]
                                 for start, end in zip(boundaries, boundaries[1:])))
        if options.hud:
            lines.append(escapes[3] + " v look  p colors  c camera  [/] mesh  SPACE pause  +/- energy"[:cols].ljust(cols))
            lines.append(escapes[3] + (f" arrows view  b/m/t pulse  h HUD  q quit   Energy {options.gain:.1f}x  Mesh {options.density:.2g}x ({self.mesh_n}x{self.mesh_n})")[:cols].ljust(cols))
        return lines

    @staticmethod
    def palette(scene, options, now=None):
        base = scene.colors.palette(options.palette, now=now)
        style = LOOKS[options.look]
        # Darker quiet wires give the bright crests room to stand out. Classic
        # keeps the previous palette exactly. Only sixteen colors reach the TTY.
        if style.crests:
            floor = .38 + .32 * scene.colors.intensity
            base = tuple(tuple(round(v * (floor + (1 - floor) * (i / 11) ** .7)) for v in rgb)
                         for i, rgb in enumerate(base))
        tip = base[-1]
        highlights = tuple(tuple(round(v + (255 - v) * mix) for v in tip)
                           for mix in (.18, .32, .48, .62))
        return tuple(base) + highlights
