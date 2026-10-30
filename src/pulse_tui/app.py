"""Audio-reactive 3D wireframe with adjustable mesh density in a Braille terminal."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import time

from .settings import CAMERAS, Options

try:
    from .audio import CavaInput
    from .renderer import Renderer
    from .scene import Scene
except ModuleNotFoundError as error:
    if error.name != "numpy":
        raise
    raise SystemExit("NumPy is required: python3 -m pip install numpy") from error

from .terminal import Terminal, handle_keys


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
