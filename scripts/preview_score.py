"""Deterministic stereo spectra for tests/renderings only, never an app mode."""
import math
import numpy as np

_BINS = np.linspace(0, 1, 64)


def stereo_score(now):
    """Intro, buildup, driving release, and breakdown; L/R lead alternation."""
    if now < 6:
        rate, volume, floor = .8, .35, .025
    elif now < 14:
        progress = (now - 6) / 8
        rate, volume, floor = 2, .25 + .55 * progress, .025 + .16 * progress
    elif now < 26:
        rate, volume, floor = 4, .95, .07
    else:
        rate, volume, floor = 1, .4, .035
    bass = np.exp(-((_BINS - .13) / .11) ** 2)
    lead = np.exp(-((_BINS - (.43 + .07 * math.sin(now * 1.3))) / .1) ** 2)
    hats = np.exp(-((_BINS - .85) / .09) ** 2)
    kick = math.exp(-(now % (1 / rate)) * 12)
    note = math.exp(-((now + .13) % (1 / rate)) * 9)
    tick = math.exp(-(now % (1 / rate)) * 30)
    pan = .85 * math.sin(now * 1.7)
    channels = []
    for side in (-1, 1):
        spectrum = (bass * kick * .85 + lead * note * (.6 + side * pan * .48)
                    + hats * tick * (.25 - side * pan * .15)) * volume
        spectrum += floor * (bass * .4 + lead * .7 + hats * .2)
        if 14 <= now < 14.12:
            spectrum += .8 * bass
        channels.append(np.clip(spectrum, 0, 1))
    return np.array(channels)
