# Pulse TUI

Audio-reactive 3D wireframe terrain, rendered entirely in your terminal. Powered by [CAVA](https://github.com/karlstav/cava), with moving cameras, adjustable mesh density, and purple-to-cyan Braille graphics.

![Pulse TUI: an animated wireframe terrain responding to bass, midrange, and treble](docs/media/pulse.gif)

*Actual terminal-renderer output, driven by generated PCM audio through CAVA. The GIF runs at 12 fps; the application targets 24 fps by default.*

## Quick start

Requires Python 3.10+, NumPy, and CAVA. On macOS, use a true-color terminal such as iTerm2:

```sh
brew install cava
git clone https://github.com/tjcanro/pulse-tui.git
cd pulse-tui
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./Pulse.command
```

Pulse uses live audio from CAVA. You can also double-click `Pulse.command` in Finder to start it. macOS may request system-audio capture permission for CAVA.

## Mesh coarseness

Press **`]` for a finer mesh** with smaller gaps, or **`[` for a coarser mesh**. The footer shows the current density and grid dimensions. Density changes work while paused, so you can compare the same frame.

The default is **2x**, a **77x77** vertex grid. The original prototype used a **39x39** grid (now `1x`). Density scales the number of edges along each axis: twice the density roughly halves the spacing and quadruples the number of triangles. The supported range is `0.5x` (20x20) to `4x` (153x153), in steps of `0.25x`.

```sh
./Pulse.command --mesh-density 3
./Pulse.command --mesh-density 4 --camera overhead
```

`--density` is an alias for `--mesh-density`. A higher density produces finer geometry; it costs more rendering time. The surface depth mask is rasterized from the same mesh as the visible edges to reduce false holes from the earlier sampled depth mask.

The dots themselves are Braille glyphs: increasing mesh density shrinks the spaces between wireframe edges, while individual-dot spacing still depends on terminal font and font size. A smaller terminal font gives more display detail.

## Ultrawide performance

The launcher automatically uses a small compiled C rasterizer for depth masking and wire drawing. Mesh geometry and density are unchanged. The header shows **native** when it is active. Unicode text encoding is batched, and unchanged terminal rows are not resent.

The native binary is built locally into `src/pulse_tui/_native/` and is excluded from version control. When needed, the launcher tries to rebuild it with an existing C compiler; it does not install a compiler. The portable Python path remains available if the library cannot load.

```sh
python3 scripts/build_native.py
./Pulse.command --python-renderer
```

In local checks at the default 2x mesh density, average renderer time fell from approximately **103 ms to 8 ms at 360x90**, and **159 ms to 12 ms at 480x110**. These are computation/encoding timings, not measured iTerm2 display frame rates. Actual smoothness also depends on terminal redraw performance, font size, and output throughput. The existing FPS counter includes terminal writes.

If a very large window remains slow, use `[` to reduce mesh density slightly, or increase the font size to reduce the number of terminal cells.

## Controls

| Key | Action |
| --- | --- |
| `]` / `[` | Finer / coarser mesh |
| `c` | Cycle cinematic flight, low orbit, overhead, fixed |
| Arrow keys | Adjust viewing angle and height |
| Space | Pause motion; mesh and camera controls remain available |
| `+` / `-` | Adjust response strength |
| `b` / `m` / `t` | Manually trigger a bass / mid / treble pulse |
| `h` | Hide/show controls |
| `q` or Ctrl-C | Quit and restore the terminal |

## Audio integration

Live mode starts CAVA as a child process using raw, 8-bit, 64-band mono output. It copies the input settings from `~/.config/cava/config` into a temporary configuration. Your CAVA config and iTerm2 settings are not modified. The child process and temporary config are cleaned up on normal exit or Ctrl-C.

Bass, mids, and highs drive different ripple widths and speeds. Sudden increases trigger pulses; sustained frequency amplitudes also shape the surface. This is an onset heuristic, not precise BPM tracking or instrument separation. Live capture errors are reported directly.

```sh
./Pulse.command --input-method coreaudio --source tap
./Pulse.command --config /path/to/cava/config
./Pulse.command --gain 1.1 --fps 24
./Pulse.command --duration 30
./Pulse.command --help
```

Resize the terminal at any time. The default frame-rate target is 24 fps; the measured rate appears in the header. Large terminals and fine meshes cost more rendering time.

## Portability and validation

Requires Python 3.10+, NumPy, CAVA, and a Unix-like true-color terminal with Braille font support. An existing C compiler enables native acceleration on other machines. The `.command` launcher is for macOS. Elsewhere:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/build_native.py
PYTHONPATH=src python3 -m pulse_tui
python3 tests/test_app.py
```

Set `PULSE_PYTHON=/path/to/python3` to override the Mac launcher's interpreter.

Tests cover native/Python renderer parity, suppression of unchanged terminal rows, mesh density and screen coverage, triangle depth rasterization, CAVA raw framing, actual CAVA with generated PCM/FIFO input, terminal controls, resizing, and cleanup. The audio test uses generated input, not your microphone or system playback. Final appearance and system-audio permission still need evaluation in your iTerm2 session.

This is an independent front end consuming CAVA's existing raw interface. Sources: [CAVA](https://github.com/karlstav/cava), [raw output configuration](https://github.com/karlstav/cava/blob/1.0.0/example_files/config).

## Project layout

```text
src/pulse_tui/          Audio, scene, camera, renderer, terminal, and CLI modules
native/wireframe.c     Native rasterizer source
scripts/               Native build helper
tests/                 Renderer, audio-stream, and terminal integration checks
docs/                  Architecture, performance, roadmap, and preview media
Pulse.command          macOS launcher
Makefile               Build, run, and test commands
pyproject.toml         Python package metadata
```

Development commands: `make build`, `make run`, and `make test`. To install into an existing development environment, use `python3 -m pip install -e .`; the `pulse-tui` command is then available. Build native acceleration with `make build` before running. CAVA is an external runtime dependency.

For a step-by-step explanation of the Python/C boundary and how sound becomes Braille text, read [how Pulse works](docs/architecture.md).

More detail: [architecture](docs/architecture.md), [performance](docs/performance.md), and [roadmap](docs/roadmap.md).

## Shell shortcut

To use `party` as a shortcut, add an alias to your shell configuration (`~/.bashrc` for Bash or `~/.zshrc` for Zsh), replacing the path with your checkout:

```sh
alias party='"$HOME/Workspace/pulse-tui/Pulse.command"'
```

Reload your shell configuration, then run `party`. Arguments pass through, for example `party --mesh-density 3`.
