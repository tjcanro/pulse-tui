"""Continuous camera cues and conservative buildup/release section heuristics."""
from __future__ import annotations

import math

import numpy as np


class MusicDirector:
    def __init__(self):
        self.intensity = 0.0
        self.tension = 0.0
        self.pan = 0.0
        self.energy = 0.0
        self.baseline = 0.0
        self.section = "calm"
        self.releases = []
        self._previous = np.zeros(64)
        self._started = None
        self._build_time = 0.0
        self._peak_tension = 0.0
        self._last_release = -math.inf
        self._section_since = 0.0

    def update(self, stereo, now, dt, activity):
        dt = max(0.0, dt)
        mono = stereo.mean(axis=0)
        energy = float(np.sqrt(np.mean(mono ** 2)))
        novelty = float(np.maximum(mono - self._previous, 0).mean())
        self._previous = mono.copy()
        if self._started is None:
            self._started = now
            self.energy = self.baseline = energy
        self.energy += (energy - self.energy) * (1 - math.exp(-dt / .5))
        self.baseline += (energy - self.baseline) * (1 - math.exp(-dt / 7))
        target = min(1.0, max(0.0, (self.energy - self.baseline) / max(.10, self.baseline) * 1.4))
        self.tension += (target - self.tension) * (1 - math.exp(-dt / 1.5))
        self._peak_tension = max(self.tension, self._peak_tension * math.exp(-dt / 6))
        self._build_time = min(6.0, max(0, self._build_time + (dt if self.tension > .18 else -dt)))
        if (now - self._started > 5 and now - self._last_release > 8
                and self._build_time > 1.5 and self._peak_tension > .35
                and (novelty > .09 or self._peak_tension - self.tension > .22)):
            self.releases.append((now, min(1.0, .5 + self._peak_tension * .5)))
            self._last_release = now
            self._build_time = 0.0
            self._peak_tension = 0.0
        self.releases = [(t, s) for t, s in self.releases if now - t < 5][-3:]
        # No per-kick camera shake: these cues move on a much slower time scale.
        audible_activity = activity * min(1.0, energy / .03)
        target_intensity = min(1.0, .75 * audible_activity + .25 * min(1.0, self.energy / .45))
        self.intensity += (target_intensity - self.intensity) * (1 - math.exp(-dt / 2.5))
        sides = np.sum(stereo ** 2, axis=1)
        pan = float((sides[1] - sides[0]) / max(.01, float(sides.sum())))
        self.pan += (pan - self.pan) * (1 - math.exp(-dt / 1.2))
        state = ("release" if now - self._last_release < 2.5 else
                 "build" if self.tension > .3 else
                 "drive" if self.intensity > .58 else
                 "calm" if self.intensity < .23 else "flow")
        if state != self.section and (state == "release" or now - self._section_since > 2):
            self.section, self._section_since = state, now

    def openness(self, now):
        """A smooth opening after a release, never a camera cut."""
        result = 0.0
        for when, strength in self.releases:
            age = max(0, now - when)
            fade = min(1.0, max(0.0, (5 - age) / 2))
            fade = fade * fade * (3 - 2 * fade)
            result += strength * (1 - math.exp(-age / .65)) ** 2 * math.exp(-age / 2) * fade
        return min(1.0, result)
