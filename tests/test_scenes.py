"""Geometry behavior, scene controls, and native/portable scene parity."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts')]
from preview_score import stereo_score
from pulse_tui.camera import camera
from pulse_tui.curves import frame, spline, tangents, transported_normals
from pulse_tui.geometry import pulse_field
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Pulse, Scene
from pulse_tui.settings import CAMERAS, Options, SCENES
from pulse_tui.spatial import SpatialScenes
from pulse_tui.terminal import handle_keys


def prepared():
    scene = Scene()
    for frame in range(18*24):
        scene.update(stereo_score(frame/24), frame/24, 1/24)
    return scene


class SceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = prepared()

    def test_scene_keys_wrap_both_ways_and_keep_other_controls(self):
        options = Options(camera='fixed', palette='neon', density=1.5, gain=1.1, paused=True)
        before = vars(options).copy()
        for expected in (*SCENES[1:], 'terrain'):
            handle_keys('s', options, self.audio, 18)
            self.assertEqual(options.scene, expected)
            self.assertEqual({k:v for k,v in vars(options).items() if k!='scene'},
                             {k:v for k,v in before.items() if k!='scene'})
        handle_keys('S', options, self.audio, 18)
        self.assertEqual(options.scene, 'filaments')
        handle_keys('v', options, self.audio, 18)
        self.assertEqual(options.scene, 'filaments')

    def test_cli_lists_all_scenes_and_rejects_unknown_scene_before_audio(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'))
        command = [sys.executable, '-m', 'pulse_tui']
        help_result = subprocess.run([*command, '--help'], env=env, capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        for name in SCENES:
            self.assertIn(name, help_result.stdout)
        result = subprocess.run([*command, '--scene', 'unknown'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)

    def test_geometry_is_finite_and_density_adds_real_detail(self):
        provider = SpatialScenes()
        for name in SCENES[1:]:
            counts = []
            for density in (.5, 2, 4):
                geometry = provider.evaluate(self.audio, 18, Options(scene=name, density=density))
                self.assertTrue(np.isfinite(geometry.vertices).all())
                self.assertTrue(np.isfinite(geometry.heat).all())
                self.assertEqual(geometry.vertices.shape, (len(geometry.heat), 3))
                self.assertEqual(geometry.edges.shape[1], 2)
                self.assertEqual(geometry.faces.shape[1], 3)
                for indices in (geometry.edges, geometry.faces):
                    self.assertTrue(indices.flags.c_contiguous)
                    if indices.size:
                        self.assertGreaterEqual(indices.min(), 0)
                        self.assertLess(indices.max(), len(geometry.vertices))
                counts.append(len(geometry.edges))
            self.assertTrue(counts[0]<counts[1]<counts[2], (name, counts))
            self.assertLess(len(geometry.vertices), 40000)

    def test_curved_frames_keep_width_through_turns_without_flipping(self):
        from pulse_tui.ribbons import PATHS
        paths = np.array([spline(np.array(path, dtype=float), np.linspace(0,1,180)) for path in PATHS])
        reference = transported_normals(paths)
        normal, binormal = frame(paths, reference)
        tangent = tangents(paths)
        self.assertTrue(np.allclose(np.linalg.norm(normal, axis=-1), 1))
        self.assertTrue(np.allclose(np.linalg.norm(binormal, axis=-1), 1))
        self.assertLess(np.abs(np.sum(normal*tangent, axis=-1)).max(), 1e-8)
        deformed = paths.copy()
        deformed[..., 2] += .02*np.sin(np.linspace(0,6,180))
        following, _ = frame(deformed, reference)
        self.assertGreater(np.sum(normal*following, axis=-1).min(), .99)

    def test_ribbons_loop_back_and_current_has_a_sweeping_spatial_bend(self):
        provider = SpatialScenes()
        geometry = provider.evaluate(self.audio, 18, Options(scene='ribbons'))
        model = provider.model
        body = geometry.vertices[:model.count*model.length*model.width]
        centers = body.reshape(model.count, model.length, model.width, 3).mean(axis=2)
        # The old x-monotone sine waves could never turn back through depth.
        direction = np.diff(centers[0, :, 0])
        self.assertLess(direction.min(), -.05)
        self.assertGreater(direction.max(), .05)
        self.assertGreater(np.ptp(centers[..., 2]), 15)
        geometry = provider.evaluate(self.audio, 18, Options(scene='filaments'))
        model = provider.model
        main = geometry.vertices.reshape(model.count, model.length, 3)[model.group==0]
        heat = geometry.heat.reshape(model.count, model.length)[model.group==0]
        step = np.diff(main, axis=1)
        visible = (heat[:,:-1]>=0)&(heat[:,1:]>=0)
        self.assertLess(step[...,0][visible].min(), -.05)
        self.assertGreater(np.ptp(main[...,1][heat>=0]), 25)

    def test_ribbon_frame_follows_a_right_angle_without_a_roll_flip(self):
        parameter = np.linspace(0,1,20)[None,:,None]
        rest = np.broadcast_to([1.,0,0],(1,20,3))
        reference = np.broadcast_to([0.,1,0],(1,20,3))
        previous = None
        for angle in np.linspace(np.deg2rad(80),np.deg2rad(100),9):
            direction = np.array([np.cos(angle),np.sin(angle),0])
            normal, binormal = frame(parameter*direction, reference, rest_tangent=rest)
            self.assertTrue(np.allclose(np.linalg.norm(normal,axis=-1),1))
            self.assertTrue(np.allclose(np.linalg.norm(binormal,axis=-1),1))
            self.assertLess(np.abs(np.sum(normal*direction,axis=-1)).max(),1e-8)
            if previous is not None:
                self.assertGreater(np.sum(normal*previous,axis=-1).min(),.99)
            previous = normal

    def test_material_flows_forward_between_beats_with_a_fixed_camera(self):
        for name in ('ribbons','filaments'):
            audio, provider = Scene(), SpatialScenes()
            options = Options(scene=name, camera='fixed')
            a = provider.evaluate(audio, 4, options)
            b = provider.evaluate(audio, 4.5, options)
            model = provider.model
            if name=='ribbons':
                count = model.count*model.length*model.width
                shape = (model.count,model.length,model.width,3)
                before, after = a.vertices[:count].reshape(shape), b.vertices[:count].reshape(shape)
                visible = ((a.heat[:count]>=0)&(b.heat[:count]>=0)).reshape(shape[:-1])[:,1:-1]
            else:
                shape = (model.count,model.length,3)
                before, after = a.vertices.reshape(shape), b.vertices.reshape(shape)
                visible = ((a.heat>=0)&(b.heat>=0)).reshape(shape[:-1])[:,1:-1]
            tangent = before[:,2:]-before[:,:-2]
            movement = (after-before)[:,1:-1]
            distance = np.linalg.norm(movement, axis=-1)
            alignment = np.sum(movement*tangent,axis=-1)/np.maximum(1e-9,distance*np.linalg.norm(tangent,axis=-1))
            self.assertGreater(np.median(distance[visible]), .8, name)
            self.assertGreater(np.median(alignment[visible]), .75, name)

    def test_ribbon_width_varies_along_and_between_bands(self):
        provider = SpatialScenes()
        geometry = provider.evaluate(Scene(), 8, Options(scene='ribbons'))
        model = provider.model
        count = model.count*model.length*model.width
        body = geometry.vertices[:count].reshape(model.count,model.length,model.width,3)
        heat = geometry.heat[:count].reshape(model.count,model.length,model.width)
        widths = np.linalg.norm(body[:,:,-1]-body[:,:,0],axis=-1)
        means = []
        for width, ink in zip(widths, heat):
            visible = width[(ink[:,0]>0)&(ink[:,-1]>0)]
            self.assertGreater(np.percentile(visible,95)/np.percentile(visible,5), 3.5)
            means.append(np.mean(visible))
        self.assertGreater(max(means)/min(means), 3)

    def test_interwoven_ribbons_alternate_front_and_back_at_crossings(self):
        from pulse_tui.ribbons import Ribbons
        model = Ribbons(2)
        parameter = np.broadcast_to(np.linspace(.08,.92,300),(model.count,300))
        for now in (0,8,18):
            centers = model.centerlines(parameter, now)
            difference = centers[2]-centers[4]
            crossing = np.flatnonzero(difference[:-1,1]*difference[1:,1]<0)
            self.assertGreaterEqual(len(crossing), 4)
            depths = difference[crossing,2]
            self.assertTrue(np.all(np.abs(depths)>1))
            self.assertTrue(np.all(depths[:-1]*depths[1:]<0))

    def test_flowing_material_recycles_only_while_hidden(self):
        for name in ('ribbons','filaments'):
            audio, provider = Scene(), SpatialScenes()
            options = Options(scene=name, density=.5, camera='fixed')
            before = provider.evaluate(audio, 0, options)
            resets = 0
            for step in range(1,241):
                after = provider.evaluate(audio, step/10, options)
                jumped = np.linalg.norm(after.vertices-before.vertices,axis=1)>15
                if jumped.any():
                    resets += 1
                    self.assertTrue(np.all(before.heat[jumped]<0), name)
                    self.assertTrue(np.all(after.heat[jumped]<0), name)
                # Wrapped rails must not draw a long chord through the scene.
                ends = after.vertices[after.edges]
                long = np.linalg.norm(ends[:,0]-ends[:,1],axis=-1)>20
                self.assertTrue(np.all(after.heat[after.edges[long]]<0), name)
                before = after
            self.assertGreater(resets, 5, name)

    def test_each_scene_responds_to_audio_and_manual_pulses(self):
        quiet, loud = Scene(), Scene()
        for frame in range(24):
            loud.update(np.full(64, .6), frame/24, 1/24)
        for name in SCENES[1:]:
            options = Options(scene=name)
            provider = SpatialScenes()
            a = provider.evaluate(quiet, 1, options)
            b = provider.evaluate(loud, 1, options)
            self.assertGreater(np.max(np.abs(a.vertices-b.vertices)), .1, name)
            self.assertGreater(np.max(b.heat-a.heat), .1, name)
            baseline = provider.evaluate(quiet, 1.25, options).heat
            for band in range(3):
                quiet.pulses = [Pulse(1, 0, 0, band, 1)]
                struck = provider.evaluate(quiet, 1.25, options).heat
                self.assertGreater(np.max(struck-baseline), .1, (name,band))
                quiet.pulses = []

    def test_density_and_scene_switches_rebuild_only_one_cached_model(self):
        provider = SpatialScenes()
        options = Options(scene='ribbons')
        first = provider.evaluate(self.audio, 18, options)
        model = provider.model
        provider.evaluate(self.audio, 19, options)
        self.assertIs(provider.model, model)
        options.scene = 'orbit'
        provider.evaluate(self.audio, 19, options)
        self.assertIsNot(provider.model, model)
        options.scene = 'ribbons'
        again = provider.evaluate(self.audio, 18, options)
        self.assertTrue(np.array_equal(first.vertices, again.vertices))
        self.assertTrue(np.array_equal(first.heat, again.heat))

    def test_orbit_pulse_front_moves_from_center_to_margins(self):
        audio = Scene()
        audio.pulses = [Pulse(1, 0, 0, 0, 1)]
        radius = np.linspace(0, 18, 500)
        early = radius[pulse_field(audio, 1.2, radius, 6, band=0).argmax()]
        later = radius[pulse_field(audio, 2.6, radius, 6, band=0).argmax()]
        self.assertLess(early, 2)
        self.assertGreater(later, 9)

    def test_orbit_keeps_a_dense_center_and_reaches_the_outer_frame(self):
        dots = Renderer().dots(self.audio, 18, Options(scene='orbit'), 160, 48)
        y, x = np.mgrid[:dots.shape[0], :dots.shape[1]]
        radius = np.hypot(x-dots.shape[1]/2, y-dots.shape[0]/2)/dots.shape[0]
        center = np.mean(dots[radius<.2]>=0)
        outside = np.mean(dots[(radius>.4)&(radius<.7)]>=0)
        self.assertGreater(center, outside*2)
        occupied = np.argwhere(dots>=0)
        self.assertLess(occupied[:, 1].min(), dots.shape[1]*.15)
        self.assertGreater(occupied[:, 1].max(), dots.shape[1]*.85)

    def test_orbit_fragment_resets_are_invisible(self):
        provider, audio, options = SpatialScenes(), Scene(), Options(scene='orbit')
        before = provider.evaluate(audio, 0, options)
        resets = 0
        for frame in range(1, 24*15):
            after = provider.evaluate(audio, frame/24, options)
            jumped = np.linalg.norm(after.vertices-before.vertices, axis=1)>5
            if jumped.any():
                resets += 1
                self.assertTrue(np.all(before.heat[jumped]<0))
                self.assertTrue(np.all(after.heat[jumped]<0))
            before = after
        self.assertGreater(resets, 10)

    def test_camera_and_visible_geometry_move_continuously(self):
        provider = SpatialScenes()
        for name in SCENES[1:]:
            options = Options(scene=name)
            a = provider.evaluate(self.audio, 18, options)
            b = provider.evaluate(self.audio, 18+1/24, options)
            visible = (a.heat>=0)&(b.heat>=0)
            distance = np.linalg.norm(b.vertices[visible]-a.vertices[visible], axis=1)
            self.assertLess(distance.max(), .5, name)
            eye = camera(18, options, self.audio.director)[0]
            next_eye = camera(18+1/24, options, self.audio.director)[0]
            self.assertLess(np.linalg.norm(next_eye-eye), .1)

    def test_all_cameras_and_scene_switches_render_and_pause_is_exact(self):
        renderer = Renderer()
        for name in (*SCENES, 'terrain'):
            for view in CAMERAS:
                options = Options(scene=name, camera=view, paused=True)
                frame = renderer.frame(self.audio, 18, options, 100, 30, 'TEST', 24)
                self.assertEqual(len(frame), 30)
                self.assertEqual(frame, renderer.frame(self.audio, 18, options, 100, 30, 'TEST', 24))
                self.assertGreater(sum(0x2800<=ord(c)<=0x28ff for line in frame for c in line), 20)

    def test_new_scenes_keep_native_and_portable_parity(self):
        native, portable = Renderer(), Renderer(use_native=False)
        for name in SCENES[1:]:
            for view in ('choreo', 'orbit', 'overhead'):
                options = Options(scene=name, camera=view, density=1)
                a = native.dots(self.audio, 18, options, 100, 30)
                b = portable.dots(self.audio, 18, options, 100, 30)
                self.assertLessEqual(np.count_nonzero((a>=0)!=(b>=0)), 8, (name,view))
                shared = (a>=0)&(b>=0)
                self.assertTrue(np.allclose(a[shared], b[shared], atol=1e-8), (name,view))


if __name__ == '__main__':
    unittest.main()
