"""Behavioral tests for sound-driven palettes; fixtures are not a runtime mode."""
from pathlib import Path
import math
import os
import subprocess
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pulse_tui.colors import AdaptiveColors, PRESET_RGB, lab_to_rgb
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options, PALETTES
from pulse_tui.terminal import handle_keys


def spectrum_at(now, rate, volume=1):
    """Same spectral shape at every rate: only the temporal envelope changes."""
    positions = np.linspace(0, 1, 64)
    shape = np.exp(-((positions - .15) / .15) ** 2) + .35 * np.exp(-((positions - .7) / .25) ** 2)
    attack = math.exp(-(now % (1 / rate)) * 20) if rate else .4
    return shape * (.10 + .7 * attack) * volume


def observe(rate, fps=24, volume=1, duration=30):
    colors = AdaptiveColors()
    for frame in range(int(fps * duration)):
        now = frame / fps
        colors.update(spectrum_at(now, rate, volume), now, 1 / fps)
    return colors


class ColorTests(unittest.TestCase):
    def test_color_conversion_reference_primaries_and_neutrals(self):
        for lab, expected in [((0, 0, 0), (0, 0, 0)), ((1, 0, 0), (255, 255, 255)),
                              ((.62795536, .22486306, .1258463), (255, 0, 0)),
                              ((.45201372, -.03245698, -.31152815), (0, 0, 255))]:
            self.assertTrue(np.allclose(lab_to_rgb(lab), expected, atol=1))

    def test_slow_and_driving_broad_bass_patterns(self):
        for rate, expected in [(.8, 'warm'), (2, 'neon'), (4, 'neon')]:
            colors = observe(rate)
            self.assertEqual(colors.name, expected)
            self.assertGreater(colors.weights[('warm', 'blue', 'neon').index(expected)], .7)
            self.assertAlmostEqual(colors.onset_rate, rate, delta=.15)
            self.assertAlmostEqual(float(colors.weights.sum()), 1)

    def test_loud_sustained_sound_does_not_imply_a_fast_rhythm(self):
        colors = observe(0)
        self.assertNotEqual(colors.name, 'neon')
        self.assertEqual(colors.onset_rate, 0)

    def test_vocal_entrance_changes_intensity_not_the_bass_palette(self):
        accompaniment, singing = AdaptiveColors(), AdaptiveColors()
        for frame in range(24 * 35):
            now = frame / 24
            bass = spectrum_at(now, .8)
            bass[12:] = 0
            vocal = np.zeros(64)
            if now > 15:
                vocal[17:50] = .35 + .45 * math.exp(-(now % .25) * 14)
            accompaniment.update(bass, now, 1 / 24)
            singing.update(np.clip(bass + vocal, 0, 1), now, 1 / 24)
        self.assertEqual(singing.name, 'warm')
        self.assertTrue(np.array_equal(singing.weights, accompaniment.weights))
        self.assertGreater(singing.intensity, accompaniment.intensity)
        self.assertNotEqual(singing.palette(), accompaniment.palette())
        self.assertTrue(all(red > green and red > blue for red, green, blue in singing.palette()))

    def test_no_bass_holds_hue_even_with_fast_mids_and_highs(self):
        colors = observe(.8)
        weights = colors.weights.copy()
        for frame in range(24 * 12):
            spectrum = spectrum_at(frame / 24, 4)
            spectrum[:12] = 0
            colors.update(spectrum, 30 + frame / 24, 1 / 24)
        self.assertTrue(np.array_equal(weights, colors.weights))
        self.assertEqual(colors.name, 'warm')

    def test_relative_features_resist_volume_changes(self):
        for rate in (.8, 2, 4):
            quiet, loud = observe(rate, volume=.35), observe(rate, volume=1)
            self.assertEqual(quiet.name, loud.name)
            self.assertTrue(np.allclose(quiet.weights, loud.weights, atol=.03))

    def test_similar_result_at_different_frame_rates(self):
        for rate, expected in [(.8, 'warm'), (2, 'neon'), (4, 'neon')]:
            for fps in (12, 24, 60):
                self.assertEqual(observe(rate, fps=fps).name, expected)

    def test_frequency_balance_contributes_without_inventing_attacks(self):
        dark, bright = AdaptiveColors(), AdaptiveColors()
        for frame in range(24 * 12):
            dark.update(np.r_[np.full(17, .5), np.zeros(47)], frame / 24, 1 / 24)
            bright.update(np.r_[np.zeros(44), np.full(20, .5)], frame / 24, 1 / 24)
        self.assertGreater(bright.brightness, dark.brightness)
        self.assertEqual(dark.onset_rate, 0)
        self.assertEqual(bright.onset_rate, 0)

    def test_transitions_are_gradual_and_eventually_follow_new_track(self):
        colors = observe(.8, duration=20)
        before = np.array(colors.palette())
        largest_step = 0
        for frame in range(24 * 24):
            now = 20 + frame / 24
            colors.update(spectrum_at(now, 4), now, 1 / 24)
            after = np.array(colors.palette())
            largest_step = max(largest_step, np.abs(after - before).max())
            before = after
        self.assertEqual(colors.name, 'neon')
        self.assertLessEqual(largest_step, 24)

    def test_silence_holds_last_palette_and_cannot_add_attacks(self):
        colors = observe(4)
        before, weights = colors.palette(), colors.weights.copy()
        for frame in range(24 * 20):
            colors.update(np.zeros(64), 30 + frame / 24, 1 / 24)
        self.assertEqual(colors.palette(), before)
        self.assertTrue(np.array_equal(colors.weights, weights))
        self.assertEqual(len(colors._attacks), 0)
        silent = AdaptiveColors()
        for frame in range(24 * 10):
            silent.update(np.zeros(64), frame / 24, 1 / 24)
        self.assertEqual(silent.name, 'warm')
        self.assertEqual(len(silent._attacks), 0)

    def test_modes_gamut_and_repeated_render_do_not_mutate_palette(self):
        scene = Scene()
        renderer = Renderer()
        options = Options()
        for name in PALETTES:
            palette = scene.colors.palette(name)
            self.assertEqual(len(palette), 12)
            self.assertTrue(all(isinstance(v, int) and 0 <= v <= 255 for rgb in palette for v in rgb))
        original = scene.colors.palette()
        for expected in (*PALETTES[1:], 'auto'):
            handle_keys('p', options, scene, 1)
            self.assertEqual(options.palette, expected)
        options.paused = True
        one = renderer.frame(scene, 1, options, 80, 24, 'TEST', 24)
        two = renderer.frame(scene, 1, options, 80, 24, 'TEST', 24)
        self.assertEqual(one, two)
        self.assertEqual(scene.colors.palette(), original)
        self.assertEqual(scene.colors.palette('neon'), PRESET_RGB['neon'])

    def test_palette_cli_help_and_invalid_value(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        command = [sys.executable, '-m', 'pulse_tui']
        result = subprocess.run([*command, '--help'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--palette', result.stdout)
        for family in PALETTES:
            self.assertIn(family, result.stdout)
        result = subprocess.run([*command, '--palette', 'unknown'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)


if __name__ == '__main__':
    unittest.main()
