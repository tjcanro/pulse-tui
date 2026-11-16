"""Bass-only musical character estimates, not trained artist/genre recognition.

Regular, broad, punchy low-end pulses favor electronic-like Neon, even around
120 BPM. Narrow/rounded bass favors Ember at the same tempo. Upper bands never
enter this module, so a vocal entrance cannot change its evidence.
"""
from __future__ import annotations

from collections import deque
import math

import numpy as np

BASS_BINS = 12  # CAVA's first 12 log-spaced bins: approximately 40–120 Hz.


class BassCharacter:
    def __init__(self):
        self.family = "warm"
        self.label = "listening"
        self.confidence = 0.0
        self.onset_rate = self.regularity = self.activity = 0.0
        self.spread = self.contrast = self.pulse = self.glide = 0.0
        self.pulse_rate = self.residual_spread = 0.0
        self.scores = {}
        self._previous = np.zeros(BASS_BINS)
        self._flux_mean = 0.0
        self._last_attack = -math.inf
        self.attacks = deque()
        self._rows = deque(maxlen=144)
        self._started = None
        self._next_sample = self._next_assessment = 0.0
        self._candidate = "warm"
        self._candidate_since = self._changed = 0.0

    def update(self, bass, now, dt):
        if self._started is None:
            self._started = now
            self._candidate_since = now
        while self.attacks and self.attacks[0][0] < now - 10:
            self.attacks.popleft()
        energy = float(np.sqrt(np.mean(bass ** 2)))
        change = np.maximum(bass - self._previous, 0)
        flux = float(change.mean()) / max(.025, float(bass.mean()))
        self._previous = bass.copy()
        power = bass ** 2
        if energy >= .012:
            distribution = power / max(1e-12, float(power.sum()))
            centroid = float(np.dot(distribution, np.linspace(0, 1, BASS_BINS)))
            entropy = float(-np.sum(distribution * np.log(distribution + 1e-12)) / math.log(BASS_BINS))
            delta_power = change ** 2
            delta_distribution = delta_power / max(1e-12, float(delta_power.sum()))
            attack_entropy = float(-np.sum(delta_distribution * np.log(delta_distribution + 1e-12)) / math.log(BASS_BINS))
            if (flux > max(.08, self._flux_mean * 1.8) and now - self._last_attack >= .16
                    and now - self._started >= .2):
                self.attacks.append((now, attack_entropy))
                self._last_attack = now
            self._flux_mean += (flux - self._flux_mean) * (1 - math.exp(-dt / 2))
        else:
            entropy = centroid = 0.0
            self._flux_mean *= math.exp(-dt / 2)
        window = min(10.0, max(2.0, now - self._started))
        self.onset_rate = len(self.attacks) / window
        if len(self.attacks) >= 4:
            intervals = np.diff([t for t, _ in self.attacks])
            self.regularity = math.exp(-3 * float(intervals.std() / intervals.mean()))
        else:
            self.regularity = 0.0
        rate = min(1.0, self.onset_rate / 4)
        self.activity = min(1.0, .7 * rate + .15 * rate * self.regularity
                            + .1 * min(1.0, self._flux_mean * 5))
        if now + 1e-9 >= self._next_sample:
            self._rows.append((now, energy, entropy, centroid, *bass))
            self._next_sample = now + 1 / 12
        if now + 1e-9 >= self._next_assessment:
            self._next_assessment = now + .5
            self._assess(now)

    def _assess(self, now):
        recent = np.array([row for row in self._rows if row[0] >= now - 10])
        if len(recent) < 24:
            return
        active = recent[recent[:, 1] >= .012]
        if not len(active) or now - active[-1, 0] > 1.25:
            self._candidate, self._candidate_since = self.family, now
            return
        # A decision uses the WINDOW, not just the exact assessment instant.
        # Otherwise a .5-second assessor can always land between 120-BPM kicks.
        # Uniform resampling makes pulse evidence independent of render FPS.
        time_grid = np.arange(max(recent[0, 0], now - 10), now + 1e-8, 1 / 12)
        envelope = np.interp(time_grid, recent[:, 0], recent[:, 1])
        upper, lower = np.percentile(envelope, [90, 20])
        self.contrast = float(np.clip((upper - lower) / max(.025, upper), 0, 1))
        spectra = recent[:, 4:]
        residual = np.maximum(0, spectra - np.percentile(spectra, 20, axis=0))
        residual_power = residual ** 2
        residual_energy = np.sqrt(np.mean(residual_power, axis=1))
        distribution = residual_power / np.maximum(1e-12, residual_power.sum(axis=1, keepdims=True))
        residual_width = -np.sum(distribution * np.log(distribution + 1e-12), axis=1) / math.log(BASS_BINS)
        residual_centroid = distribution @ np.linspace(0, 1, BASS_BINS)
        strong = residual_energy >= max(.004, float(np.percentile(residual_energy, 70)))
        self.residual_spread = float(np.median(residual_width[strong])) if strong.any() else 0.0
        # Remove the sustained per-bin bed before looking for a pulse or pitch
        # sweep; a kick need not rise out of silence to supply that evidence.
        pulse_envelope = np.interp(time_grid, recent[:, 0], residual_energy)
        centered = pulse_envelope - pulse_envelope.mean()
        self.pulse = 0.0
        self.pulse_rate = 0.0
        correlations = []
        if centered.std() > .002:
            # ~0.33–1.33 seconds includes ordinary mid-tempo grooves. This is
            # periodicity evidence, not a precise BPM/downbeat estimator.
            for lag in range(4, min(17, len(centered) // 2)):
                a, b = centered[:-lag], centered[lag:]
                correlation = float(np.dot(a, b) / max(1e-12, np.linalg.norm(a) * np.linalg.norm(b)))
                correlations.append((lag, correlation))
                self.pulse = max(self.pulse, correlation)
        if self.pulse >= .65:
            # Prefer the shortest strong period, rather than a double-length
            # harmonic. Onsets may be weak in compressed or smoothed music.
            lag = next(lag for lag, strength in correlations if strength >= self.pulse * .92)
            self.pulse_rate = 12 / lag
        attack_widths = [width for _, width in self.attacks]
        # Silent gaps have entropy zero, not evidence of a pitched/rounded body.
        loud = recent[:, 1] >= max(.012, float(np.percentile(recent[:, 1], 50)))
        body_width = float(recent[loud, 2].mean())
        self.spread = float(np.median(attack_widths)) if len(attack_widths) >= 3 else body_width
        glides = []
        for when, _ in self.attacks:
            if when + .24 > now or when < recent[0, 0]:
                continue
            early = float(np.interp(when + .025, recent[:, 0], residual_centroid))
            late = float(np.interp(when + .20, recent[:, 0], residual_centroid))
            tail_energy = float(np.interp(when + .20, recent[:, 0], residual_energy))
            if tail_energy >= max(.004, float(residual_energy.max()) * .05):
                glides.append(max(0.0, early - late))
        self.glide = float(np.median(glides)) if len(glides) >= 3 else 0.0
        wide = float(np.clip((max(self.spread, self.residual_spread) - .60) / .28, 0, 1))
        # Electronic kicks can start narrow and sweep down in pitch. A fixed
        # acoustic fundamental at the same tempo does not supply that evidence.
        glide_strength = min(1.0, self.glide / .12)
        kick = max(wide, glide_strength)
        punch = float(np.clip((self.contrast - .20) / .60, 0, 1))
        rhythm = max(self.regularity, self.pulse * .95)
        effective_rate = max(self.onset_rate, self.pulse_rate)
        driving = float(np.clip((effective_rate - .9) / .65, 0, 1))
        electronic = kick * (.72 + .28 * punch) * (.35 + .65 * rhythm) * driving
        rounded = float(np.clip((.82 - self.spread) / .35, 0, 1))
        tonal_body = float(np.clip((.90 - body_width) / .25, 0, 1))
        rounded = max(rounded, tonal_body)
        flowing = (max(0.0, 1 - abs(self.spread - .65) / .24)
                   * max(0.0, 1 - abs(self.contrast - .45) / .55) * (.4 + .6 * rhythm))
        sustained = (max(0.0, (body_width - .72) / .28)
                     * max(0.0, 1 - self.contrast / .35))
        rough = wide * punch * (1 - rhythm) * min(1.0, self.onset_rate / 3)
        scores = {"warm": (.45 + .5 * rounded * (1 - .85 * glide_strength), "rounded"),
                  "neon": (electronic, "driving"),
                  "blue": (flowing * .9, "flowing"),
                  "aurora": (sustained * .9, "sustained"),
                  "crimson": (rough * .9, "rough")}
        if effective_rate < 1.1 and self.contrast > .35:
            scores["warm"] = (max(scores["warm"][0], .70), "mellow")
        scores = self._style_scores(scores, now)
        self.scores = {name: float(score) for name, (score, _) in scores.items()}
        ranked = sorted(scores, key=lambda k: scores[k][0], reverse=True)
        winner = ranked[0]
        confidence, label = scores[winner]
        self.confidence = min(1.0, confidence)
        # Ambiguous evidence holds the current choice; it does not bounce to an
        # arbitrary genre. Require a lead and sustained evidence before a change.
        enough = (now - self._started >= 3 and confidence >= .62
                  and confidence - scores[ranked[1]][0] >= .10)
        if not enough:
            self.label = "holding" if now - self._started >= 3 else "listening"
            self._candidate = self.family
            self._candidate_since = now
            return
        if winner == self.family:
            self.label = label
            self._candidate = winner
            self._candidate_since = now
        elif winner != self._candidate:
            self._candidate, self._candidate_since = winner, now
            self.label = 'settling ' + winner
        elif now - self._candidate_since >= 1.5 and now - self._changed >= 6:
            self.family, self.label, self._changed = winner, label, now

    def _style_scores(self, scores, now):
        """Bass-only baseline; MusicCharacter adds guarded rhythmic context."""
        return scores
