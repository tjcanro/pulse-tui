"""Continuous cycling through every family, independent of classifier/audio."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pulse_tui.colors import AdaptiveColors
from pulse_tui.palettes import CYCLE_ORDER, PALETTE_LABS, expressive_labs, lab_to_rgb
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options


class CycleTests(unittest.TestCase):
    def test_every_palette_is_visited_and_the_loop_closes_without_audio(self):
        colors = AdaptiveColors(cycle_seconds=14)
        self.assertEqual(set(CYCLE_ORDER), set(PALETTE_LABS))
        for i, family in enumerate(CYCLE_ORDER):
            expected = tuple(lab_to_rgb(lab) for lab in expressive_labs(family, .35))
            self.assertEqual(colors.palette('cycle', i*14), expected)
        self.assertEqual(colors.palette('cycle', 0), colors.palette('cycle', 14*len(CYCLE_ORDER)))

    def test_gradual_transitions_and_no_boundary_jump(self):
        default = AdaptiveColors()
        frames = np.array([default.palette('cycle', i/24) for i in range(14*9*24+1)])
        self.assertLessEqual(np.max(np.abs(np.diff(frames, axis=0))), 5)
        colors = AdaptiveColors(cycle_seconds=2)
        frames = np.array([colors.palette('cycle', i/24) for i in range(2*9*24+1)])
        self.assertLess(np.max(np.abs(np.diff(frames, axis=0))), 24)
        for boundary in range(1, 10):
            before = np.array(colors.palette('cycle', boundary*2-.001))
            after = np.array(colors.palette('cycle', boundary*2+.001))
            self.assertLessEqual(np.abs(after-before).max(), 1)

    def test_pause_freezes_cycle_and_fresh_audio_is_not_required(self):
        scene = Scene(cycle_seconds=3)
        options = Options(palette='cycle', paused=True)
        renderer = Renderer()
        first = renderer.frame(scene, 1, options, 80, 24, 'TEST', 24)
        self.assertEqual(first, renderer.frame(scene, 1, options, 80, 24, 'TEST', 24))
        self.assertNotEqual(scene.colors.palette('cycle', 1), scene.colors.palette('cycle', 4))

    def test_speed_is_configurable_and_cli_rejects_invalid_values(self):
        fast, slow = AdaptiveColors(cycle_seconds=7), AdaptiveColors(cycle_seconds=14)
        self.assertEqual(fast.palette('cycle', 7), slow.palette('cycle', 14))
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'))
        result = subprocess.run([sys.executable, '-m', 'pulse_tui', '--cycle-seconds', '0'],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cycle seconds 2–120', result.stderr)


if __name__ == '__main__':
    unittest.main()
