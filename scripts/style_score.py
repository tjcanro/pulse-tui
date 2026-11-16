"""Procedural musical feature examples for tests/previews, never runtime inputs.

Names describe intended instrumentation, not labeled recordings or genre data.
All pitched parts use Gaussian CAVA-bin envelopes; percussion uses broad highs.
"""
import math
import numpy as np


STYLES = ('acoustic', 'hip-hop', 'latin', 'electronic', 'pop', 'swing',
          'soul', 'dance-pop', 'ambient')


def strikes(now, onsets, period, decay):
    return sum(math.exp(-((now - onset) % period) * decay) for onset in onsets)


def style_score(now, style, lively=.65):
    bins = np.arange(64)
    spectrum = np.zeros(64)
    beat = now % .5
    center, width, body, attack = 8, 1.1, .12, .5*math.exp(-beat*10)
    hats = strikes(now, (0, .5, 1, 1.5), 2, 25)
    mid, top = .18, .18
    if style == 'acoustic':
        attack = .4*math.exp(-(now % .75)*6)
        top = 0
    elif style == 'hip-hop':
        center, body = 2, .33
        attack = .35*strikes(now, (0, .75, 1.5, 2.75, 3.25), 4, 9)
        hats = strikes(now, np.arange(0, 2, .25), 2, 25)
    elif style == 'latin':
        notes = (8, 10, 7, 10, 9)
        onsets = (0, .75, 1.5, 2.5, 3.75)
        ages = [(now-onset) % 4 for onset in onsets]
        center = notes[int(np.argmin(ages))]
        attack = .5*strikes(now, onsets, 4, 10)
        hats = strikes(now, np.arange(0, 2, .25), 2, 25)
    elif style == 'electronic':
        center, width, body = 6, 4.5, .08
        attack = .7*math.exp(-beat*20)
        hats = strikes(now, np.arange(0, 2, .25), 2, 25)
    elif style == 'pop':
        pass
    elif style == 'swing':
        center = (5, 8, 10, 6)[int(now*2) % 4]
        hats = strikes(now, (0, .3, .5, .8, 1, 1.3, 1.5, 1.8), 2, 30)
    elif style == 'soul':
        center, body = 2, .3
        attack = .18*math.exp(-beat*6)
    elif style == 'dance-pop':
        hats = strikes(now, np.arange(0, 2, .25), 2, 25)
        mid, top = .035, .3
    elif style == 'ambient':
        spectrum[:12] = .16
        spectrum[25] = .4*(1+.08*math.sin(now*.3))
        return spectrum
    else:
        raise ValueError(style)
    spectrum[:12] = np.exp(-((bins[:12]-center)/width)**2) * (body+attack)
    # Melodic midrange and truly wide, transient high-band percussion.
    spectrum[12:44] = np.exp(-((bins[12:44]-26)/6)**2) * mid * (1+.25*math.sin(now*3))
    spectrum[44:] = top*(.8+.2*np.cos(bins[44:]*.7))*hats
    if style == 'dance-pop':
        spectrum[44:] *= np.linspace(.25, 1, 20)
    # Expression changes the upper parts, leaving their timing and bass intact.
    spectrum[12:] *= .4+.9*lively
    return np.clip(spectrum, 0, 1)


def vocal_score(now, strength=1):
    """Moving midrange formants with occasional narrow upper harmonics."""
    bins = np.arange(64)
    center = 27+5*math.sin(now*2.3)
    body = np.exp(-((bins-center)/5)**2)
    harmonic = .3*np.exp(-((bins-47-2*math.sin(now*1.7))/1.5)**2)
    spectrum = strength*(body+harmonic)*(.3+.4*math.exp(-(now % .31)*8))
    spectrum[:12] = 0
    return spectrum
