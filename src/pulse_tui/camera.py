"""Choose a viewpoint and project world coordinates onto the dot grid."""
from __future__ import annotations

import math

import numpy as np
from .looks import LOOKS

def camera(now, options, director=None):
    """Return camera position and its right/up/forward viewing axes."""
    if options.camera == "choreo":
        motion = LOOKS[options.look].motion
        intensity = director.intensity if director else 0.0
        opening = director.openness(now) if director and options.sections else 0.0
        pan = director.pan if director and options.stereo else 0.0
        angle = -.55 + motion * (.22 * math.sin(now * .075) + .07 * math.sin(now * .11))
        angle += pan * motion * .06
        radius = 16.3 - 3.8 * intensity * motion + .8 * motion * math.sin(now * .08) + 1.8 * opening
        y = max(2.7, 8.5 - 5 * intensity * motion + .45 * motion * math.sin(now * .11) + opening)
        target = np.array([.5 * math.sin(now * .09) * motion, .5, -3.5 + intensity])
    elif options.camera == "flight":
        angle, radius, y = -.85 + now * .12, 13.2 + 2.5 * math.sin(now * .22), 5.1 + 2.3 * math.sin(now * .27 - .8)
        target = np.array([math.sin(now * .15) * 1.3, .65, math.cos(now * .17) * 1.3])
    else:
        angle = -.65 + now * .065 if options.camera == "orbit" else -.55
        radius, y = (10, 15) if options.camera == "overhead" else (13.5, 4.2)
        target = np.array([0, .55, 0])
    angle += options.yaw
    eye = np.array([math.sin(angle) * radius, max(1.5, y + options.elevation), math.cos(angle) * radius])
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return eye, right, up, forward



def project(x, y, z, camera, width, height, aspect):
    """Convert world coordinates to dot-grid x/y coordinates and camera depth."""
    eye, right, up, forward = camera
    dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
    depth = dx * forward[0] + dy * forward[1] + dz * forward[2]
    safe = np.maximum(depth, .1)
    cx = dx * right[0] + dy * right[1] + dz * right[2]
    cy = dx * up[0] + dy * up[1] + dz * up[2]
    px = (cx * 1.85 / aspect / safe * .5 + .5) * width
    py = (.5 - cy * 1.85 / safe * .5) * height
    return px, py, depth
