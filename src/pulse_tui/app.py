"""Audio-reactive 3D wireframe with adjustable mesh density in a Braille terminal."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import time

from .settings import CAMERAS, PALETTES, Options
from .looks import LOOKS

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
    parser.add_argument("--look", choices=tuple(LOOKS), default="cinematic", help="Visual preset; classic preserves the previous look")
    parser.add_argument("--camera", choices=CAMERAS, help="Override the look's camera")
    parser.add_argument("--palette", choices=PALETTES, help="Override adaptive colors or the look's palette")
    parser.add_argument("--color-response", type=float, default=1.35, help="Color expressiveness, 0.5–2 (default 1.35)")
    parser.add_argument("--cycle-seconds", type=float, default=14.0, help="Seconds per palette in cycle mode, 2–120 (default 14)")
    parser.add_argument("--fps", type=int, default=24, help="Frame-rate target (default 24)")
    parser.add_argument("--gain", type=float, help="Response strength, 0.2–3 (preset default)")
    parser.add_argument("--mesh-density", "--density", dest="density", type=float, help="Mesh density per axis, 0.5–4 (preset default; higher is finer)")
    parser.add_argument("--no-history", action="store_true", help="Disable the trailing terrain history")
    parser.add_argument("--no-highlights", action="store_true", help="Disable bright crest accents")
    parser.add_argument("--no-sections", action="store_true", help="Disable section release waves and camera opening")
    parser.add_argument("--mono", action="store_true", help="Request mono capture; disable stereo placement (also for mono input devices)")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/cava/config", help="Read audio input settings from this CAVA config")
    parser.add_argument("--input-method", help="Override CAVA capture method")
    parser.add_argument("--source", help="Override CAVA audio source")
    parser.add_argument("--duration", type=float, default=0, help="Exit after this many wall-clock seconds")
    args = parser.parse_args(argv)
    options = Options.for_look(args.look)
    for name in ("camera", "palette", "gain", "density"):
        if getattr(args, name) is not None:
            setattr(options, name, getattr(args, name))
    options.history = not args.no_history
    options.highlights = not args.no_highlights
    options.sections = not args.no_sections
    options.stereo = not args.mono
    if not 1 <= args.fps <= 60 or not .2 <= options.gain <= 3 or not .5 <= options.density <= 4 or not .5 <= args.color_response <= 2 or not 2 <= args.cycle_seconds <= 120:
        parser.error("Use fps 1–60, gain 0.2–3, mesh density 0.5–4, color response 0.5–2, and cycle seconds 2–120")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Run this in an interactive terminal.")
    renderer, scene = Renderer(use_native=not args.python_renderer), Scene(color_response=args.color_response, cycle_seconds=args.cycle_seconds)
    audio = None
    try:
        audio = CavaInput(args.config, args.input_method, args.source, stereo=not args.mono)
        started = last = time.monotonic()
        now, frames, measured_fps, last_sequence = 0.0, 0, 0.0, -1
        fps_started = started
        with Terminal() as terminal:
            while True:
                tick = time.monotonic()
                dt, last = tick - last, tick
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
