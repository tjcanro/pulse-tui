"""Pitched acoustic-bass examples with drums, omissions, and brief pickups.

Procedural regression inputs, not recorded songs or genre training data. Unlike
Latin's repeated anticipation pattern, most notes stay on the main beat phase.
"""
import math
import numpy as np

from style_score import style_score


PATTERNS = {
    'omitted': (0, .5, 1, 2, 3, 3.5),
    'pickup': (0, 1, 2, 3, 3.75),
    'humanized': (0, .5, 1, 2, 3, 3.5),
}


def acoustic_score(now, variant='omitted'):
    spectrum = style_score(now, 'latin')
    onsets = PATTERNS[variant]
    # Different note names do not imply syncopation. Root/fifth changes are
    # deliberately as large as the existing Latin example's pitch movement.
    notes = (7, 10, 8, 7, 10, 8)
    events = []
    for phrase in range(math.floor(now/4)-1, math.floor(now/4)+1):
        for i, onset in enumerate(onsets):
            jitter = .035*math.sin((phrase*len(onsets)+i)*1.31) if variant == 'humanized' else 0
            event = phrase*4+onset+jitter
            if event <= now:
                events.append((event, notes[i]))
    last, center = max(events)
    spectrum[:12] = np.exp(-((np.arange(12)-center)/1.1)**2) * (.12+.5*math.exp(-(now-last)*10))
    return spectrum
