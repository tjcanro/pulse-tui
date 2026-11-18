# Spatial scenes

Press **s** to cycle Terrain → Endless Ribbons → Orbital Fragments → Filament
Current. **Shift+s** cycles backward. Scene choice is independent of a look (`v`),
palette (`p`), or camera (`c`). Switching scenes retains those settings, the live
spectrum, palette analysis, audio history, manual view offsets, gain, and pause.
Terrain remains the default.

```sh
party --scene ribbons
party --scene orbit --palette warm
party --scene filaments --palette neon
party --scene terrain
```

[Actual terminal recordings](media/scenes/index.html) ·
[Comparison still](media/scenes/comparison.png)

The clips use the same generated stereo spectrum score at 24 fps. The refined
Ribbons and Filaments previews use 192 × 64 terminal cells; the preserved Orbit
preview uses 160 × 48. They show the implemented renderer; the earlier AI-generated
planning images are visual references rather than measurements of terminal
resolution. No generated music or demo mode is added to the live application.

## Endless Ribbons

Five bands loop back through depth and extend beyond the viewport. Broad sheets
and fine strands have distinct widths, and travelling taper profiles narrow and
widen each band along its length. Ribbon cross-sections follow transported local
frames, with bank, proportional camber, fine interior wires, bright companion
rails, and small edge marks.
Dimmer stray filaments surround the bands. The open wire geometry is transparent
so overlapping layers remain visible, with stronger foreground/background
contrast. A broad band and a narrow band wind around a shared curved spine,
alternating in front of and behind each other at successive crossings. Larger
travelling bends add wave-like curvature across the other loops as well.

The mesh is moving material: cross-ribs, paired rails, and edge marks slide
continuously along each loop. Travelling twists and wider bends reshape the
bands between beats. Each path has its own steady flow speed; the direction
comes from the path rather than camera motion. Open ends fade before recycling,
so wrapped edges cannot draw a chord across the view.

Bass adds a small width change, sustained spectrum/history adds local shape,
and attacks send accents along the strips. Broad swelling is deliberately
subdued so continuous movement dominates. Stereo balance shifts depth. The
gain control changes local detail and accent strength.

## Orbital Fragments

Permanent broken arcs concentrate in the middle, with no latitude/longitude
sphere underneath. Additional arc fragments continually emerge near the center,
expand toward the margins, and fade before recycling. Bass launches brighter
fronts outward through the structure. The camera retains the central composition.

The geometry uses deterministic seeds and scene time. Fragment resets are hidden
while their heat is below the visible threshold, preventing an arc from visibly
teleporting inward. Different planes and rotation directions give layered motion;
farther wires dim with depth. Arc strips have occasional cross-ribs but no solid
surface mask, retaining a transparent filigree appearance.

## Filament Current

Most strands form a sweeping S-shaped stream, with two smaller crossing
currents at other depths. A dense core, a narrowing bend, fanning ends, and
sparse outliers give uneven density and a sense of large scale. Finite strands
actually stream along those paths, with different speeds and lengths, bright
leading sections, fading tails, and rolling eddies. Their heads, tails, and
open-path recycling all fade smoothly. Flow continues with constant audio and
a fixed camera. Sustained frequency detail adds turbulence, bass modestly
changes spread, and attacks add travelling accents. Strand counts and
longitudinal samples scale with the square root of detail, keeping the maximum
geometry bounded.

## Controls and rendering

- `[` / `]`: decrease/increase real geometry detail in 0.25x steps, 0.5–4x.
- `c` and arrows: camera mode, yaw, and elevation. `--camera fixed` holds the view.
- `+` / `-`: audio response strength.
- `b` / `m` / `t`: manual bass/mid/high accents; Orbit uses strong bass fronts and finer mid/high fronts.
- Space: freeze scene time; geometry, palette and camera controls remain usable.
- `v`: existing look presets, including their camera/color/detail defaults.
- `p`: Auto, Cycle, and all nine fixed palettes.
- `--no-history`: current spectrum only, without retained spectral detail.
- `--no-highlights`: suppress the brightest accent indices.

Terrain-specific crest curvature and buildup/release surface waves remain part
of Terrain. The spatial scenes use their own accents and camera framing, sharing
the existing stereo audio, color analysis and history. The native rasterizer ABI
and C source are unchanged. No GPU, shader, metadata integration or new runtime
dependency is needed.

Only the current spatial model/topology is cached, alongside the existing terrain
mesh. Increasing detail adds samples and wires; decreasing it reduces actual
work. Geometry sizes stay bounded. The HUD reports scene name and vertex count,
while the existing FPS counter includes terminal writes. Actual display speed
also depends on terminal size/font and the terminal's redraw cost.

## Implementation and checks

`geometry.py` contains common mesh data, history sampling, and travelling accents.
`curves.py` samples natural cubic paths with continuous curvature and transports
stable local frames. Cached normals are sampled at each material point's moving
position and aligned to its current deformation. Shared end fades hide recycling.
Ribbons use the smallest rotation between rest and deformed tangents to keep
their cross-sections stable through sharp bends.
Movement depends on scene time, so pause is exact and rendering never integrates
or mutates animation state.
`ribbons.py`, `orbit.py`, and `filaments.py` evaluate their own geometry.
`spatial.py` caches one provider; `renderer.py` projects its arrays and sends them
through the existing native or NumPy rasterizer and Braille/ANSI encoder.

Run `make test`. `tests/test_scenes.py` checks finite geometry, actual detail
scaling, audio/manual response, exact paused frames, all camera modes, scene-cache
switching, motion continuity, center/outward composition, invisible fragment
recycling, forward material flow without beats, hidden material recycling,
turning spatial paths, width contrast, alternating depth at braid crossings,
stable ribbon frames through right-angle bends, CLI options, and
native/portable parity. The PTY integration test
starts Ribbons, cycles through all four scenes, changes looks, resizes, and
verifies quit/terminal restoration. Existing audio and palette regressions remain
in the suite.

Regenerate the previews using optional development tools Pillow and ffmpeg:

```sh
python3 scripts/render_scenes.py
python3 scripts/render_scenes.py --palette neon --output /tmp/pulse-neon-scenes
python3 scripts/render_scenes.py --scenes ribbons filaments --columns 192 --rows 64
python3 scripts/render_scenes.py --scenes ribbons filaments --camera fixed --output /tmp/pulse-fixed-flow
```
