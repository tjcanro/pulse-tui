"""Stereo, advection, camera continuity, section cues, and native rendering."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from preview_score import stereo_score
from pulse_tui.audio import StereoFrames
from pulse_tui.camera import camera
from pulse_tui.director import MusicDirector
from pulse_tui.history import TerrainHistory
from pulse_tui.looks import LOOKS
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Pulse, Scene
from pulse_tui.settings import Options
from pulse_tui.terminal import handle_keys


def score_scene(seconds=24):
    scene = Scene()
    for frame in range(seconds * 24):
        now = frame / 24
        scene.update(stereo_score(now), now, 1 / 24)
    return scene


class CinematicTests(unittest.TestCase):
    def test_stereo_frame_fragmentation_and_left_bin_reversal(self):
        left, right = bytes(range(64)), bytes(range(64, 128))
        frame = left[::-1] + right
        decoder = StereoFrames()
        self.assertIsNone(decoder.feed(frame[:13]))
        decoded = decoder.feed(frame[13:] + frame + frame[:7])
        self.assertEqual(decoder.pending, bytearray(frame[:7]))
        self.assertTrue(np.allclose(decoded[0], np.arange(64) / 255))
        self.assertTrue(np.allclose(decoded[1], np.arange(64, 128) / 255))

    def test_mono_and_dual_mono_make_identical_scenes(self):
        mono, stereo = Scene(), Scene()
        for frame in range(100):
            values = stereo_score(frame / 24).mean(axis=0)
            mono.update(values, frame / 24, 1 / 24)
            stereo.update(np.stack((values, values)), frame / 24, 1 / 24)
        renderer = Renderer()
        options = Options()
        self.assertTrue(np.array_equal(renderer.dots(mono, 4.2, options, 100, 30),
                                       renderer.dots(stereo, 4.2, options, 100, 30)))

    def test_stereo_pulses_move_to_the_heard_side_and_can_be_disabled(self):
        left, right = Scene(), Scene()
        left.pulses = [Pulse(1, 0, 0, 1, 1, -1)]
        right.pulses = [Pulse(1, 0, 0, 1, 1, 1)]
        x, z = np.linspace(-10, 10, 201), np.zeros(201)
        options = Options(history=False, sections=False)
        left_height = left.surface(x, z, 1.12, 1, options)[1]
        right_height = right.surface(x, z, 1.12, 1, options)[1]
        self.assertLess(x[left_height.argmax()], -2)
        self.assertGreater(x[right_height.argmax()], 2)
        options.stereo = False
        self.assertTrue(np.array_equal(left.surface(x, z, 1.12, 1, options)[1],
                                       right.surface(x, z, 1.12, 1, options)[1]))

    def test_cinematic_pulse_ramps_in_without_an_instant_height_jump(self):
        scene, empty = Scene(), Scene()
        scene.pulses = [Pulse(1, 0, 0, 0, 1)]
        x, z = np.array([0.0]), np.array([0.0])
        options = Options(history=False, sections=False)
        initial = scene.surface(x, z, 1, 1, options)[1]
        baseline = empty.surface(x, z, 1, 1, options)[1]
        self.assertTrue(np.array_equal(initial, baseline))
        self.assertGreater(scene.surface(x, z, 1.08, 1, options)[1][0], initial[0])

    def test_history_remembers_old_sound_and_advects_without_row_steps(self):
        history = TerrainHistory()
        for frame in range(8 * 24):
            now = frame / 24
            history.update(np.full((2, 64), .8 if now < 2 else 0), now, 1 / 24)
        x = np.array([0.0])
        position = 1 - (8 - 1.4) * 1.9
        old = history.sample(x, np.array([position]), 8)[0]
        present = history.sample(x, np.array([0.0]), 8)[0]
        following = history.sample(x, np.array([position - 1.9 / 24]), 8 + 1 / 24)[0]
        self.assertGreater(old, .3)
        self.assertLess(present, .001)
        self.assertAlmostEqual(old, following, delta=.005)
        for frame in range(8 * 24, 45 * 24):
            history.update(np.zeros((2, 64)), frame / 24, 1 / 24)
        self.assertLessEqual(len(history.times), 192)

    def test_camera_is_continuous_across_build_release_and_calm(self):
        scene, options = Scene(), Options()
        eyes, releases = [], []
        for frame in range(32 * 24):
            now = frame / 24
            scene.update(stereo_score(now), now, 1 / 24)
            eye = camera(now, options, scene.director)[0]
            self.assertTrue(np.all(np.isfinite(eye)))
            self.assertGreaterEqual(eye[1], 2.7)
            eyes.append(eye)
            releases.extend(scene.director.releases)
        maximum = np.linalg.norm(np.diff(eyes, axis=0), axis=1).max()
        self.assertLess(maximum, .10, maximum)
        self.assertTrue(any(13 <= when <= 17 for when, _ in releases))

    def test_steady_sound_does_not_invent_releases_and_silence_relaxes_camera(self):
        director = MusicDirector()
        for frame in range(20 * 24):
            director.update(np.full((2, 64), .4), frame / 24, 1 / 24, .8)
        self.assertFalse(director.releases)
        active = director.intensity
        for frame in range(20 * 24, 30 * 24):
            director.update(np.zeros((2, 64)), frame / 24, 1 / 24, .8)
        self.assertLess(director.intensity, active / 10)

    def test_crest_highlights_preserve_visible_geometry(self):
        scene = score_scene(24)
        renderer, options = Renderer(), Options()
        accented = renderer.dots(scene, 24, options, 120, 36)
        options.highlights = False
        plain = renderer.dots(scene, 24, options, 120, 36)
        self.assertTrue(np.array_equal(accented >= 0, plain >= 0))
        self.assertGreater(accented.max(), plain.max())
        self.assertGreater(accented.max(), 1)

    def test_all_looks_controls_pause_and_native_numpy_parity(self):
        scene, native, portable = score_scene(24), Renderer(), Renderer(use_native=False)
        for name in LOOKS:
            options = Options.for_look(name)
            a = native.dots(scene, 24, options, 100, 30)
            b = portable.dots(scene, 24, options, 100, 30)
            self.assertLessEqual(np.count_nonzero((a >= 0) != (b >= 0)), 4)
            shared = (a >= 0) & (b >= 0)
            self.assertTrue(np.allclose(a[shared], b[shared]))
            options.paused = True
            frame = native.frame(scene, 24, options, 100, 30, 'TEST', 24)
            self.assertEqual(frame, native.frame(scene, 24, options, 100, 30, 'TEST', 24))
        options = Options()
        for expected in list(LOOKS)[1:] + ['cinematic']:
            handle_keys('v', options, scene, 24)
            self.assertEqual(options.look, expected)
            self.assertEqual(options.palette, LOOKS[expected].palette)


if __name__ == '__main__':
    unittest.main()
