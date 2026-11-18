"""Tapered, interwoven wire bands with travelling curves and material flow."""
import numpy as np

from .curves import fade_ends, frame, spline, tangents, transported_normals
from .geometry import audio_sample, finish, pulse_field, strips
from .looks import LOOKS


WAVE_PATH = ((-34,15,0),(-19,10,1),(-7,2,4),(3,-5,6),(15,-3,4),(24,5,-1),(34,12,-7))

PATHS = (
    ((-32,-8,5),(-16,-2,7),(-3,-5,6),(8,-6,3),(14,0,0),(8,7,-3),
     (-1,11,-2),(-12,8,1),(-12,1,4),(-3,-4,6),(14,-6,3),(32,2,-5)),
    ((-31,-15,7),(-14,-12,5),(-4,-4,1),(4,2,-1),(18,1,-2),(20,9,-4),
     (10,13,-6),(7,19,-10),(30,24,-13)),
    WAVE_PATH,
    ((28,20,-10),(8,14,-8),(-3,8,-4),(2,1,-1),(17,-1,2),(26,-8,1),(34,-14,-3)),
    WAVE_PATH,
)


class Ribbons:
    def __init__(self, density):
        self.count = len(PATHS)
        self.length = round(110*np.sqrt(density))+1
        self.width = max(7, round(6*density)+1)
        self.s = np.linspace(0, 1, self.length)
        self.paths = tuple(np.array(path, dtype=float) for path in PATHS)
        rest = np.array([spline(path, self.s) for path in self.paths])
        self.normals = transported_normals(rest)
        self.rest_tangent = tangents(rest)
        self.v = np.r_[-1, -.975, np.linspace(-.82, .82, self.width-4), .975, 1]
        self.phase = np.arange(self.count)[:, None]*1.31
        self.wave_phase = self.phase.copy()
        self.wave_phase[4] = self.wave_phase[2]
        self.band_width = np.array([2.8, 1.35, 2.25, .62, .95])[:,None]
        self.flow = np.array([.027, .037, .035, .038, .041])[:,None]
        edges, self.faces = strips(self.count, self.length, self.width,
                                   max(1, round(3*np.sqrt(density))))
        grid = np.arange(self.count*self.length*self.width).reshape(self.count, self.length, self.width)
        self.beads = grid[:, ::max(2, round(3*np.sqrt(density))), [0, -1]].ravel()
        marks = grid.size+np.arange(len(self.beads)*6).reshape(-1, 6)
        bead_edges = np.column_stack((marks[:, [0, 2, 4]].ravel(), marks[:, [1, 3, 5]].ravel()))
        self.strays = np.array([-1.8, -1.4, 1.4, 1.8])
        self.stray_start = grid.size+len(self.beads)*6
        stray_edges, _ = strips(self.count, self.length, len(self.strays), rib_step=self.length+1)
        # Strays run longitudinally only, without the first cross-rib.
        stray_edges = stray_edges[:self.count*(self.length-1)*len(self.strays)]
        self.edges = np.concatenate((edges, bead_edges, stray_edges+self.stray_start))
        self.marks = np.array([[-1,0,0],[1,0,0],[0,-1,0],[0,1,0],[0,0,-1],[0,0,1]])*.055

    def centerlines(self, s, t):
        """Travelling bends plus an over/under pair around a shared wave path."""
        centers = []
        for i, path in enumerate(self.paths):
            knots = path.copy()
            phase = np.arange(len(path))*.63+(2 if i==4 else i)*1.4
            knots[:, 1] += 1.6*np.sin(t*.24+phase)
            knots[:, 2] += 1.3*np.sin(t*.18+phase*.8)
            centers.append(spline(knots, s[i]))
        center = np.array(centers)
        normal, binormal = frame(center, self.normals, s, self.rest_tangent)
        q = self.wave_phase
        wave = 2.6*np.sin(s*12-t*.48+q)+.45*np.sin(s*23-t*.67+q*.5)
        depth = 1.5*np.cos(s*11-t*.36+q*.8)
        center += normal*wave[...,None]+binormal*depth[...,None]
        normal, binormal = frame(center, self.normals, s, self.rest_tangent)
        # One broad and one narrow ribbon share a spine but pass alternately
        # in front of and behind each other instead of merely overlapping in XY.
        for i, phase in ((2,0), (4,np.pi)):
            angle = s[i]*16.5-t*.23+phase
            radius = 1.95+.45*np.sin(s[i]*7-t*.24)
            center[i] += radius[:,None]*(normal[i]*np.sin(angle)[:,None]
                                        +binormal[i]*np.cos(angle)[:,None])
        return center

    def evaluate(self, audio, now, options):
        style = LOOKS[options.look]
        t = now*style.speed
        bass, mid, high = audio.levels*options.gain
        p = self.phase
        # Vertices are material points: ribs and edge marks really travel along
        # the bands, while the open ends recycle beyond the visible frame.
        s = (self.s[None,:]+t*self.flow+p*.11) % 1
        center = self.centerlines(s, t)
        normal, binormal = frame(center, self.normals, s, self.rest_tangent)
        frequency = .5+.46*np.sin(s*2.7+p*.45)
        detail = audio_sample(audio, frequency, s*6, now, options)
        accent = pulse_field(audio, now, np.broadcast_to(s*56, detail.shape), 19)*options.gain
        center += normal*(detail*np.sin(s*11+p)*.6+accent*.025)[..., None]
        normal, binormal = frame(center, self.normals, s, self.rest_tangent)
        roll = (.90*np.sin(s*7.5-t*.50+p)+.42*np.sin(s*14-t*.55+p*.7)
                +.30*np.sin(p*.7)+.22*np.sin(t*.19+p))
        across = normal*np.cos(roll)[..., None]+binormal*np.sin(roll)[..., None]
        bend = np.cross(across, np.gradient(center, axis=1))
        bend /= np.maximum(1e-9, np.linalg.norm(bend, axis=-1, keepdims=True))
        swell = (.5+.5*np.sin(s*11-t*.65+p))**1.4
        width = (self.band_width*(.22+.95*swell)
                 *(.90+.10*np.sin(s*7-t*.38+p*.6))+bass*.05)
        v = self.v[None, None, :, None]
        vertices = (center[:, :, None, :]+across[:, :, None, :]*v*width[:, :, None, None]
                    +bend[:, :, None, :]*(1-v*v)*width[:, :, None, None]*.20)
        if options.stereo:
            vertices[..., 2] += audio.director.pan*style.stereo*.6
        edge = np.abs(self.v)[None, None, :]**4
        heat = (.28+.70*edge+.16*np.sin(self.s[None,:]*26+p)[:, :, None]
                +detail[:, :, None]*.6+accent[:, :, None]*(.35+.35*edge)+high*.12)
        heat = fade_ends(heat, s)
        points = vertices.reshape(-1, 3)[self.beads, None, :]+self.marks[None, :, :]
        point_heat = np.repeat(heat.ravel()[self.beads]+.12, 6)
        sv = self.strays[None, None, :, None]
        wisps = (center[:, :, None, :]+across[:, :, None, :]*sv*width[:, :, None, None]
                 +bend[:, :, None, :]*.55*np.sin(s[:, :, None, None]*15-t*.8+p[:, :, None, None]+sv))
        if options.stereo:
            wisps[..., 2] += audio.director.pan*style.stereo*.6
        wisp_heat = (.12+.20*np.sin(self.s[None,:,None]*16+p[:, :, None]+self.strays[None, None, :])
                     +detail[:, :, None]*.3)
        wisp_heat = fade_ends(wisp_heat, s)
        vertices = np.concatenate((vertices.reshape(-1, 3), points.reshape(-1, 3), wisps.reshape(-1, 3)))
        heat = np.r_[heat.ravel(), point_heat, wisp_heat.ravel()]
        return finish(vertices, heat, self.edges, self.faces, options)
