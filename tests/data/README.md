# Generated bass regression fixtures

`bass_reference.npz` contains CAVA output for two procedurally generated signals,
not music recordings and not a genre training/evaluation dataset. Both repeat at
120 BPM. It was captured through the installed CAVA 1.0.0 executable using 44.1kHz,
16-bit stereo PCM via FIFO, 64 bands/channel, 40–16000Hz, autosensitivity enabled,
and noise reduction 35. Left/right were identical, then averaged after decoding.

The two signals use time `t` and beat phase `p = t % 0.5`:

```text
rounded = sin(2π·80·t) · (0.18 + 0.45·exp(-6p))
driving = sin(2π·(44p + (100/35)·(1-exp(-35p)))) · exp(-12p)·0.95
          + 0.04·sin(2π·60·t)
```

After clipping to [-1, 1], samples were scaled by 24000 and encoded as int16.
The resulting fourteen seconds of CAVA frames were sampled at 24Hz and stored
as uint8 amplitudes plus float32 timestamps. The NPZ contains no Python objects.

This tests a physically useful distinction: a fixed pitched bass versus a
descending percussive kick. The latter may look narrow at the attack in CAVA's
coarse bins; its downward pitch motion supplies additional evidence. Passing
these tests does not establish artist or real-world genre recognition accuracy.

`mixed_bass_reference.npz` is another actual CAVA capture, with the same settings
and sampling, for a quiet descending kick over sustained bass and mids:

```text
mix = 0.22 * [the descending kick above, without the 60Hz additive tone]
      + 0.28 * sin(2π·80·t) + 0.12 * sin(2π·220·t)
```

It has a clear 120-BPM pulse but less than 20% bass-envelope contrast after CAVA.
The old analyzer incorrectly held warm on this capture. The regression checks
that sustained bass and CAVA smoothing do not hide a periodic kick.

## Full-band musical-profile reference

`style_reference.npz` contains four additional **procedural PCM mixtures passed
through the real CAVA 1.0.0 binary**, with the same 44.1 kHz/stereo/raw settings.
Each capture lasts 28 seconds and is polled at 24 Hz. Arrays are named
`hip-hop_frames`, `hip-hop_times`, `latin_frames`, etc.; amplitudes are uint8,
times float32, and no pickled objects are present.

Reproduce without playing any sound:

```sh
python3 scripts/capture_style_reference.py
```

The script writes to private FIFOs read by CAVA; it does not open an audio output
or the system audio input. Its four bass parts are:

- Hip-hop-like: a 52 Hz sine with a sustained bed and syncopated attacks at
  0, 0.75, 1.5, 2.75, and 3.25 seconds in each four-second phrase.
- Latin-like: pitched notes at 82, 102, 75, 104, and 92 Hz, anticipated at
  0, 0.75, 1.5, 2.5, and 3.75 seconds in a four-second phrase.
- Electronic-like: the descending 120 BPM kick from `bass_reference.npz`, with a
  quiet 60 Hz additive tone.
- Pop-like: an 86 Hz pitched bass pulsing every half-second.

All include quiet 260/510 Hz accompaniment and high-passed white-noise hats
(RNG seed 481). Hats repeat at 4 Hz except Pop at 2 Hz; their exponential decay
is 40/s. The complete signal formulas and amplitudes live in the capture script.

The tests expect Crimson, Aurora, Neon, and Blue respectively. This checks that
onset/repetition features survive actual FFT banding, autosensitivity, smoothing,
and frame polling. These names describe designed instrumentation; the fixture is
**not a collection of songs, genre training data, or a real-song accuracy test**.
Realtime capture timing can vary slightly when regenerating the reference.

## Acoustic/country false-positive reference

`acoustic_reference.npz` adds three procedural acoustic-bass negatives with the
same accompaniment and busy high-passed noise hats as the Latin-like positive
above. CAVA capture settings, timing, and array dtypes are unchanged. The complete
reproduction script is:

```sh
python3 scripts/capture_acoustic_reference.py
```

The bass changes between 82, 110, 92, 75, 110, and 92 Hz. It follows these attack
patterns in a four-second phrase:

- `omitted`: 0, 0.5, 1, 2, 3, 3.5 seconds (main-beat notes with omissions).
- `pickup`: 0, 1, 2, 3, 3.75 seconds (one brief anticipation).
- `humanized`: the omitted pattern with up to ±35 ms deterministic timing
  variation. This should not be interpreted as a new genre.

All three must remain Warm throughout the reference, even though their bass
intervals are irregular, notes change, and upper percussion qualifies. This
catches Aurora overgeneralization and false swing caused by missed CAVA hat
onsets. The adjacent `scripts/acoustic_score.py` supplies corresponding idealized
spectra at several tempos/frame rates/volumes, also with a vocal entrance.

The existing idealized swing positive still reaches Gold. Frame sampling,
smoothing, and missed attacks can obscure real swing timing, so the new guard is
deliberately conservative: a genuine shuffle may fit another profile when its
alternation is not visible in CAVA's coarse output.

These are instrumentation recipes passed through CAVA, not recorded songs or a
real-song genre evaluation. No audio is played or system-audio device opened.
