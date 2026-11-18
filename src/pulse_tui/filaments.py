"""Sweeping spatial fiber bundles with an S-bend, eddies, and sparse outliers."""
import numpy as np

from .curves import fade_ends, frame, spline, transported_normals
from .geometry import audio_sample, finish, pulse_field, strips
from .looks import LOOKS


PATHS = (
    ((-33,-17,8),(-19,-10,6),(-3,-6,3),(10,-1,0),(1,4,-2),
     (-2,8,-5),(6,13,-9),(30,21,-14)),
    ((-33,13,3),(-17,11,5),(-5,4,7),(8,-3,7),(22,-2,2),(37,8,-9)),
    ((-34,-12,11),(-17,-7,10),(-1,-9,8),(17,-8,4),(27,0,-3),(42,13,-12)),
)


class Filaments:
    def __init__(self, density):
        self.count = max(32, round(84*np.sqrt(density)))
        self.length = round(112*np.sqrt(density))+1
        self.s = np.linspace(0, 1, self.length)
        self.paths = tuple(np.array(path, dtype=float) for path in PATHS)
        self.normals = transported_normals(np.array([spline(path, self.s) for path in self.paths]))
        rng = np.random.default_rng(991)
        self.offset = np.clip(rng.normal(0, 1, (self.count, 2)), -2.8, 2.8)
        self.seed = rng.uniform(0, 1, (self.count, 4))
        self.flow = (.039+.015*self.seed[:, 1])[:,None]
        self.span = (.44+.24*self.seed[:, 2])[:,None]
        group = np.arange(self.count) % 10
        self.group = np.where(group<7, 0, np.where(group<9, 1, 2))
        self.edges, self.faces = strips(self.count, self.length, 1)

    def evaluate(self, audio, now, options):
        style = LOOKS[options.look]
        t = now*style.speed
        bass, mid, high = audio.levels*options.gain
        material = self.s[None,:]
        s = (material*self.span+t*self.flow+self.seed[:, 3,None]) % 1
        center = np.empty((self.count,self.length,3))
        for i, path in enumerate(self.paths):
            knots = path.copy()
            phase = np.arange(len(path))*.7+i*1.5
            knots[:, 1] += 1.4*np.sin(t*.23+phase)
            knots[:, 2] += 1.1*np.sin(t*.18+phase*.8)
            selected = self.group==i
            center[selected] = spline(knots, s[selected])
        normal, binormal = frame(center, self.normals[self.group], s)
        phase = self.seed[:, 0, None]*np.pi*2
        roll = .65*np.sin(s*6-t*.7)+s*1.2-t*.16
        a, b = self.offset[:, 0, None]*2.0, self.offset[:, 1, None]*1.3
        lateral = a*np.cos(roll)-b*np.sin(roll)
        depth = a*np.sin(roll)+b*np.cos(roll)
        spread = (.65+1.65*(1-.9*np.exp(-((s-.55)/.20)**2)))*(1+bass*.035)
        frequency = .5+.46*np.sin(s*3.8+self.seed[:, 1, None]*1.4)
        detail = audio_sample(audio, frequency, s*6+self.group[:, None]*.3, now, options)
        accent = pulse_field(audio, now, np.broadcast_to(s*56, detail.shape), 23)*options.gain
        lateral = lateral*spread + .35*np.sin(s*23-t*1.3+phase) + detail*.6*np.sin(s*9+phase)
        depth = depth*spread + .30*np.sin(s*13-t*.85+phase)+accent*.10
        vertices = center+normal*lateral[..., None]+binormal*depth[..., None]
        if options.stereo:
            vertices[..., 2] += audio.director.pan*.7*style.stereo
        weight = np.exp(-.22*np.sum(self.offset*self.offset, axis=1))[:, None]
        brightness = .55+.45*self.seed[:, 2, None]
        leading = np.exp(-((material-.82)/.12)**2)
        heat = (.24+.43*weight*brightness+detail*.55+accent*.55*(.4+.6*weight)
                +high*.12+.28*leading+.18*(self.seed[:, 3,None]>.9))
        heat = fade_ends(fade_ends(heat, material, margin=.015, fade=.12), s)
        return finish(vertices, heat, self.edges, self.faces, options)
