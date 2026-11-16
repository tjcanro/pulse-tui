# Audio-only musical profiles and expressive colors

Run `party` for Auto. Analysis stays entirely local: CAVA supplies frequency-band
amplitudes; Python uses NumPy to measure musical patterns. There is no player
integration, metadata, artist list, model download, account, or network lookup.
Runtime dependencies remain Python, NumPy, and CAVA.

[Four-style TUI comparison](media/styles/index.html) ·
[Nine automatic profiles](media/styles/profiles.png) ·
[Nine quiet/lively palettes](media/character/atlas.png)

## How Auto chooses

Bass remains the anchor. `character.py` measures attack width, tonal width,
subtracted-bed periodicity, attack spacing, envelope contrast, and downward pitch
motion in the first twelve CAVA bins (roughly 40–120 Hz). A fixed pitched bass and
a descending synthesized kick can therefore look different even at the same
120 BPM. A sustained per-bin bed is removed before assessing dynamic width and
pulse evidence, so compressed mixes can still reach Neon.

`rhythm.py` now adds upper-band **percussion context**. It does not treat extra
vocal energy, overall brightness, or loudness as evidence of a new genre:

1. Look for simultaneous positive changes across at least 40% of the upper
   twenty bands. Narrow harmonics and steady bright sounds do not qualify.
2. Keep a bounded ten-second event/spectrum history. Require at least eight
   attacks and six seconds of evidence, with bass present.
3. Require the upper-band envelope itself to recur (autocorrelation at least
   0.55). A regular bass cannot turn random upper-band speech into a beat.
4. Estimate repeating periods from the upper envelope, refining their lags
   between samples. Require onset-time matches in both halves of the window and
   enough evidence for two bar-sized groups of repetitions. Subtract the chance
   coincidence rate implied by the event density, so busy random bursts do not
   appear repetitive simply because they occupy many timestamps.
5. Require both onset recurrence and a combined quality threshold before letting
   this context supplement the bass scores.

These windows are rhythmic evidence, **not detected musical meter/downbeats**.
The shortest strong repeat can be a beat subdivision or a multiple of the beat.
Refining its period avoids locking the detector to a few exact tempos. Onset
matches use a small time tolerance for CAVA/render-frame jitter, and the exit
threshold is lower than the entry threshold to avoid dropping a profile on one
weak assessment.

`style.py` combines the evidence into these profiles:

| Bass and qualified percussion | Favored family | HUD style |
| --- | --- | --- |
| Rounded/pitched bass without stronger offbeat, kick, or swing evidence | Ember (`warm`) | rounded / mellow |
| Sustained sub-bass, dense hats relative to bass attacks | Crimson | hip-hop-like |
| Repeated offbeat bass phrases locked to percussion subdivisions | Aurora | latin-like |
| Regular broad/descending kicks | Neon | electronic-like |
| Pitched bass and regular percussion | Blue | pop-like |
| Moving bass notes with alternating short/long percussion | Gold | swing/funk-like |
| Sustained sub-bass and sparser percussion | Violet | soul-like |
| Regular bass with bright, dense percussion subdivisions | Sunset | bright dance-pop |
| Very still, diffuse low-end bed | Ice | ambient-like |

The profile rules are ordered: sub-heavy/dense and syncopated patterns are tested
before the regular-kick, soul, swing, bright-pop, and general-pop cases. Attack
subdivisions relative to bass attacks help a slower hip-hop groove reach Crimson;
there is no single BPM cutoff deciding every style. Sunset uses the timbre of
qualified percussion attacks, **not the highs-to-vocals energy ratio**. Ice's
stillness rule uses bass, so a new melodic voice does not displace it. With no
qualified percussion, the original bass-only rounded/driving/flowing/sustained/
rough scores remain a fallback.

Aurora uses a stricter relationship check: **irregularity is not automatically
syncopation**. A skipped bass note or occasional pickup can make a country or
acoustic accompaniment irregular too. The analyzer fits an upper-percussion
subdivision grid, checks that bass attacks share its timing, and requires
substantial attacks on both alternating grid phases in both halves of the recent
window. The bass phrase must also repeat, using up to sixteen seconds of bounded
onset history and correcting for coincidental matches in busy patterns. At least
six recent bass attacks are needed. This is a relative timing heuristic; no
actual musical downbeat is assumed, and the bass/percussion latency offset is
free. If those checks fail, the strong rounded-bass fallback can stay Warm even
with busy drums.

Gold's timing check also requires short and long percussion intervals to
alternate consistently. Interval variance alone is insufficient: missed hi-hat
detections and fills can inflate it without any swing. This prevents a rejected
Aurora guess from simply sending the same acoustic mix to Gold instead.

One shared selector requires a score of at least 0.62, a lead of 0.10, candidate
evidence lasting 1.5 seconds, and six seconds between changes. Percussion-based
choices need their longer evidence window first. Visible family weights then
crossfade with a 2.5-second time constant. A new passage typically needs about
8–15 seconds; weak or conflicting evidence holds the current family. The HUD
shows `Style: ...`, `settling crimson`, or `holding`; `auto:warm>crimson` means the
visible color blend is still catching up with the chosen target.

These are **hand-tuned musical-pattern heuristics, not a trained genre model**.
Genre boundaries overlap, and CAVA supplies coarse amplitudes rather than isolated
instruments or raw waveform phase. A country track with pop production may fit
Blue; a melodic rap passage may fit Violet. Broad, repeated vocal fricatives can
still resemble percussion. The safeguards reduce vocal-triggered changes; they
are not source separation or a guarantee for every singer. No artist identity or
real-song genre-accuracy percentage is claimed.

## Liveliness inside the palette

The whole spectrum drives a faster-attack/slower-release intensity envelope from
RMS energy, positive spectral change, brightness, and energy relative to a slow
baseline. Relative energy helps despite CAVA autosensitivity. This path is
independent of the slower family decision.

Each of the nine families has quiet and lively OKLCH gradients. Expression changes
lightness, chroma, and related hues: Ember can grow from brick/terracotta into
copper/orange/gold; Neon can bloom from violet/blue into magenta/cyan. Quiet valley
wires dim; lively ones become more present. Gradients and family weights blend in
Oklab. RGB steps are limited to eighteen levels per update, at most eight times
per second. Silence holds the last displayed colors; pause freezes analysis.

```sh
party                             # Auto with the default cinematic look
party --color-response 1.8         # Stronger in-family expression (range 0.5–2)
party --palette warm              # Lock a family; keep live expression
party --look neon --palette auto  # Neon geometry with automatic color selection
```

## Nine palettes and fourteen looks

| Palette | Look | Quiet → lively colors |
| --- | --- | --- |
| `warm` | `ember` | Red/terracotta → copper/orange/gold |
| `blue` | `deep-space` | Indigo/navy → azure/icy cyan |
| `neon` | `neon` | Violet/blue → magenta/violet/cyan |
| `aurora` | `aurora` | Emerald/teal → mint/cyan |
| `crimson` | `crimson` | Burgundy/cherry → scarlet/apricot |
| `gold` | `gold` | Bronze/amber → gold/lemon |
| `violet` | `velvet` | Plum/mauve → orchid/rose |
| `sunset` | `sunset` | Rose/coral → pink/orange/amber |
| `ice` | `glacier` | Steel blue → glacial cyan/white |

All nine can be reached by Auto. `p` cycles **Auto → Cycle → fixed families**;
`v` cycles complete looks. A look with a fixed palette or an explicit `--palette`
overrides Auto. Use default Cinematic or `--palette auto` for musical selection.

```sh
party --palette cycle
party --palette cycle --cycle-seconds 8
```

Cycle is independent of classification. It eases through warm → gold → aurora →
ice → blue → neon → violet → sunset → crimson → warm, keeping live expression.
The default is fourteen seconds per family (126 seconds per loop), adjustable
from 2–120 seconds. It uses scene time, continues without fresh audio, and freezes
with Space/pause.

## Implementation and evidence

- `character.py`: bass features and the shared stable decision mechanism.
- `rhythm.py`: qualified upper-band percussion and repetition checks. It also
  measures bass/subdivision timing, offbeat balance, repeated bass
  phrases, and short/long percussion alternation for the more selective profiles.
- `style.py`: musical profiles supplementing the bass-only fallback.
- `palettes.py`: nine quiet/lively gradients and gamut-safe sRGB conversion.
- `colors.py`: expression, family blending, and bounded RGB updates.
- `tests/test_styles.py`: nine reachable families, all-family vocal entrances,
  several tempos/frame rates/volumes, random speech-like bursts, brief fills,
  track changes, and actual CAVA output for four procedural instrument mixtures.
  Acoustic mixtures with omitted notes, pickups, and humanized timing must remain
  Warm despite busy percussion, including after an Aurora passage.
- `tests/test_character.py`: bass distinctions, weak/phase-shifted kicks, voice
  invariance, compressed mixes, and earlier real-CAVA bass regressions.

The new comparison uses the actual terminal renderer with **generated spectra**;
it is not captured music. `tests/data/style_reference.npz` separately records
procedural PCM passed through the actual CAVA executable. Both are controlled
regression tools, not a labeled song corpus or proof of genre accuracy. See the
[fixture recipes](../tests/data/README.md).

Run `make test`. `scripts/render_styles.py` regenerates the current comparison;
`scripts/capture_style_reference.py` regenerates the new CAVA fixture without
playing audio. Pillow/ffmpeg are optional development tools for previews only.
`scripts/capture_acoustic_reference.py` regenerates the acoustic negatives, also
through silent FIFOs. Sampling and missed attacks can hide real swing; without
clear alternation evidence a shuffle may fit another profile.
Earlier [bass comparison](media/character/index.html) and
[cinematic experiments](media/showcase/index.html) remain available as historical
renderings. The CAVA capture path, terminal geometry, and native rasterizer ABI
are unchanged.
