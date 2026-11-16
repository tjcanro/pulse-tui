#!/usr/bin/env python3
"""Procedural country/acoustic bass with busy hats -> actual CAVA, via FIFO.

No audio is played and no system capture device is opened. This is controlled
instrumentation, not recorded country music or a genre evaluation corpus.
"""
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import numpy as np

from acoustic_score import PATTERNS
from capture_style_reference import ROOT, RATE, SECONDS, capture


def acoustic_pcm(variant):
    t = np.arange(RATE*SECONDS)/RATE
    onsets, frequencies = [], []
    notes = (82, 110, 92, 75, 110, 92)
    pattern = PATTERNS[variant]
    for phrase in range(-1, SECONDS//4+1):
        for i, onset in enumerate(pattern):
            jitter = .035*np.sin((phrase*len(pattern)+i)*1.31) if variant == 'humanized' else 0
            onsets.append(phrase*4+onset+jitter)
            frequencies.append(notes[i % len(notes)])
    onsets, frequencies = np.array(onsets), np.array(frequencies)
    last = (np.searchsorted(onsets, t, side='right')-1).clip(0, len(onsets)-1)
    age = t-onsets[last]
    phase = np.cumsum(frequencies[last])/RATE
    audio = np.sin(2*np.pi*phase)*(.08+.4*np.exp(-age*8))
    noise = np.random.default_rng(481).normal(0, 1, len(t))
    noise = np.r_[0, np.diff(noise)]*.5
    audio += noise*.18*np.exp(-(t % .25)*40)
    audio += .065*np.sin(2*np.pi*260*t)+.035*np.sin(2*np.pi*510*t)
    audio = np.clip(audio, -1, 1)*24000
    return np.repeat(audio.astype('<i2')[:, None], 2, axis=1).tobytes()


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(partial(capture, make_pcm=acoustic_pcm), PATTERNS))
    np.savez_compressed(ROOT/'tests/data/acoustic_reference.npz',
        **{key: value for name, rows, times in results
           for key, value in ((name+'_frames', rows), (name+'_times', times))})


if __name__ == '__main__':
    main()
