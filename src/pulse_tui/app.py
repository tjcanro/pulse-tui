#!/usr/bin/env python3
"""Audio-reactive 3D wireframe with adjustable mesh density in a Braille terminal."""
from __future__ import annotations

import argparse
import configparser
import ctypes
import dataclasses
import math
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty

try:
    import numpy as np
except ImportError:
    raise SystemExit("NumPy is required: python3 -m pip install numpy")

BARS = 64
BG = "\x1b[48;2;8;5;16m"
RESET = "\x1b[0m"
CAMERAS = ("flight", "orbit", "overhead", "fixed")


class RawFrames:
    """8-bit mono CAVA frames; reads may split or combine arbitrary frames."""
    def __init__(self, bars=BARS):
        self.bars = bars
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        count = len(self.pending) // self.bars
        if not count:
            return None
        start = (count - 1) * self.bars
        latest = np.frombuffer(bytes(self.pending[start:start + self.bars]), dtype=np.uint8)
        del self.pending[:count * self.bars]
        return latest.astype(float) / 255.0


class CavaInput:
    """Run CAVA with an isolated temporary raw-output config, never edit the user's."""
    def __init__(self, config, method=None, source=None):
        executable = shutil.which("cava")
        if not executable:
            raise RuntimeError("CAVA was not found. Install CAVA to capture audio.")
        self.config = configparser.ConfigParser(strict=False)
        self.config.read(config)
        for section in ("general", "input", "output", "smoothing"):
            if not self.config.has_section(section):
                self.config.add_section(section)
        for key, value in {"bars": str(BARS), "framerate": "60", "autosens": "1",
                           "lower_cutoff_freq": "40", "higher_cutoff_freq": "16000",
                           "live-config": "0"}.items():
            self.config.set("general", key, value)
        if not self.config.has_option("input", "method"):
            self.config.set("input", "method", "coreaudio" if sys.platform == "darwin" else "pulse")
        if not self.config.has_option("input", "source"):
            self.config.set("input", "source", "tap" if sys.platform == "darwin" else "auto")
        if method:
            self.config.set("input", "method", method)
        if source:
            self.config.set("input", "source", source)
        # Replace the complete visual-output section so existing orientations cannot interfere.
        self.config.remove_section("output")
        self.config.add_section("output")
        for key, value in {"method": "raw", "raw_target": "/dev/stdout", "data_format": "binary",
                           "bit_format": "8bit", "channels": "mono", "mono_option": "average"}.items():
            self.config.set("output", key, value)
        for key, value in {"monstercat": "0", "waves": "0", "noise_reduction": "35"}.items():
            self.config.set("smoothing", key, value)
        self.directory = tempfile.TemporaryDirectory(prefix="pulse-tui-")
        self.path = Path(self.directory.name) / "cava.conf"
        with self.path.open("w") as f:
            self.config.write(f)
        self.log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen([executable, "-p", str(self.path)], stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=self.log)
        except BaseException:
            self.log.close()
            self.directory.cleanup()
            raise
        self.latest = np.zeros(BARS)
        self.lock = threading.Lock()
        self.sequence = 0
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        self.started = time.monotonic()

    def _read(self):
        decoder = RawFrames()
        try:
            while True:
                data = os.read(self.process.stdout.fileno(), 4096)
                if not data:
                    break
                frame = decoder.feed(data)
                if frame is not None:
                    with self.lock:
                        self.latest = frame
                        self.sequence += 1
        except (OSError, ValueError):
            pass

    def poll(self):
        if self.process.poll() is not None:
            self.log.seek(0)
            message = self.log.read().decode(errors="replace").strip()
            raise RuntimeError("CAVA stopped: " + (message[-1600:] or f"exit {self.process.returncode}"))
        with self.lock:
            return self.latest.copy(), self.sequence

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.thread.join(timeout=2)
        self.process.stdout.close()
        self.log.close()
        self.directory.cleanup()


@dataclasses.dataclass
class Pulse:
    when: float
    x: float
    z: float
    band: int
    strength: float


class Scene:
    def __init__(self):
        self.pulses = []
        self.levels = np.zeros(3)
        self.average = np.full(3, .06)
        self.previous = np.zeros(3)
        self.last_hit = np.full(3, -10.0)
        self.counter = 0
        self.spectrum = np.zeros(BARS)

    def add(self, now, band, strength=1.0):
        angle = self.counter * 2.399963
        radius = (1.4, 4.0, 5.7)[band]
        self.pulses.append(Pulse(now, math.cos(angle) * radius, math.sin(angle) * radius,
                                 band, min(1.6, max(.15, strength))))
        self.pulses = self.pulses[-12:]
        self.counter += 1

    def update(self, spectrum, now, dt):
        self.spectrum = spectrum
        # Log-spaced CAVA bins: approximately 40–200, 200–2500 and 2500–16000 Hz.
        levels = np.array([np.sqrt(np.mean(spectrum[a:b] ** 2))
                           for a, b in ((0, 17), (17, 44), (44, BARS))])
        smoothing = 1 - math.exp(-max(dt, 0) * 18)
        self.levels += (levels - self.levels) * smoothing
        adaptation = 1 - math.exp(-max(dt, 0) * 1.8)
        self.average += (levels - self.average) * adaptation
        flux = np.maximum(levels - self.previous, 0)
        for band in range(3):
            threshold = max(.018, self.average[band] * .16)
            if levels[band] > .035 and flux[band] > threshold and now - self.last_hit[band] > (.18, .13, .09)[band]:
                self.add(now, band, .4 + levels[band] * 1.8 + flux[band] * 1.5)
                self.last_hit[band] = now
        self.previous = levels.copy()
        self.pulses = [p for p in self.pulses if now - p.when < 3.5]

    def surface(self, x, z, now, gain):
        h = .10 * np.sin(x * .52 + z * .32) + .07 * np.sin(x * .91 - z * .64)
        energy = np.zeros_like(x)
        high_energy = np.zeros_like(x)
        for p in self.pulses:
            age = max(0, now - p.when)
            dx, dz = x - p.x, z - p.z
            r = np.sqrt(dx * dx + dz * dz)
            speed, frequency = ((5.5, 2.0), (4.0, 3.5), (6.0, 7.5))[p.band]
            envelope = math.exp(-age * (1.65 if p.band == 2 else .9))
            ring = np.exp(-((r - age * speed) * .8) ** 2)
            crest = ring * envelope * p.strength * (.32 if p.band == 2 else .8) * gain
            mound = np.exp(-r * r * (.27 if p.band == 1 else .13)) * math.exp(-age * 1.8) * p.strength * gain
            h += np.sin(r * frequency - age * speed * frequency) * crest + mound
            energy += crest + mound * .4
            if p.band == 2:
                high_energy += crest
        # Sustained frequencies shape the center even when no distinct attack is detected.
        r = np.sqrt(x * x + z * z)
        angle = np.arctan2(z, x)
        band_index = (angle + np.pi) * (BARS - 1) / (2 * np.pi)
        amplitudes = np.interp(band_index, np.arange(BARS), self.spectrum)
        h += amplitudes * np.exp(-r * r * .065) * gain * 1.4
        return x, h, z, np.clip(energy * .6 + h * .16, 0, 1), high_energy


@dataclasses.dataclass
class Options:
    camera: str = "flight"
    gain: float = 1.3
    density: float = 2.0
    paused: bool = False
    hud: bool = True
    yaw: float = 0.0
    elevation: float = 0.0


class NativeRasterizer:
    """Optional compiled hot loops; all audio, camera and mesh controls stay in Python."""
    def __init__(self):
        self.library = ctypes.CDLL(str(Path(__file__).parent / "_native" / "wireframe_native.so"))
        self.library.pulse_renderer_abi.restype = ctypes.c_int
        if self.library.pulse_renderer_abi() != 1:
            raise RuntimeError("Unsupported native renderer ABI")
        vector = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags="C_CONTIGUOUS")
        indices = np.ctypeslib.ndpointer(dtype=np.int64, ndim=2, flags="C_CONTIGUOUS")
        self.render = self.library.pulse_rasterize
        self.render.argtypes = [vector, vector, vector, vector, indices, ctypes.c_size_t,
                                indices, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, vector, vector]
        self.render.restype = None


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

    @staticmethod
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

    @staticmethod
    def camera(now, options):
        if options.camera == "flight":
            angle, radius, y = -.85 + now * .12, 13.2 + 2.5 * math.sin(now * .22), 5.1 + 2.3 * math.sin(now * .27 - .8)
            target = np.array([math.sin(now * .15) * 1.3, .65, math.cos(now * .17) * 1.3])
        else:
            angle = -.65 + now * .065 if options.camera == "orbit" else -.55
            radius, y = (10, 15) if options.camera == "overhead" else (13.5, 4.2)
            target = np.array([0, .55, 0])
        angle += options.yaw
        eye = np.array([math.sin(angle) * radius, max(1.5, y + options.elevation), math.cos(angle) * radius])
        forward = target - eye
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, [0, 1, 0])
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        return eye, right, up, forward

    @staticmethod
    def project(x, y, z, camera, width, height, aspect):
        eye, right, up, forward = camera
        dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
        depth = dx * forward[0] + dy * forward[1] + dz * forward[2]
        safe = np.maximum(depth, .1)
        cx = dx * right[0] + dy * right[1] + dz * right[2]
        cy = dx * up[0] + dy * up[1] + dz * up[2]
        px = (cx * 1.85 / aspect / safe * .5 + .5) * width
        py = (.5 - cy * 1.85 / safe * .5) * height
        return px, py, depth

    def dots(self, scene, now, options, cols, rows):
        width, height = cols * 2, rows * 4
        aspect = cols / max(1, rows * 2)  # Typical terminal cell is twice as tall as wide.
        cam = self.camera(now, options)
        heatmap = np.full(width * height, -1.0)
        self.mesh(options.density)
        x, y, z, heat, _ = scene.surface(self.mesh_x, self.mesh_z, now, options.gain)
        px, py, depth = self.project(x, y, z, cam, width, height, aspect)
        if self.native:
            depthmap = np.empty(width * height)
            self.native.render(np.ascontiguousarray(px), np.ascontiguousarray(py),
                               np.ascontiguousarray(depth), np.ascontiguousarray(heat),
                               self.faces, len(self.faces), self.edges, len(self.edges),
                               width, height, depthmap, heatmap)
            return heatmap.reshape(height, width)
        depthmap = self.depth_mask(px, py, depth, self.faces, width, height)
        a, b = self.edges.T
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

    @staticmethod
    def cells(dots):
        rows, cols = dots.shape[0] // 4, dots.shape[1] // 2
        codes = np.zeros((rows, cols), dtype=np.uint16)
        heat = np.zeros((rows, cols))
        bits = ((1, 8), (2, 16), (4, 32), (64, 128))
        for y in range(4):
            for x in range(2):
                sample = dots[y::4, x::2]
                codes |= (sample >= 0).astype(np.uint16) * bits[y][x]
                heat = np.maximum(heat, sample)
        # A small stable palette keeps output bandwidth modest and colors consistent.
        levels = np.clip((heat * 11).astype(int), 0, 11)
        palette = [(int(130 * (1 - k / 11)), int(45 + 200 * k / 11), 245) for k in range(12)]
        return codes, levels, palette

    def frame(self, scene, now, options, cols, rows, source, fps):
        if cols < 28 or rows < 12:
            return ["Resize terminal to at least 28 x 12"[:max(1, cols)]] + [" " * cols] * max(0, rows - 1)
        top = 2 if options.hud else 0
        bottom = 2 if options.hud else 0
        dots = self.dots(scene, now, options, cols, rows - top - bottom)
        codes, levels, palette = self.cells(dots)
        lines = []
        if options.hud:
            state = "PAUSED" if options.paused else source
            lines.append("\x1b[38;2;0;220;255m" + f" PULSE  /  WIREFRAME  |  {state}  |  {options.camera}  |  {fps:.0f} fps  |  {'native' if self.native else 'python'}"[:cols].ljust(cols))
            meters = []
            for label, v in zip(("BASS", "MIDS", "HIGH"), scene.levels):
                n = min(8, int(v * 10))
                meters.append(label + " " + "█" * n + "·" * (8 - n))
            lines.append("\x1b[38;2;145;125;180m" + (" " + "   ".join(meters))[:cols].ljust(cols))
        # Construct Unicode rows in C, then emit runs of the same color. Avoid
        # a Python loop, integer conversion and string append for every cell.
        codepoints = np.where(codes == 0, 32, codes + 0x2800).astype(np.uint32)
        encoding = "utf-32-le" if sys.byteorder == "little" else "utf-32-be"
        text = codepoints.tobytes().decode(encoding)
        last_ink = np.maximum.accumulate(np.where(codes != 0, np.arange(cols), 0), axis=1)
        colors = np.take_along_axis(levels, last_ink, axis=1)
        escapes = [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in palette]
        for i, rowcolors in enumerate(colors):
            row = text[i * cols:(i + 1) * cols]
            if not codes[i].any():
                lines.append(row)
                continue
            boundaries = [0, *(np.flatnonzero(rowcolors[1:] != rowcolors[:-1]) + 1), cols]
            lines.append("".join(escapes[rowcolors[start]] + row[start:end]
                                 for start, end in zip(boundaries, boundaries[1:])))
        if options.hud:
            lines.append("\x1b[38;2;170;155;200m" + " [ coarser  ] finer  c camera  SPACE pause  +/- energy"[:cols].ljust(cols))
            lines.append("\x1b[38;2;170;155;200m" + (f" arrows view  b/m/t pulse  h HUD  q quit   Energy {options.gain:.1f}x  Mesh {options.density:.2g}x ({self.mesh_n}x{self.mesh_n})")[:cols].ljust(cols))
        return lines


class Terminal:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.original = termios.tcgetattr(self.fd)
        self.pending_keys = ""
        self.previous_lines = []
        tty.setcbreak(self.fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l" + BG + "\x1b[2J")
        sys.stdout.flush()
        return self

    def __exit__(self, *_):
        try:
            sys.stdout.write(RESET + "\x1b[?7h\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original)

    def keys(self):
        if select.select([self.fd], [], [], 0)[0]:
            self.pending_keys += os.read(self.fd, 1024).decode(errors="ignore")
        keys, self.pending_keys = self.pending_keys, ""
        # Keep partial arrow sequences until the remaining bytes arrive.
        for suffix in ("\x1b[", "\x1b"):
            if keys.endswith(suffix):
                keys, self.pending_keys = keys[:-len(suffix)], suffix
                break
        return keys

    def draw(self, lines):
        # Skip unchanged rows, including the quiet horizon and paused frames.
        previous = self.previous_lines if len(self.previous_lines) == len(lines) else []
        updates = [f"\x1b[{i + 1};1H{line}\x1b[K" for i, line in enumerate(lines)
                   if i >= len(previous) or line != previous[i]]
        if updates:
            sys.stdout.write(BG + "".join(updates))
            sys.stdout.flush()
        self.previous_lines = lines


def handle_keys(keys, options, scene, now):
    for sequence, yaw, height in (("\x1b[D", -.14, 0), ("\x1b[C", .14, 0),
                                  ("\x1b[A", 0, .6), ("\x1b[B", 0, -.6)):
        while sequence in keys:
            options.yaw += yaw
            options.elevation = min(10, max(-2, options.elevation + height))
            keys = keys.replace(sequence, "", 1)
    for key in keys:
        if key in "qQ\x03":
            return False
        if key == "c":
            options.camera = CAMERAS[(CAMERAS.index(options.camera) + 1) % len(CAMERAS)]
        elif key == " ":
            options.paused = not options.paused
        elif key in "+=":
            options.gain = min(3, round(options.gain + .1, 1))
        elif key == "-":
            options.gain = max(.2, round(options.gain - .1, 1))
        elif key == "]":
            options.density = min(4.0, round(options.density + .25, 2))
        elif key == "[":
            options.density = max(.5, round(options.density - .25, 2))
        elif key == "h":
            options.hud = not options.hud
        elif key in "bmt":
            scene.add(now, "bmt".index(key))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-renderer", action="store_true", help="Force the portable Python renderer for comparison")
    parser.add_argument("--camera", choices=CAMERAS, default="flight")
    parser.add_argument("--fps", type=int, default=24, help="Frame-rate target (default 24)")
    parser.add_argument("--gain", type=float, default=1.3)
    parser.add_argument("--mesh-density", "--density", dest="density", type=float, default=2.0, help="Mesh density per axis, 0.5–4 (default 2; higher is finer)")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/cava/config", help="Read audio input settings from this CAVA config")
    parser.add_argument("--input-method", help="Override CAVA capture method")
    parser.add_argument("--source", help="Override CAVA audio source")
    parser.add_argument("--duration", type=float, default=0, help="Exit after this many wall-clock seconds")
    args = parser.parse_args(argv)
    if not 1 <= args.fps <= 60 or not .2 <= args.gain <= 3 or not .5 <= args.density <= 4:
        parser.error("Use fps 1–60, gain 0.2–3, and mesh density 0.5–4")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Run this in an interactive terminal.")
    options = Options(camera=args.camera, gain=args.gain, density=args.density)
    renderer, scene = Renderer(use_native=not args.python_renderer), Scene()
    audio = None
    try:
        audio = CavaInput(args.config, args.input_method, args.source)
        started = last = time.monotonic()
        now, frames, measured_fps, last_sequence = 0.0, 0, 0.0, -1
        fps_started = started
        with Terminal() as terminal:
            while True:
                tick = time.monotonic()
                dt, last = min(.1, tick - last), tick
                if args.duration and tick - started >= args.duration:
                    break
                if not handle_keys(terminal.keys(), options, scene, now):
                    break
                spectrum, sequence = audio.poll()
                source = "LIVE / CAVA" if sequence else "WAITING FOR CAVA"
                if not sequence and tick - started > 8:
                    raise RuntimeError("No audio frames from CAVA after 8 seconds. Check system-audio capture permissions and the configured input source.")
                if not options.paused:
                    now += dt
                    if sequence != last_sequence:
                        scene.update(spectrum, now, dt)
                        last_sequence = sequence
                size = shutil.get_terminal_size((120, 40))
                cols, rows = max(1, size.columns), max(1, size.lines)
                lines = renderer.frame(scene, now, options, cols, rows, source, measured_fps)
                terminal.draw(lines)
                frames += 1
                if tick - fps_started >= .5:
                    measured_fps = frames / (tick - fps_started)
                    frames, fps_started = 0, tick
                time.sleep(max(0, 1 / args.fps - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError) as e:
        print(f"Pulse: {e}", file=sys.stderr)
        return 1
    finally:
        if audio:
            audio.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
