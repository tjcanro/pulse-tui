# Architecture

Pulse is a separate terminal application that consumes CAVA's documented raw output. It is not a CAVA fork.

```text
System audio → CAVA child process → 64 frequency bands
                                       ↓
                            Onset detection + terrain
                                       ↓
                             Camera and projection
                                       ↓
                        C rasterizer / Python fallback
                                       ↓
                          Braille cells + ANSI colors
                                       ↓
                                    Terminal
```

## Source layout

- `src/pulse_tui/app.py`: audio reader, scene, projection, renderer, terminal lifecycle, and CLI. These remain together from the validated prototype; split into modules when the interfaces stabilize.
- `src/pulse_tui/__main__.py`: supports `python -m pulse_tui`.
- `native/wireframe.c`: triangle depth rasterization and visible line sampling through a plain C ABI.
- `scripts/build_native.py`: builds a platform-local shared library in `src/pulse_tui/_native/`. Generated binaries are ignored by Git.
- `tests/test_app.py`: deterministic renderer checks, native/Python parity, actual CAVA with synthetic PCM, and pseudoterminal interaction tests.

## Audio and configuration

CAVA is launched with a temporary configuration copied from the user's input settings. Output is replaced with 8-bit, 64-band mono binary frames. The reader tolerates fragmented and combined pipe reads. The main loop consumes the newest available spectrum.

Bass/mid/treble attacks launch spatial ripples. Sustained frequency amplitudes also shape the terrain. The onset heuristic is not instrument separation or precise beat tracking. The application always consumes live CAVA output; failed audio capture is reported directly.

Existing CAVA and terminal settings are not modified. Normal exit and Ctrl-C restore terminal state and clean up the child process and temporary files.

## Rendering

Mesh density scales vertices per axis. Default 2x gives 77x77 vertices. Projected triangles form a depth mask, and edge samples are tested against that same mesh. Dot positions are packed into Unicode Braille cells, with one of twelve foreground colors per cell. Unicode encoding is batched, and unchanged rows are not resent.

The C and Python paths share the same projection, mesh, depth tolerance, and color mapping. Native rendering is optional; the title reports which path is active.
