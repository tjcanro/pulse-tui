"""Smooth spatial paths and stable local frames for wire bands and currents."""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=16)
def _curvature(count):
    system = np.eye(count)
    operator = np.zeros((count,count))
    for i in range(1,count-1):
        system[i,i-1:i+2] = (1,4,1)
        operator[i,i-1:i+2] = (6,-12,6)
    return np.linalg.solve(system,operator)


def spline(knots, parameter):
    """C2-continuous interpolating paths; smooth curvature also smooths rails."""
    position = np.clip(parameter,0,1)*(len(knots)-1)
    segment = np.minimum(position.astype(int),len(knots)-2)
    b = (position-segment)[...,None]
    a = 1-b
    second = _curvature(len(knots))@knots
    return (a*knots[segment]+b*knots[segment+1]
            +((a*a*a-a)*second[segment]+(b*b*b-b)*second[segment+1])/6)


def tangents(center):
    tangent = np.gradient(center, axis=-2)
    tangent /= np.maximum(1e-9, np.linalg.norm(tangent, axis=-1, keepdims=True))
    return tangent


def transported_normals(center):
    """Transport a normal along cached paths, avoiding inflection-point flips."""
    tangent = tangents(center)
    normal = np.zeros_like(center)
    normal[:, 0] = np.cross(tangent[:, 0], [0, 0, 1])
    normal[:, 0] /= np.maximum(1e-9, np.linalg.norm(normal[:, 0], axis=-1, keepdims=True))
    for i in range(1, center.shape[-2]):
        previous, direction = normal[:, i-1], tangent[:, i]
        value = previous-direction*np.sum(previous*direction, axis=-1, keepdims=True)
        normal[:, i] = value/np.maximum(1e-9, np.linalg.norm(value, axis=-1, keepdims=True))
    return normal


def frame(center, reference, parameter=None, rest_tangent=None):
    """Align cached normals with the deformed tangent without temporal flips."""
    if parameter is not None:
        # The material grid slides along the path. Sample its cached frame at
        # the new positions rather than attaching the old normals to indices.
        position = parameter*(reference.shape[1]-1)
        index = np.minimum(position.astype(int), reference.shape[1]-2)
        mix = (position-index)[...,None]
        row = np.arange(len(reference))[:,None]
        reference = reference[row,index]*(1-mix)+reference[row,index+1]*mix
        if rest_tangent is not None:
            rest_tangent = rest_tangent[row,index]*(1-mix)+rest_tangent[row,index+1]*mix
    tangent = tangents(center)
    if rest_tangent is None:
        normal = reference-tangent*np.sum(reference*tangent, axis=-1, keepdims=True)
    else:
        # Rotate the rest frame by the smallest rotation between tangents.
        # Projection alone becomes unstable when a bend turns through 90°.
        rest_tangent = rest_tangent/np.maximum(1e-9,np.linalg.norm(rest_tangent,axis=-1,keepdims=True))
        reference = reference-rest_tangent*np.sum(reference*rest_tangent,axis=-1,keepdims=True)
        axis = np.cross(rest_tangent,tangent)
        cosine = np.sum(rest_tangent*tangent,axis=-1,keepdims=True)
        turn = np.cross(axis,reference)
        normal = reference+turn+np.cross(axis,turn)/np.maximum(1e-6,1+cosine)
        normal -= tangent*np.sum(normal*tangent,axis=-1,keepdims=True)
    normal /= np.maximum(1e-9, np.linalg.norm(normal, axis=-1, keepdims=True))
    return normal, np.cross(tangent, normal)


def fade_ends(heat, parameter, margin=.035, fade=.045):
    """Hide open-path recycling and fade a flowing strand's head and tail."""
    envelope = np.clip((np.minimum(parameter,1-parameter)-margin)/fade, 0, 1)
    while envelope.ndim < heat.ndim:
        envelope = envelope[...,None]
    return np.where(envelope>0, heat*envelope-(1-envelope)*.4, -.4)
