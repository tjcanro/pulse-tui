/* Terminal rasterizer: same triangles, depth tolerance and dot grid as Python.
 * Plain C ABI for ctypes; no Python or NumPy headers are required. */
#include <math.h>
#include <stddef.h>
#include <stdint.h>

int pulse_renderer_abi(void) { return 1; }

static double minimum3(double a, double b, double c) { return fmin(a, fmin(b, c)); }
static double maximum3(double a, double b, double c) { return fmax(a, fmax(b, c)); }

static int clip(double p, double q, double *first, double *last) {
    if (fabs(p) < 1e-12) return q >= 0;
    double r = q / p;
    if (p < 0) {
        if (r > *last) return 0;
        if (r > *first) *first = r;
    } else {
        if (r < *first) return 0;
        if (r < *last) *last = r;
    }
    return 1;
}

void pulse_rasterize(const double *px, const double *py, const double *depth,
                     const double *heat, const int64_t *faces, size_t face_count,
                     const int64_t *edges, size_t edge_count, int width, int height,
                     double *zbuffer, double *dots) {
    size_t count = (size_t)width * (size_t)height;
    for (size_t i = 0; i < count; ++i) { zbuffer[i] = INFINITY; dots[i] = -1; }

    for (size_t face = 0; face < face_count; ++face) {
        int64_t a = faces[3 * face], b = faces[3 * face + 1], c = faces[3 * face + 2];
        if (depth[a] <= .7 || depth[b] <= .7 || depth[c] <= .7) continue;
        double x0 = px[a], x1 = px[b], x2 = px[c];
        double y0 = py[a], y1 = py[b], y2 = py[c];
        int minx = (int)fmax(0, floor(minimum3(x0, x1, x2)));
        int maxx = (int)fmin(width - 1, ceil(maximum3(x0, x1, x2)));
        int miny = (int)fmax(0, floor(minimum3(y0, y1, y2)));
        int maxy = (int)fmin(height - 1, ceil(maximum3(y0, y1, y2)));
        if (minx > maxx || miny > maxy) continue;
        double denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2);
        if (fabs(denominator) <= 1e-8) continue;
        double ux = (y1 - y2) / denominator, uy = (x2 - x1) / denominator;
        double vx = (y2 - y0) / denominator, vy = (x0 - x2) / denominator;
        double za = 1 / depth[a], zb = 1 / depth[b], zc = 1 / depth[c];
        for (int y = miny; y <= maxy; ++y) {
            double u = ux * (minx - x2) + uy * (y - y2);
            double v = vx * (minx - x2) + vy * (y - y2);
            size_t row = (size_t)y * width;
            for (int x = minx; x <= maxx; ++x, u += ux, v += vx) {
                if (u < -1e-5 || v < -1e-5 || u + v > 1.00001) continue;
                double z = 1 / (u * za + v * zb + (1 - u - v) * zc);
                if (z < zbuffer[row + x]) zbuffer[row + x] = z;
            }
        }
    }

    int max_steps = (width > height ? width : height) * 2;
    for (size_t edge = 0; edge < edge_count; ++edge) {
        int64_t a = edges[2 * edge], b = edges[2 * edge + 1];
        if (depth[a] <= .7 || depth[b] <= .7) continue;
        double dx = px[b] - px[a], dy = py[b] - py[a];
        double first = 0, last = 1;
        /* Clip iteration bounds, retaining the original DDA sample positions. */
        if (!clip(-dx, px[a] + .5, &first, &last) ||
            !clip(dx, width - .5 - px[a], &first, &last) ||
            !clip(-dy, py[a] + .5, &first, &last) ||
            !clip(dy, height - .5 - py[a], &first, &last)) continue;
        int steps = (int)ceil(fmax(fabs(dx), fabs(dy)));
        if (steps < 1) steps = 1;
        if (steps > max_steps) steps = max_steps;
        int begin = (int)fmax(0, floor(first * steps));
        int end = (int)fmin(steps, ceil(last * steps));
        double inverse_a = 1 / depth[a], inverse_b = 1 / depth[b];
        for (int j = begin; j <= end; ++j) {
            double t = (double)j / steps;
            int x = (int)nearbyint(px[a] + dx * t), y = (int)nearbyint(py[a] + dy * t);
            if (x < 0 || y < 0 || x >= width || y >= height) continue;
            size_t key = (size_t)y * width + x;
            double z = 1 / ((1 - t) * inverse_a + t * inverse_b);
            if (z > zbuffer[key] + .25) continue;
            double value = heat[a] * (1 - t) + heat[b] * t;
            if (value > dots[key]) dots[key] = value;
        }
    }
}
