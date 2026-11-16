"""Audio-only character palettes with expressive, smooth in-family color motion."""
from __future__ import annotations

import math
import numpy as np

from .character import BASS_BINS
from .style import MusicCharacter
# Keep the public conversion helpers importable from the original module.
from .palettes import CYCLE_ORDER, PALETTE_LABS, PRESET_RGB, expressive_labs, lab_to_rgb
from .settings import BARS

_NAMES = tuple(PALETTE_LABS)


class AdaptiveColors:
    """Bass and qualified percussion choose a family; all bands add expression.

    No metadata, network, artist lists, or external models are used. Color work
    is capped at eight updates/second and RGB steps are bounded to avoid flashes.
    """
    def __init__(self, response=1.35, cycle_seconds=14.0):
        self.response = response
        self.cycle_seconds = cycle_seconds
        self.character = MusicCharacter()
        self.weights = np.zeros(len(_NAMES))
        self.weights[0] = 1.0
        self.activity = self.brightness = self.onset_rate = self.regularity = 0.0
        self.intensity = self._display_intensity = .35
        self.name = 'warm'
        self._palette = PRESET_RGB['warm']
        self._palettes = dict(PRESET_RGB, auto=self._palette)
        self._previous = np.zeros(BARS)
        self._positions = np.linspace(0, 1, BARS)
        self._baseline = None
        self._last_time = None
        self._last_palette_time = None
        self._refresh_in = 0.0

    @property
    def _attacks(self):
        """Bass onset history, retained for diagnostics and existing checks."""
        return self.character.attacks

    def update(self, spectrum, now, dt):
        if self._last_time is not None and now < self._last_time:
            self.__init__(self.response, self.cycle_seconds)
        elapsed = max(0.0, dt if self._last_time is None else now - self._last_time)
        self._last_time = now
        spectrum = np.clip(np.asarray(spectrum, dtype=float), 0, 1)
        power = spectrum * spectrum
        rms = float(np.sqrt(power.mean()))
        self.character.update(spectrum, now, elapsed)
        self.onset_rate = self.character.onset_rate
        self.regularity = self.character.regularity
        self.activity = self.character.activity
        bass_rms = float(np.sqrt(np.mean(power[:BASS_BINS])))
        if rms < .012 and bass_rms < .012:
            self._previous = spectrum.copy()
            return  # Silence holds all displayed colors, not just the hue name.

        broad_flux = float(np.maximum(spectrum - self._previous, 0).mean()) / max(.025, float(spectrum.mean()))
        self._previous = spectrum.copy()
        brightness = float(np.dot(power, self._positions) / max(1e-12, float(power.sum())))
        self.brightness += (brightness - self.brightness) * (1 - math.exp(-elapsed / 2))
        if self._baseline is None:
            self._baseline = rms
        self._baseline += (rms - self._baseline) * (1 - math.exp(-elapsed / 12))
        relative = float(np.clip((rms / max(.035, self._baseline) - .55) / 1.1, 0, 1))
        # Relative section energy helps despite CAVA autosensitivity. Broad flux
        # and overall spectral brightness animate expression, not family scores.
        target = (.40 * min(1.0, rms / .28) + .35 * relative
                  + .18 * min(1.0, broad_flux * 2.5) + .07 * self.brightness)
        target = float(np.clip(.4 + (target - .4) * self.response, 0, 1))
        tau = .4 if target > self.intensity else 1.6
        self.intensity += (target - self.intensity) * (1 - math.exp(-elapsed / tau))
        self._display_intensity += (self.intensity - self._display_intensity) * (1 - math.exp(-elapsed / .65))

        if float(np.mean(power[:BASS_BINS])) >= .012 ** 2:
            destination = np.zeros(len(_NAMES))
            destination[_NAMES.index(self.character.family)] = 1.0
            self.weights += (destination - self.weights) * (1 - math.exp(-elapsed / 2.5))
        winner = int(self.weights.argmax())
        current = _NAMES.index(self.name)
        if self.weights[winner] > self.weights[current] + .12:
            self.name = _NAMES[winner]

        self._refresh_in -= elapsed
        if self._refresh_in <= 1e-9:
            labs = [expressive_labs(name, self._display_intensity) for name in _NAMES]
            auto = np.tensordot(self.weights, np.array(labs), axes=1)
            refresh_elapsed = elapsed if self._last_palette_time is None else now - self._last_palette_time
            step = max(1, min(18, round(120 * refresh_elapsed)))
            for mode, gradient in [*zip(_NAMES, labs), ('auto', auto)]:
                target_rgb = np.array([lab_to_rgb(color) for color in gradient])
                before = np.array(self._palettes[mode])
                limited = before + np.clip(target_rgb - before, -step, step)
                self._palettes[mode] = tuple(tuple(map(int, rgb)) for rgb in limited)
            self._palette = self._palettes['auto']
            self._last_palette_time = now
            self._refresh_in = .125

    def palette(self, mode='auto', now=None):
        if mode == 'cycle':
            # Pure scene-clock rendering: cycles even with no new audio frames,
            # and is deterministic/frozen when the scene is paused.
            when = (self._last_time or 0.0) if now is None else max(0.0, now)
            phase = when / self.cycle_seconds
            index = int(phase) % len(CYCLE_ORDER)
            fraction = .5 - .5 * math.cos(math.pi * (phase % 1))
            before = expressive_labs(CYCLE_ORDER[index], self._display_intensity)
            after = expressive_labs(CYCLE_ORDER[(index + 1) % len(CYCLE_ORDER)], self._display_intensity)
            return tuple(lab_to_rgb(lab) for lab in before + (after - before) * fraction)
        return self._palettes[mode]
