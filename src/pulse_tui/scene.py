"""Turn frequency amplitudes into an animated 3D height field."""
from __future__ import annotations

import dataclasses
import math

import numpy as np

from .settings import BARS
from .colors import AdaptiveColors
from .director import MusicDirector
from .history import TerrainHistory
from .looks import LOOKS

@dataclasses.dataclass
class Pulse:
    when: float
    x: float
    z: float
    band: int
    strength: float
    pan: float = 0.0



class Scene:
    """Audio-responsive heights and colors, independent of camera or terminal."""
    def __init__(self, color_response=1.35, cycle_seconds=14.0):
        self.colors = AdaptiveColors(response=color_response, cycle_seconds=cycle_seconds)
        self.history = TerrainHistory()
        self.director = MusicDirector()
        self.band_pan = np.zeros(3)
        self.pulses = []
        self.levels = np.zeros(3)
        self.average = np.full(3, .06)
        self.previous = np.zeros(3)
        self.last_hit = np.full(3, -10.0)
        self.counter = 0
        self.spectrum = np.zeros(BARS)
        self._visual_spectrum = np.zeros(BARS)

    def add(self, now, band, strength=1.0, pan=None):
        angle = self.counter * 2.399963
        radius = (1.4, 4.0, 5.7)[band]
        self.pulses.append(Pulse(now, math.cos(angle) * radius, math.sin(angle) * radius,
                                 band, min(1.6, max(.15, strength)),
                                 self.band_pan[band] if pan is None else pan))
        self.pulses = self.pulses[-12:]
        self.counter += 1

    def update(self, spectrum, now, dt):
        spectrum = np.asarray(spectrum, dtype=float)
        stereo = np.stack((spectrum, spectrum)) if spectrum.ndim == 1 else spectrum
        if stereo.shape != (2, BARS):
            raise ValueError("Expected 64 mono bands or a 2 x 64 stereo spectrum")
        spectrum = stereo.mean(axis=0)
        self.colors.update(spectrum, now, dt)
        self.history.update(stereo, now, dt)
        self.director.update(stereo, now, dt, max(self.colors.activity, self.colors.intensity * .65))
        self.spectrum = spectrum
        self._visual_spectrum += (spectrum - self._visual_spectrum) * (1 - math.exp(-max(0, dt) / .10))
        # Log-spaced CAVA bins: approximately 40–200, 200–2500 and 2500–16000 Hz.
        levels = np.array([np.sqrt(np.mean(spectrum[a:b] ** 2))
                           for a, b in ((0, 17), (17, 44), (44, BARS))])
        smoothing = 1 - math.exp(-max(dt, 0) * 18)
        self.levels += (levels - self.levels) * smoothing
        adaptation = 1 - math.exp(-max(dt, 0) * 1.8)
        self.average += (levels - self.average) * adaptation
        flux = np.maximum(levels - self.previous, 0)
        for band in range(3):
            a, b = ((0, 17), (17, 44), (44, BARS))[band]
            sides = np.sum(stereo[:, a:b] ** 2, axis=1)
            self.band_pan[band] = (sides[1] - sides[0]) / max(.001, sides.sum())
            threshold = max(.018, self.average[band] * .16)
            if levels[band] > .035 and flux[band] > threshold and now - self.last_hit[band] > (.18, .13, .09)[band]:
                self.add(now, band, .4 + levels[band] * 1.8 + flux[band] * 1.5)
                self.last_hit[band] = now
        self.previous = levels.copy()
        self.pulses = [p for p in self.pulses if now - p.when < 3.5]

    def surface(self, x, z, now, gain, options=None):
        """Evaluate world-space heights and heat for the supplied grid positions."""
        style = LOOKS[options.look if options else "cinematic"]
        stereo = style.stereo if options is None or options.stereo else 0.0
        h = .10 * np.sin(x * .52 + z * .32) + .07 * np.sin(x * .91 - z * .64)
        energy = np.zeros_like(x)
        high_energy = np.zeros_like(x)
        for p in self.pulses:
            age = max(0, now - p.when)
            # Bass stays close to the center; mids/treble travel farther sideways.
            shift = p.pan * stereo * (1.5 if p.band == 0 else 4.0)
            dx, dz = (x - p.x - shift) / style.ripple_scale, (z - p.z) / style.ripple_scale
            r = np.sqrt(dx * dx + dz * dz)
            speed, frequency = ((5.5, 2.0), (4.0, 3.5), (6.0, 7.5))[p.band]
            speed *= style.speed
            envelope = math.exp(-age * (1.65 if p.band == 2 else .9))
            ring = np.exp(-((r - age * speed) * .8) ** 2)
            crest = ring * envelope * p.strength * (.32 if p.band == 2 else .8) * gain
            mound = np.exp(-r * r * (.27 if p.band == 1 else .13)) * math.exp(-age * 1.8) * p.strength * gain
            if style.motion:
                attack = 1 - math.exp(-age / .065)
                crest *= attack
                mound *= attack
            h += np.sin(r * frequency - age * speed * frequency) * crest + mound
            energy += crest + mound * .4
            if p.band == 2:
                high_energy += crest
        # Sustained frequencies shape the center even when no distinct attack is detected.
        r = np.sqrt(x * x + z * z)
        angle = np.arctan2(z, x)
        band_index = (angle + np.pi) * (BARS - 1) / (2 * np.pi)
        spectrum = self._visual_spectrum if style.motion else self.spectrum
        amplitudes = np.interp(band_index, np.arange(BARS), spectrum)
        h += amplitudes * np.exp(-r * r * .065) * gain * 1.4
        if style.memory and (options is None or options.history):
            trail = self.history.sample(x, z, now, speed=style.speed, stereo=stereo)
            h += trail * style.memory * gain * 1.8
            energy += trail * style.memory * .6
        if style.sections and (options is None or options.sections):
            for when, strength in self.director.releases:
                age = max(0, now - when)
                ring = np.exp(-((r - age * 5.5 * style.speed) / .9) ** 2)
                ring *= strength * math.exp(-age * .6) * style.sections
                ring *= (1 - math.exp(-age / .14)) ** 2
                h += ring * gain * .55
                energy += ring * .65
        return x, h, z, np.clip(energy * .6 + h * .16, 0, 1), high_energy
