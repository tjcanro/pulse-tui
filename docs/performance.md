# Performance

Local measurements from the prototype on this Apple Silicon Mac, with the same simulated spectrum and default 2x mesh density:

| Terminal cells | Original Python frame | Native + batched encoding |
| --- | ---: | ---: |
| 120x40 | 4.79 ms | 6.23 ms | 2.12 ms | 15.50 ms |
| 240x65 | 61.1 ms | 5.2 ms |
| 360x90 | 8.46 ms | 8.45 ms | 4.19 ms | 16.60 ms |
| 480x110 | 10.91 ms | 11.83 ms | 5.75 ms | 25.83 ms |

Raw results: [ultrawide.json](benchmarks/ultrawide.json).

These timings include scene rendering and text encoding, but exclude terminal output transport and iTerm2 display work. They are not guaranteed display frame rates. A separate 360x90 pseudoterminal run reported approximately 22–24 fps at the default 24 fps target.

The largest speedup came from moving triangle depth rasterization and line sampling into C. Mesh detail was retained. Unicode row construction was batched, and unchanged terminal rows are skipped.

Use the HUD to check `native` versus `python`. Press `[` to reduce mesh density if terminal output remains slow. Font size also matters: a small font on an ultrawide display can create a very large terminal grid.

## Reproduce basic checks

```sh
make build
make test
./Pulse.command
./Pulse.command --python-renderer
```

Compare at the same terminal dimensions, camera, mesh density, and FPS target. The tests verify native/Python geometry parity as well as live CAVA framing with generated PCM.

## Cinematic additions

Local native renderer + text-encoding checks at the same 2x mesh, using the
generated stereo score (milliseconds per frame):

| Terminal cells | Classic | Cinematic |
| --- | ---: | ---: |
| 120x40 | 4.79 ms | 6.23 ms | 2.12 ms | 15.50 ms |
| 240x65 | 5.44 ms | 8.29 ms |
| 360x90 | 8.46 ms | 8.45 ms | 4.19 ms | 16.60 ms |
| 480x110 | 10.91 ms | 11.83 ms | 5.75 ms | 25.83 ms |

[Raw measurements](benchmarks/cinematic.json). Recording ran concurrently, so
small differences are noisy; camera visibility also changes the amount of
rasterization work. These checks exclude terminal transport and display work.
They are not guaranteed iTerm2 frame rates.

History stays bounded at 192 stereo rows; interpolation/curvature operate on
the mesh vertices, not a second full-screen pass. The existing native rasterizer
and ABI are unchanged. Sixteen palette colors retain bounded ANSI color runs.
For less motion use Deep Space, Ember, a fixed camera, or the Classic fallback.

## Spatial scenes

Same-machine native checks at the default 2x detail, 72 frames per case. These
measure geometry evaluation, rasterization, and ANSI encoding; they exclude
audio analysis, terminal transport, and iTerm2 redraw work.

| Terminal cells | Terrain | Ribbons | Orbit | Filaments |
| --- | ---: | ---: | ---: | ---: |
| 120x40 | 4.79 ms | 6.23 ms | 2.12 ms | 15.50 ms |
| 360x90 | 8.46 ms | 8.45 ms | 4.19 ms | 16.60 ms |
| 480x110 | 10.91 ms | 11.83 ms | 5.75 ms | 25.83 ms |

[Raw scene measurements](benchmarks/scenes.json). These are computation timings,
not guaranteed terminal display rates. All three new scenes reuse the existing C
rasterizer ABI. Ribbons, Orbit and Filaments use transparent line geometry; Terrain retains
triangle depth masks. Refined Ribbons and Filaments include more path detail
than the first implementation, with spatial turns and foreground/background
structure rather than parallel horizontal waves. Only one spatial model/topology is cached at a time.
Density changes sample/wire counts, not just a cosmetic spacing value.
Continuous material flow resamples the cached paths and local frames at moving
positions. It reuses the same bounded vertex and edge counts.

A separate 360x90 drained-pseudoterminal run, using real CAVA with silent FIFO
input, reported roughly 20–23 fps for the flowing Ribbons and Filaments at the
24 fps target and restored the terminal on exit.
[Refinement PTY results](benchmarks/scene-refinement-pty.json) ·
[Original scene PTY results](benchmarks/scenes-pty.json).
This includes output transport through the PTY, not iTerm2's actual display work.
