"""Local musical-pattern regressions, not real-song genre accuracy scores."""
from pathlib import Path
import math
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from style_score import style_score, vocal_score
from pulse_tui.colors import AdaptiveColors
from pulse_tui.palettes import PALETTE_LABS

EXPECTED = {'acoustic': 'warm', 'hip-hop': 'crimson', 'latin': 'aurora',
            'electronic': 'neon', 'pop': 'blue', 'swing': 'gold',
            'soul': 'violet', 'dance-pop': 'sunset', 'ambient': 'ice'}
REQUESTED = ('hip-hop', 'latin', 'electronic', 'pop')


def observe(style, fps=24, offset=0, volume=1, duration=26):
    colors = AdaptiveColors()
    for frame in range(fps*duration):
        now = frame/fps
        colors.update(style_score(now+.173, style)*volume, now+offset, 1/fps)
    return colors


class StyleTests(unittest.TestCase):
    def test_all_nine_families_are_reachable_from_musical_patterns(self):
        self.assertEqual(set(EXPECTED.values()), set(PALETTE_LABS))
        for style, family in EXPECTED.items():
            with self.subTest(style=style):
                self.assertEqual(observe(style).name, family)

    def test_four_requested_profiles_survive_rate_volume_and_clock_changes(self):
        for style in REQUESTED:
            for fps, offset, volume in ((12, 0, 1), (60, 0, 1), (24, 103.17, .35)):
                with self.subTest(style=style, fps=fps, offset=offset):
                    self.assertEqual(observe(style, fps, offset, volume).name, EXPECTED[style])

    def test_actual_cava_pcm_percussion_and_bass_mixtures(self):
        with np.load(ROOT/'tests/data/style_reference.npz') as reference:
            for style in REQUESTED:
                colors = AdaptiveColors()
                for now, frame in zip(reference[style+'_times'], reference[style+'_frames']):
                    colors.update(frame.astype(float)/255, float(now), 1/24)
                with self.subTest(style=style):
                    self.assertEqual(colors.name, EXPECTED[style])
                    self.assertTrue(colors.character.rhythm.ready)

    def test_requested_profiles_are_not_locked_to_one_tempo(self):
        for speed in (.7, 1.3):
            for style in REQUESTED:
                colors = AdaptiveColors()
                for frame in range(24*30):
                    now = frame/24
                    colors.update(style_score(now*speed, style), now, 1/24)
                self.assertEqual(colors.name, EXPECTED[style], (style, speed))

    def test_vocal_entrance_preserves_every_family_but_adds_expression(self):
        for style, family in EXPECTED.items():
            quiet, singing = AdaptiveColors(), AdaptiveColors()
            for frame in range(24*36):
                now = frame/24
                base = style_score(now, style)
                quiet.update(base, now, 1/24)
                singing.update(base + (vocal_score(now) if now >= 18 else 0), now, 1/24)
            with self.subTest(style=style):
                self.assertEqual(singing.name, family)
                self.assertTrue(np.array_equal(quiet.weights, singing.weights))
                self.assertGreater(singing.intensity, quiet.intensity)

    def test_repeating_percussion_can_change_family_with_identical_bass(self):
        # This deliberately differs from the voice-only test: upper-band musical
        # rhythm is allowed to move a pitched-bass pattern from Warm to Blue.
        colors = AdaptiveColors()
        for frame in range(24*48):
            now = frame/24
            spectrum = style_score(now, 'pop')
            if now < 20:
                spectrum[44:] = 0
            colors.update(spectrum, now, 1/24)
            if frame == 20*24-1:
                self.assertEqual(colors.name, 'warm')
        self.assertEqual(colors.name, 'blue')

    def test_unstructured_broad_speech_like_bursts_do_not_become_a_beat(self):
        for seed in range(4):
            attacks = np.cumsum(np.random.default_rng(seed).uniform(.10, .60, 200))
            colors = AdaptiveColors()
            for frame in range(24*30):
                now = frame/24
                spectrum = style_score(now, 'acoustic')
                previous = attacks[attacks <= now]
                age = now-previous[-1] if len(previous) else 99
                spectrum[44:] = .4*math.exp(-age*30)
                colors.update(spectrum, now, 1/24)
                self.assertEqual(colors.character.family, 'warm')

    def test_sustained_highs_narrow_harmonics_and_a_brief_fill_hold_warm(self):
        for variant in ('sustained', 'narrow', 'fill'):
            colors = AdaptiveColors()
            for frame in range(24*30):
                now = frame/24
                spectrum = style_score(now, 'acoustic')
                if variant == 'sustained':
                    spectrum[44:] = .25+.05*math.sin(now*2.7)
                elif variant == 'narrow':
                    spectrum[48:52] = .4*math.exp(-(now % .25)*30)
                elif 12 <= now < 14:
                    spectrum[44:] = .4*math.exp(-(now % .25)*30)
                colors.update(spectrum, now, 1/24)
                self.assertEqual(colors.character.family, 'warm', (variant, now))

    def test_track_changes_can_visit_four_families_and_return_warm_smoothly(self):
        colors = AdaptiveColors()
        previous = np.array(colors.palette())
        largest_step = 0
        for part, style in enumerate((*REQUESTED, 'acoustic')):
            for frame in range(24*28):
                now = frame/24
                colors.update(style_score(now, style), part*28+now, 1/24)
                current = np.array(colors.palette())
                largest_step = max(largest_step, int(np.abs(current-previous).max()))
                previous = current
            self.assertEqual(colors.name, EXPECTED[style])
        self.assertLessEqual(largest_step, 18)


if __name__ == '__main__':
    unittest.main()
