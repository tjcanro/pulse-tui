"""Genre-like audio character: guarded multi-band rhythm over a bass baseline.

These are transparent musical-feature rules, not a trained genre classifier.
The base class performs one stable selection after this context hook runs.
"""
from .character import BassCharacter
from .rhythm import RhythmContext


class MusicCharacter(BassCharacter):
    def __init__(self):
        super().__init__()
        self.rhythm = RhythmContext()

    def update(self, spectrum, now, dt):
        self.rhythm.update(spectrum, now, dt)
        super().update(spectrum[:12], now, dt)

    def _style_scores(self, scores, now):
        r = self.rhythm
        r.analyze(self, now)
        # Very still, diffuse low-end beds use Ice. This is bass-only: adding a
        # melodic/vocal line must not change an ambient passage's family either.
        if (not r.ready and scores['aurora'][0] > .65 and self.onset_rate < .25
                and self.contrast < .12 and now - self._started > 8):
            return {**{k: (value*.7, label) for k, (value, label) in scores.items()},
                    'ice': (.9, 'ambient-like')}
        if not r.ready:
            return scores  # A vocal/body change or a single fill is not enough.

        sustain = 1 - self.contrast
        sub = r.sub_ratio
        sync = r.syncopation
        subdivisions = r.high_rate / max(.6, self.onset_rate)
        bass_kick = max(self.spread, self.residual_spread) > .78 or self.glide > .12
        # Distinct rhythmic profiles avoid giving Warm a permanent scoring prior.
        # Hip-hop: substantial sustained sub + dense hats; Latin: anticipated/
        # syncopated pitched bass against a repeating percussion pattern.
        if sub > .55 and sustain > .25 and (r.high_rate >= 3 or subdivisions >= 2.2):
            family, label = 'crimson', 'hip-hop-like'
        elif (sync > .38 and (sub < .55 or r.note_motion > .65) and r.high_rate >= 2
              and subdivisions >= 2.3 and r.subdivision_lock >= .70
              and r.bass_lock >= .70 and r.offbeat >= .24 and r.bass_repeat >= .60):
            family, label = 'aurora', 'latin-like'
        elif bass_kick and scores['neon'][0] >= .65 and self.regularity > .55:
            family, label = 'neon', 'electronic-like'
        elif sub > .55 and sustain > .38:
            family, label = 'violet', 'soul-like'
        elif (r.note_motion > .55 and .13 < r.swing < .5 and sub < .55
              and r.swing_lock >= .60):
            family, label = 'gold', 'swing/funk-like'
        elif (self.regularity > .55 and subdivisions >= 1.6 and r.high_rate >= 2.2
              and r.brightness > .57 and sub < .5):
            family, label = 'sunset', 'bright dance-pop'
        elif self.regularity > .5 and r.high_rate >= 1.2 and sub < .65:
            family, label = 'blue', 'pop-like'
        else:
            return scores

        # Multiple repeating, broad-band percussion bars are stronger evidence
        # than a bass-only prior. All hue changes still use the existing dwell,
        # score margin, cooldown, and perceptual crossfade.
        adjusted = {key: (value*.65, text) for key, (value, text) in scores.items()}
        adjusted[family] = (max(adjusted.get(family, (0, ''))[0], .80+.14*r.percussion), label)
        return adjusted
