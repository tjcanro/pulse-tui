# Performance

Local measurements from the prototype on this Apple Silicon Mac, with the same simulated spectrum and default 2x mesh density:

| Terminal cells | Original Python frame | Native + batched encoding |
| --- | ---: | ---: |
| 120x40 | 38.9 ms | 4.0 ms |
| 240x65 | 61.1 ms | 5.2 ms |
| 360x90 | 102.9 ms | 7.6 ms |
| 480x110 | 159.2 ms | 11.7 ms |

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
| 120x40 | 3.59 ms | 6.48 ms |
| 240x65 | 5.44 ms | 8.29 ms |
| 360x90 | 7.84 ms | 9.57 ms |
| 480x110 | 11.56 ms | 10.93 ms |

[Raw measurements](benchmarks/cinematic.json). Recording ran concurrently, so
small differences are noisy; camera visibility also changes the amount of
rasterization work. These checks exclude terminal transport and display work.
They are not guaranteed iTerm2 frame rates.

History stays bounded at 192 stereo rows; interpolation/curvature operate on
the mesh vertices, not a second full-screen pass. The existing native rasterizer
and ABI are unchanged. Sixteen palette colors retain bounded ANSI color runs.
For less motion use Deep Space, Ember, a fixed camera, or the Classic fallback.
