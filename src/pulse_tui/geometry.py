"""Shared geometry and audio sampling for the three spatial scenes.

Meshes feed the existing triangle/edge rasterizer. Construction is cached;
evaluation only changes positions and heat. No renderer-size particle arrays.
"""
from dataclasses import dataclass
import math

import numpy as np

from .looks import LOOKS


@dataclass
class Geometry:
    vertices: np.ndarray
    heat: np.ndarray
    edges: np.ndarray
    faces: np.ndarray


def strips(count, length, width, rib_step=1, opaque=False):
    """Longitudinal rails, occasional cross-ribs, and optional hidden surfaces."""
    indices = np.arange(count*length*width, dtype=np.int64).reshape(count, length, width)
    rails = np.column_stack((indices[:, :-1].ravel(), indices[:, 1:].ravel()))
    ribs = np.column_stack((indices[:, ::rib_step, :-1].ravel(), indices[:, ::rib_step, 1:].ravel()))
    edges = np.concatenate((rails, ribs))
    faces = np.empty((0, 3), dtype=np.int64)
    if opaque and width > 1:
        a, b = indices[:, :-1, :-1].ravel(), indices[:, 1:, :-1].ravel()
        c, d = indices[:, :-1, 1:].ravel(), indices[:, 1:, 1:].ravel()
        faces = np.concatenate((np.column_stack((a, b, c)), np.column_stack((b, d, c))))
    return edges, faces


def audio_sample(audio, frequency, lag, now, options):
    """Smooth current spectral detail plus the existing bounded audio memory."""
    frequency = np.clip(frequency, 0, 1)
    current = np.interp(frequency, np.linspace(0, 1, 64), audio._visual_spectrum)
    style = LOOKS[options.look]
    if not options.history or not style.memory:
        return current*options.gain
    # TerrainHistory's time/frequency sampler is reusable with these coordinates.
    side = np.where(frequency < .5, -1.0, 1.0)
    old = audio.history.sample(side*frequency*14, 1-lag*1.9, now,
                               stereo=style.stereo if options.stereo else 0)
    mix = min(.65, style.memory*.55)
    return (current*(1-mix)+old*mix)*options.gain


def pulse_field(audio, now, coordinate, speed, band=None):
    """Travelling, smoothly born accents; manual b/m/t pulses work here too."""
    result = np.zeros_like(coordinate, dtype=float)
    for pulse in audio.pulses:
        if band is not None and pulse.band != band:
            continue
        age = max(0, now-pulse.when)
        attack = 1-math.exp(-age/.065)
        width = (1.2, .85, .48)[pulse.band]
        wave = np.exp(-((coordinate-age*speed)/width)**2)
        result += wave*pulse.strength*attack*math.exp(-age*.65)
    return result


def finish(vertices, heat, edges, faces, options):
    heat = np.clip(heat, -.4, 1.4 if options.highlights else .98)
    return Geometry(np.ascontiguousarray(vertices.reshape(-1, 3)),
                    np.ascontiguousarray(heat.ravel()), edges, faces)
