"""Full-band rhythmic context, qualified by breadth and multi-bar repetition."""
from collections import deque
import math

import numpy as np


class RhythmContext:
    def __init__(self):
        self.rows = deque(maxlen=288)
        self.events = deque()
        self._previous = np.zeros(64)
        self._flux = 0.0
        self._next_sample = 0.0
        self._last_event = -math.inf
        self.ready = False
        self.repeat = self.high_rate = self.percussion = 0.0
        self.high_pulse = 0.0
        self.sub_ratio = self.note_motion = self.syncopation = 0.0
        self.swing = self.brightness = 0.0

    def update(self, spectrum, now, dt):
        top = spectrum[44:]
        change = np.maximum(top - self._previous[44:], 0)
        flux = float(change.mean()) / max(.025, float(top.mean()))
        coverage = float(np.mean(change > max(.008, float(change.max()) * .25)))
        high_energy = float(np.sqrt(np.mean(top ** 2)))
        if (coverage >= .40 and high_energy > .012 and flux > max(.08, self._flux * 1.6)
                and now - self._last_event >= .09):
            brightness = float(change @ np.linspace(0, 1, len(change))) / max(1e-12, float(change.sum()))
            self.events.append((now, coverage, brightness))
            self._last_event = now
        self._flux += (flux - self._flux) * (1 - math.exp(-max(0, dt) / 2))
        self._previous = spectrum.copy()
        while self.events and self.events[0][0] < now - 10:
            self.events.popleft()
        if now + 1e-9 >= self._next_sample:
            power = spectrum ** 2
            bass_total = float(power[:12].sum())
            sub = float(power[:6].sum()) / max(1e-12, bass_total)
            self.rows.append((now, high_energy, sub))
            self._next_sample = now + 1 / 24

    def analyze(self, bass, now):
        was_ready = self.ready
        self.ready = False
        self.repeat = self.percussion = self.high_pulse = 0.0
        rows = np.array([r for r in self.rows if r[0] >= now - 10])
        low = np.array([r for r in bass._rows if r[0] >= now - 10])
        if len(rows) < 24 or len(low) < 24:
            return
        span = now - rows[0, 0]
        self.sub_ratio = float(rows[:, 2].mean())
        active = low[:, 1] >= .012
        centroids = low[active, 3]
        self.note_motion = min(1.0, float(centroids.std()) / .16) if len(centroids) else 0.0
        self.syncopation = 1 - bass.regularity
        self.high_rate = len(self.events) / max(2.0, span)
        if len(self.events) < 8 or span < 6 or not active.any():
            return
        events = np.array([event[0] for event in self.events])
        self.brightness = float(np.median([event[2] for event in self.events]))
        intervals = np.diff(events)
        self.swing = float(intervals.std() / max(.01, intervals.mean()))
        grid = np.arange(rows[0, 0], now, 1/24)
        envelope = np.interp(grid, rows[:, 0], rows[:, 1])
        envelope -= envelope.mean()
        correlations = []
        for lag in range(7, min(98, len(envelope)//2)):
            a, b = envelope[:-lag], envelope[lag:]
            correlations.append((lag, float(a@b / max(1e-12, np.linalg.norm(a)*np.linalg.norm(b)))))
        if not correlations:
            return
        self.high_pulse = max(value for _, value in correlations)
        # Repeated dense events can overlap by chance. The high-band envelope
        # itself must repeat; a regular bass must not make random speech rhythmic.
        if self.high_pulse < (.45 if was_ready else .55):
            return
        # Refine repeat periods between samples. Evaluate onset recurrence
        # directly in time: coarse phase bins alias at certain tempos, and a
        # quantized bass clock drifts away from valid 156-BPM percussion.
        peaks = [(i, lag) for i, (lag, value) in enumerate(correlations[1:-1], 1)
                 if 8 <= lag <= 96 and value >= max(.45, self.high_pulse*.85)
                 and value >= correlations[i-1][1] and value >= correlations[i+1][1]]
        if events[-1]-events[0] < 4:
            return  # A short fill is not a persistent new accompaniment.
        coverage = float(np.mean([event[1] for event in self.events]))
        for index, lag in peaks:
            before, at, after = (correlations[index+i][1] for i in (-1, 0, 1))
            curvature = before-2*at+after
            correction = .5*(before-after)/curvature if abs(curvature) > 1e-9 else 0
            period = (lag+float(np.clip(correction, -.5, .5)))/24
            # Require two bar-sized groups of repetitions, without claiming
            # to identify the actual musical meter or downbeat.
            bar = period*(4 if period <= .75 else 2 if period <= 1.5 else 1)
            if span < 2*bar:
                continue
            repeat = self._onset_repeat(events, period, now)
            quality = .35*repeat + .50*at + .15*coverage
            if quality > self.percussion:
                self.repeat, self.percussion = repeat, quality
        # A slightly lower exit threshold prevents one noisy assessment from
        # replacing an established profile with the bass-only warm prior.
        self.ready = (self.repeat >= (.25 if was_ready else .35)
                      and self.percussion >= (.43 if was_ready else .50))

    def _onset_repeat(self, events, period, now):
        source = events[events <= now-period-.1]
        if len(source) < 6:
            return 0.0
        targets = source+period
        right = np.searchsorted(events, targets).clip(0, len(events)-1)
        left = (right-1).clip(0, len(events)-1)
        error = np.minimum(abs(events[right]-targets), abs(events[left]-targets))
        tolerance = max(.06, min(.10, period*.12))
        matches = error <= tolerance
        middle = len(matches)//2
        # The pattern must recur in BOTH halves, not just during one fill.
        observed = min(float(matches[:middle].mean()), float(matches[middle:].mean()))
        # Dense random bursts also coincide by chance. Correct for the window
        # occupied by all events before treating coincidence as repetition.
        chance = min(.8, 2*tolerance*self.high_rate)
        return float(np.clip((observed-chance)/(1-chance), 0, 1))
