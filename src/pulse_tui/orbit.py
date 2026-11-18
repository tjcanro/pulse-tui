"""Dense central arc work, with fading fragments expanding to the margins."""
import numpy as np

from .geometry import audio_sample, finish, pulse_field, strips
from .looks import LOOKS


class Orbit:
    def __init__(self, density):
        self.core = max(12, round(26*density))
        self.outer = max(12, round(28*density))
        self.count = self.core+self.outer
        self.length = max(12, round(25*np.sqrt(density)))+1
        rng = np.random.default_rng(7701)
        self.seed = rng.uniform(0, 1, (self.count, 8))
        self.u = np.linspace(0, 1, self.length)[None, :, None]
        self.v = np.array([-.5, .5])[None, None, :]
        self.edges, self.faces = strips(self.count, self.length, 2,
                                        max(2, round(5*np.sqrt(density))))

    def evaluate(self, audio, now, options):
        style = LOOKS[options.look]
        t = now*style.speed
        seed = self.seed
        bass, mid, high = audio.levels*options.gain
        # Most of the permanent structure stays near the center. Transient
        # fragments are continuously born there and expand outward, fading
        # before their cyclic reset so no visible object teleports inward.
        progress = (seed[:, 0]+t*.073) % 1
        radius = np.where(np.arange(self.count) < self.core,
                          .45+5.8*seed[:, 0]**1.3, .7+15.5*progress)
        envelope = np.where(np.arange(self.count) < self.core, 1.0,
                            (1-np.exp(-progress*24))*(1-progress)**.55)
        r = radius[:, None, None]
        theta = (seed[:, 1, None, None]*np.pi*2 + self.u*(.35+seed[:, 2, None, None])*np.pi
                 + t*(.075+seed[:, 3, None, None]*.075)*np.where(seed[:, 4, None, None]>.5, 1, -1))
        frequency = np.broadcast_to(seed[:, 5, None, None], (self.count, self.length, 1))
        detail = audio_sample(audio, frequency, np.broadcast_to(self.u*4, frequency.shape), now, options)
        coordinate = r+np.zeros_like(self.u)
        wave = (pulse_field(audio, now, coordinate, 6.0, band=0)
                + .65*pulse_field(audio, now, coordinate, 8.0, band=1)
                + .4*pulse_field(audio, now, coordinate, 11.0, band=2))*options.gain
        r = r*(1+.035*bass)+self.v*(.10+seed[:, 6, None, None]*.28)
        r = r+detail*.22*np.sin(theta*5+seed[:, 7, None, None]*6)
        a, b = r*np.cos(theta), r*np.sin(theta)
        yaw = seed[:, 4, None, None]*np.pi+t*.025
        tilt = (seed[:, 3, None, None]-.5)*2.1+t*.018
        x = a*np.cos(yaw)-b*np.cos(tilt)*np.sin(yaw)
        y = b*np.sin(tilt)+.15*mid*np.sin(theta*3+t*.2)
        z = a*np.sin(yaw)+b*np.cos(tilt)*np.cos(yaw)
        heat = (.38+seed[:, 7, None, None]*.25+detail*.65+wave*.6+high*.2)
        heat = (heat+.12)*envelope[:, None, None]-.12
        heat = heat+np.zeros_like(self.v)
        vertices = np.stack((x, y+np.zeros_like(x), z), axis=-1)
        return finish(vertices, heat, self.edges, self.faces, options)
