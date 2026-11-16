"""Controlled bass timbres for QA/renderings, not labeled genre training data."""
import math
import numpy as np


def character_score(now, kind='rounded', lively=0.0):
    """Two 120-BPM patterns: pitched/rounded versus broad/percussive bass."""
    spectrum = np.zeros(64)
    positions = np.linspace(0, 1, 64)[:12]
    phase = now % .5
    if kind == 'rounded':
        bass = np.exp(-((positions - .11) / .018) ** 2)
        spectrum[:12] = bass * (.18 + .45 * math.exp(-phase * 6))
    elif kind == 'driving':
        bass = np.exp(-((positions - .12) / .15) ** 2)
        spectrum[:12] = bass * (.1 + .7 * math.exp(-phase * 20))
    else:
        raise ValueError(kind)
    # Bass is invariant: liveliness only introduces mids and highs.
    x = np.linspace(0, 1, 64)
    melody = np.exp(-((x - .40) / .11) ** 2)
    hats = np.exp(-((x - .84) / .09) ** 2)
    extra = (melody * (.10 + .7 * math.exp(-((now + .07) % .25) * 12))
             + hats * .5 * math.exp(-(now % .125) * 30)) * lively
    extra[:12] = 0
    return np.clip(spectrum + extra, 0, 1)
