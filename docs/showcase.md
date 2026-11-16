# Stages, experiments, and the selected default

**Cinematic is the selected default.** It combines all six additions while keeping
camera motion slower than the surface: terrain history, crest highlights,
stereo placement, musical camera choreography, buildup/release transitions,
and complete visual presets. Surge preserves the stronger-motion experiment.

- [Open the playable gallery](media/showcase/index.html).
- [View the comparison sheet](media/showcase/comparison.png).
- [Watch the selected look at 24 fps](media/showcase/cinematic.mp4).
- [View the lighter inline GIF](media/showcase/cinematic.gif).

All eight clips use **the same twelve-second segment of a generated stereo
spectrum score**, including a buildup and release. They are silent renderings of
the real terminal renderer, not recordings of a song. The videos are 24 fps;
the GIF is 12 fps. The gallery and media are ordinary HTML/PNG/MP4/GIF files and
require no shader support. Open the HTML locally to play the gallery; GitHub's
source view does not execute HTML.

| Stage / look | What changes | Run it |
| --- | --- | --- |
| Classic | Previous geometry/camera; current audio-driven colors | `party --look classic --mono` |
| Crests | Adds bright ridge accents and quieter valleys | `party --look crests` |
| Memory | Adds smoothly traveling history, displayed as a mono landscape | `party --look memory` |
| **Cinematic** | Complete restrained mix, bass-guided family, 2x mesh | `party` |
| Ember | Red/amber, broad slower ripples, gentle camera, 1.75x mesh | `party --look ember` |
| Neon | Magenta/violet/cyan, sharper faster ripples, closer camera, 2x mesh | `party --look neon` |
| Deep Space | Blue, spacious slow motion, longer history, 1.5x mesh | `party --look deep-space` |
| Surge | Stronger release waves, narrower ripples, more camera motion | `party --look surge` |

## Why Cinematic was selected

The earlier flight camera can rotate to the far side of the scene and sometimes
lets the foreground dominate. The new camera remains on the front side, so
stereo placement is visually consistent and the traveling history stays in view.
It moves lower/closer as sustained musical intensity rises, and gently opens
after a release. There are no hard camera cuts or kick-driven shakes.

Surge explores stronger movement, but its closer camera makes the foreground
more dominant. Ember and Deep Space are quieter alternatives. Any look can be
used as the permanent choice by passing its name from your shell alias.

## Controls and independent overrides

`v` now cycles fourteen looks (the eight recorded here plus six new themes); from the default, the next look is Classic. Applying
a look resets camera, palette, density, and gain to its defaults, while feature-
disable flags and pause remain in effect. `p` cycles colors; `c` cycles cameras.
Arrows adjust angle/height, and `[`/`]` change mesh density.

```sh
party --look cinematic --camera fixed        # All geometry, stationary camera
party --look cinematic --no-history          # Remove terrain memory
party --look cinematic --no-highlights       # Remove crest accents
party --look cinematic --no-sections         # Remove release waves/opening
party --look cinematic --mono                # Centered mono capture/placement
party --look ember --mesh-density 2.5         # Preset with finer mesh
party --look deep-space --palette auto       # Spacious motion, adaptive family
```

## Color correction included

These recordings precede the [expanded audio-only character engine](character.md).
They preserve the earlier visual experiments; the current runtime has stronger
color expression and nine palette choices.


Only approximately **40–120 Hz** chooses the automatic family. Mids, vocals, and
highs affect intensity/lightness/chroma instead. A vocal-range entrance with the
same bass cannot change the hue blend. Fixed presets also respond in intensity
without changing family. Bass/vocal overlap below 120 Hz can still occur; this
is a heuristic, not source separation.

## Under the hood

- `history.py`: up to 192 stereo rows at 12 Hz, bilinearly interpolated into the
  terrain. Age fades and interpolation prevent row stepping.
- `director.py`: slow intensity/tension/pan cues and bounded release events.
  Section labels are approximate visual cues, not verse/chorus detection.
- `looks.py`: immutable configurations for every stage and alternative.
- `audio.py`: raw stereo decoder with mirrored-left-bin correction. `--mono`
  requests the previous protocol and supports mono input devices.
- `renderer.py`: mesh-spacing-normalized crest highlights, sixteen colors, and
  the existing native/NumPy paths. The C ABI is unchanged.
- `colors.py`: family blending and full-spectrum intensity, with
  smoother eight-Hz palette updates.

Classic was compared against the previous renderer at three camera/mesh
combinations and produced exactly the same dot positions and heat values with
mono fixture input. Its hues intentionally include the vocal fix.

## Reproduce the renderings

Rendering is a development tool, separate from the live app. It does not restore
`--demo` or add a synthetic audio source to the app.

```sh
python3 -m pip install Pillow     # Optional: only for the recording helper
python3 scripts/render_showcase.py
python3 scripts/render_showcase.py --stills-only
python3 scripts/render_showcase.py --looks cinematic classic surge
```

Video rendering also needs `ffmpeg`. The helper uses installed Apple Symbols or
DejaVu Sans Mono fonts. Output goes to `docs/media/showcase/`; each clip uses the
same score from `preview_score.py`.

`make test` covers real CAVA stereo order, mono compatibility, history advection
and bounds, camera continuity, conservative section events, crest visibility,
all presets, pause, native/NumPy parity, and the bass/vocal color regression,
alongside the existing terminal integration checks.
