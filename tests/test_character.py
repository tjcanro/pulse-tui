"""Controlled audio-feature behaviors; these tests do not measure genre accuracy."""
from pathlib import Path
import math
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from character_score import character_score
from style_score import vocal_score
from pulse_tui.colors import AdaptiveColors
from pulse_tui.palettes import PALETTE_LABS, PRESET_RGB, expressive_labs, lab_to_rgb
from pulse_tui.settings import PALETTES


def observe(kind, lively=0, fps=24):
    colors = AdaptiveColors()
    for frame in range(30 * fps):
        now = frame / fps
        # A voice-only fixture: the old "lively" score also added repeating
        # broad hi-hats, which are now explicitly allowed to inform character.
        colors.update(character_score(now, kind) + vocal_score(now, lively), now, 1/fps)
    return colors


class CharacterTests(unittest.TestCase):
    def test_same_tempo_distinct_bass_timbres(self):
        rounded, driving = observe('rounded'), observe('driving')
        self.assertEqual(rounded.name, 'warm')
        self.assertEqual(driving.name, 'neon')
        self.assertAlmostEqual(rounded.onset_rate, driving.onset_rate, delta=.15)
        self.assertGreater(driving.character.spread, rounded.character.spread + .25)

    def test_actual_cava_output_for_pitched_tone_and_descending_kick(self):
        # Procedurally generated PCM, analyzed by the real CAVA binary. These
        # fixtures catch differences that idealized spectra do not reproduce.
        reference = np.load(ROOT/'tests/data/bass_reference.npz')
        for kind, expected in [('rounded', 'warm'), ('driving', 'neon')]:
            colors = AdaptiveColors()
            for now, frame in zip(reference[kind+'_times'], reference[kind+'_frames']):
                colors.update(frame.astype(float)/255, float(now), 1/24)
            self.assertEqual(colors.name, expected)
            self.assertGreater(colors.character.pulse, .7)

    def test_real_cava_reference_can_transition_back_from_neon_to_warm(self):
        reference = np.load(ROOT/'tests/data/bass_reference.npz')
        colors = AdaptiveColors()
        for offset, kind in [(0, 'driving'), (14, 'rounded')]:
            for now, frame in zip(reference[kind+'_times'], reference[kind+'_frames']):
                colors.update(frame.astype(float)/255, float(now)+offset, 1/24)
        self.assertEqual(colors.name, 'warm')

    def test_vocals_change_expression_without_changing_character(self):
        for kind in ('rounded', 'driving'):
            quiet, lively = observe(kind), observe(kind, lively=1)
            self.assertEqual(quiet.name, lively.name)
            self.assertTrue(np.array_equal(quiet.weights, lively.weights))
            self.assertEqual(quiet.character.label, lively.character.label)
            self.assertGreater(lively.intensity, quiet.intensity)
            delta = np.abs(np.array(lively.palette()) - np.array(quiet.palette()))
            self.assertGreater(delta.max(), 12)

    def test_quiet_bass_family_is_not_gated_by_vocal_loudness(self):
        alone, voice = AdaptiveColors(), AdaptiveColors()
        for frame in range(24*20):
            now = frame/24
            bass = character_score(now, 'driving') * .12
            singing = bass.copy()
            singing[18:50] = .6 * math.exp(-(now % .25)*10)
            alone.update(bass, now, 1/24)
            voice.update(singing, now, 1/24)
        self.assertTrue(np.array_equal(alone.weights, voice.weights))

    def test_consistency_across_frame_rates(self):
        for fps in (12, 24, 60):
            self.assertEqual(observe('rounded', fps=fps).name, 'warm')
            self.assertEqual(observe('driving', fps=fps).name, 'neon')

    def test_all_nine_themes_have_distinct_quiet_and_lively_gradients(self):
        self.assertEqual(set(PALETTES)-{'auto', 'cycle'}, set(PALETTE_LABS))
        self.assertEqual(len(PALETTE_LABS), 9)
        for name in PALETTE_LABS:
            quiet = np.array([lab_to_rgb(lab) for lab in expressive_labs(name, 0)])
            lively = np.array([lab_to_rgb(lab) for lab in expressive_labs(name, 1)])
            self.assertTrue(np.all((quiet >= 0) & (quiet <= 255)))
            self.assertTrue(np.all((lively >= 0) & (lively <= 255)))
            self.assertGreater(np.abs(lively-quiet).max(), 45)

    def test_a_brief_bass_change_does_not_flip_the_family(self):
        colors = observe('rounded')
        for frame in range(24):
            now = 30 + frame/24
            colors.update(character_score(now, 'driving'), now, 1/24)
        self.assertEqual(colors.name, 'warm')

    def test_assessment_between_short_kicks_does_not_lock_warm(self):
        colors = AdaptiveColors()
        bins = np.linspace(0, 1, 64)
        shape = np.exp(-((bins-.12)/.15)**2)
        shape[12:] = 0
        for frame in range(24*25):
            now = frame/24
            # Every assessment at n*.5 lands in the near-silent gap. Kicks
            # arrive one frame later, a valid 120-BPM input phase.
            spectrum = shape*.8*math.exp(-((now-1/24) % .5)*35)
            colors.update(spectrum, now, 1/24)
        self.assertEqual(colors.name, 'neon')
        self.assertGreater(colors.character.pulse, .8)

    def test_compressed_broad_pulse_does_not_need_large_level_changes(self):
        colors = AdaptiveColors()
        bins = np.linspace(0, 1, 64)
        shape = np.exp(-((bins-.12)/.15)**2)
        shape[12:] = 0
        for frame in range(24*25):
            now = frame/24
            colors.update(shape*(.28+.045*math.cos(2*math.pi*2*now)), now, 1/24)
        self.assertEqual(colors.name, 'neon')
        self.assertLess(colors.character.contrast, .3)

    def test_real_cava_kick_remains_detectable_over_sustained_bass(self):
        reference = np.load(ROOT/'tests/data/bass_reference.npz')
        kick = reference['driving_frames'].astype(float)/255
        bed = np.median(reference['rounded_frames'].astype(float)/255, axis=0)
        colors = AdaptiveColors()
        for frame in range(24*30):
            colors.update(.65*bed + .25*kick[frame % len(kick)], frame/24, 1/24)
        self.assertEqual(colors.name, 'neon')

    def test_actual_cava_output_for_a_quiet_kick_in_a_full_mix(self):
        reference = np.load(ROOT/'tests/data/mixed_bass_reference.npz')
        colors = AdaptiveColors()
        for now, frame in zip(reference['times'], reference['frames']):
            colors.update(frame.astype(float)/255, float(now), 1/24)
        self.assertEqual(colors.name, 'neon')
        self.assertLess(colors.character.contrast, .2)

    def test_response_control_increases_range_and_steps_remain_bounded(self):
        gentle, vivid = AdaptiveColors(.5), AdaptiveColors(2)
        previous = np.array(vivid.palette())
        largest = 0
        for frame in range(30 * 24):
            now = frame/24
            lively = 0 if now < 15 else 1
            spectrum = character_score(now, 'rounded', lively)
            gentle.update(spectrum, now, 1/24)
            vivid.update(spectrum, now, 1/24)
            current = np.array(vivid.palette())
            largest = max(largest, np.abs(current-previous).max())
            previous = current
        self.assertLessEqual(largest, 18)
        self.assertGreater(vivid.intensity, gentle.intensity)
        self.assertEqual(vivid.name, gentle.name)


if __name__ == '__main__':
    unittest.main()
