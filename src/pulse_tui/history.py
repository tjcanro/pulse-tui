"""A bounded, smoothly sampled stereo history, advected toward the horizon."""
from __future__ import annotations

from collections import deque

import numpy as np


class TerrainHistory:
    def __init__(self):
        self.times = deque(maxlen=192)
        self.rows = deque(maxlen=192)
        self._smoothed = np.zeros((2, 32))
        self._last_update = None
        self._cache = None

    def update(self, stereo, now, dt):
        if self.times and now < self.times[-1]:
            self.__init__()
        # Adjacent-bin averaging removes spikes without blurring the time axis.
        row = np.asarray(stereo).reshape(2, 32, 2).mean(axis=2)
        row = np.stack([np.convolve(channel, [1, 2, 3, 2, 1], mode="same") / 9
                        for channel in row])
        elapsed = dt if self._last_update is None else max(0, now - self._last_update)
        self._last_update = now
        self._smoothed += (row - self._smoothed) * (1 - np.exp(-elapsed / .16))
        if not self.times or now - self.times[-1] >= 1 / 12 - 1e-8:
            self.times.append(now)
            self.rows.append(self._smoothed.copy())
            self._cache = None

    def sample(self, x, z, now, speed=1.0, stereo=1.0):
        """Bilinear interpolation in time/frequency; zero before recording began."""
        if len(self.times) < 2:
            return np.zeros_like(x)
        if self._cache is None:
            self._cache = np.array(self.times), np.array(self.rows)
        times, rows = self._cache
        age = np.maximum(0, 1 - z) / (1.9 * speed)
        requested = now - age
        high = np.clip(np.searchsorted(times, requested), 1, len(times) - 1)
        low = high - 1
        t = np.clip((requested - times[low]) / (times[high] - times[low]), 0, 1)
        frequency = np.clip(np.abs(x) / 14, 0, 1) * 31
        a = np.minimum(30, frequency.astype(int))
        f = frequency - a
        values = []
        for channel in (0, 1):
            before = rows[low, channel, a] * (1 - f) + rows[low, channel, a + 1] * f
            after = rows[high, channel, a] * (1 - f) + rows[high, channel, a + 1] * f
            values.append(before * (1 - t) + after * t)
        pan = (.5 + .5 * np.tanh(x / 3)) * stereo + .5 * (1 - stereo)
        value = values[0] * (1 - pan) + values[1] * pan
        # Soft entry and exit prevent a hard moving wall at the history boundary.
        fade_in = np.clip((times[-1] - requested) / .65, 0, 1)
        fade_out = np.clip((requested - times[0]) / .8, 0, 1)
        behind = np.clip((1 - z) / 2.2, 0, 1)
        edge = np.exp(-(np.abs(x) / 17) ** 6) * np.exp(-age * .065)
        return value * fade_in * fade_out * behind * edge
