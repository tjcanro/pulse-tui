"""Turn frequency amplitudes into an animated 3D height field."""
from __future__ import annotations

import dataclasses
import math

import numpy as np

from .settings import BARS

@dataclasses.dataclass

class Pulse:
    when: float
    x: float
    z: float
    band: int
    strength: float



class Scene:
    """Audio-responsive heights and colors, independent of camera or terminal."""
    def __init__(self):
        self.pulses = []
        self.levels = np.zeros(3)
        self.average = np.full(3, .06)
        self.previous = np.zeros(3)
        self.last_hit = np.full(3, -10.0)
        self.counter = 0
        self.spectrum = np.zeros(BARS)

    def add(self, now, band, strength=1.0):
        angle = self.counter * 2.399963
        radius = (1.4, 4.0, 5.7)[band]
        self.pulses.append(Pulse(now, math.cos(angle) * radius, math.sin(angle) * radius,
                                 band, min(1.6, max(.15, strength))))
        self.pulses = self.pulses[-12:]
        self.counter += 1

    def update(self, spectrum, now, dt):
        self.spectrum = spectrum
        # Log-spaced CAVA bins: approximately 40–200, 200–2500 and 2500–16000 Hz.
        levels = np.array([np.sqrt(np.mean(spectrum[a:b] ** 2))
                           for a, b in ((0, 17), (17, 44), (44, BARS))])
        smoothing = 1 - math.exp(-max(dt, 0) * 18)
        self.levels += (levels - self.levels) * smoothing
        adaptation = 1 - math.exp(-max(dt, 0) * 1.8)
        self.average += (levels - self.average) * adaptation
        flux = np.maximum(levels - self.previous, 0)
        for band in range(3):
            threshold = max(.018, self.average[band] * .16)
            if levels[band] > .035 and flux[band] > threshold and now - self.last_hit[band] > (.18, .13, .09)[band]:
                self.add(now, band, .4 + levels[band] * 1.8 + flux[band] * 1.5)
                self.last_hit[band] = now
        self.previous = levels.copy()
        self.pulses = [p for p in self.pulses if now - p.when < 3.5]

    def surface(self, x, z, now, gain):
        """Evaluate world-space heights and heat for the supplied grid positions."""
        h = .10 * np.sin(x * .52 + z * .32) + .07 * np.sin(x * .91 - z * .64)
        energy = np.zeros_like(x)
        high_energy = np.zeros_like(x)
        for p in self.pulses:
            age = max(0, now - p.when)
            dx, dz = x - p.x, z - p.z
            r = np.sqrt(dx * dx + dz * dz)
            speed, frequency = ((5.5, 2.0), (4.0, 3.5), (6.0, 7.5))[p.band]
            envelope = math.exp(-age * (1.65 if p.band == 2 else .9))
            ring = np.exp(-((r - age * speed) * .8) ** 2)
            crest = ring * envelope * p.strength * (.32 if p.band == 2 else .8) * gain
            mound = np.exp(-r * r * (.27 if p.band == 1 else .13)) * math.exp(-age * 1.8) * p.strength * gain
            h += np.sin(r * frequency - age * speed * frequency) * crest + mound
            energy += crest + mound * .4
            if p.band == 2:
                high_energy += crest
        # Sustained frequencies shape the center even when no distinct attack is detected.
        r = np.sqrt(x * x + z * z)
        angle = np.arctan2(z, x)
        band_index = (angle + np.pi) * (BARS - 1) / (2 * np.pi)
        amplitudes = np.interp(band_index, np.arange(BARS), self.spectrum)
        h += amplitudes * np.exp(-r * r * .065) * gain * 1.4
        return x, h, z, np.clip(energy * .6 + h * .16, 0, 1), high_energy
