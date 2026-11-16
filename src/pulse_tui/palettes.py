"""OKLCH theme gradients and sRGB conversion, shared by live color analysis."""
from __future__ import annotations

import math
import numpy as np


def _lch_to_lab(lightness, chroma, hue):
    angle = math.radians(hue)
    return lightness, chroma * math.cos(angle), chroma * math.sin(angle)


def _linear_rgb(lightness, a, b):
    # Björn Ottosson's public-domain Oklab conversion matrices:
    # https://bottosson.github.io/posts/oklab/#converting-from-linear-srgb-to-oklab
    l = (lightness + .3963377774 * a + .2158037573 * b) ** 3
    m = (lightness - .1055613458 * a - .0638541728 * b) ** 3
    s = (lightness - .0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + .2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - .3413193965 * s,
            -.0041960863 * l - .7034186147 * m + 1.7076147010 * s)


def lab_to_rgb(lab):
    """Reduce chroma into sRGB gamut while preserving hue and lightness."""
    lightness, a, b = map(float, lab)
    rgb = _linear_rgb(lightness, a, b)
    if min(rgb) < 0 or max(rgb) > 1:
        low, high = 0.0, 1.0
        for _ in range(14):
            scale = (low + high) / 2
            candidate = _linear_rgb(lightness, a * scale, b * scale)
            if min(candidate) >= 0 and max(candidate) <= 1:
                low = scale
            else:
                high = scale
        rgb = _linear_rgb(lightness, a * low, b * low)

    def encode(channel):
        channel = max(0.0, min(1.0, channel))
        value = 12.92 * channel if channel <= .0031308 else 1.055 * channel ** (1 / 2.4) - .055
        return round(value * 255)

    return tuple(encode(channel) for channel in rgb)


def _gradient(stops):
    """Twelve heat colors, interpolating hue by the shorter arc of the wheel."""
    result = []
    for t in np.linspace(0, 2, 12):
        i = min(1, int(t))
        fraction = t - i
        l0, c0, h0 = stops[i]
        l1, c1, h1 = stops[i + 1]
        hue = h0 + ((h1 - h0 + 180) % 360 - 180) * fraction
        result.append(_lch_to_lab(l0 + (l1 - l0) * fraction,
                                  c0 + (c1 - c0) * fraction, hue))
    return np.array(result)


# Low terrain → middle → hottest crests. Warm is deliberately softer than neon.
PALETTE_LABS = {
    "warm": _gradient(((.68, .16, 25), (.80, .18, 55), (.90, .15, 85))),
    "blue": _gradient(((.65, .19, 275), (.78, .18, 240), (.88, .14, 205))),
    "neon": _gradient(((.67, .27, 330), (.75, .25, 290), (.89, .17, 190))),
    "aurora": _gradient(((.61, .16, 165), (.77, .19, 180), (.89, .12, 210))),
    "crimson": _gradient(((.60, .23, 15), (.73, .25, 25), (.86, .19, 50))),
    "gold": _gradient(((.65, .14, 55), (.80, .18, 80), (.92, .14, 100))),
    "violet": _gradient(((.60, .22, 300), (.75, .20, 320), (.88, .12, 350))),
    "sunset": _gradient(((.65, .23, 350), (.79, .20, 25), (.90, .16, 75))),
    "ice": _gradient(((.62, .13, 260), (.79, .13, 225), (.94, .04, 210))),
}


def _quiet_variant(labs, shifts):
    result = labs.copy()
    angles = np.linspace(*shifts, len(labs)) * math.pi / 180
    a, b = labs[:, 1], labs[:, 2]
    result[:, 0] -= .13
    result[:, 1] = (a * np.cos(angles) - b * np.sin(angles)) * .62
    result[:, 2] = (a * np.sin(angles) + b * np.cos(angles)) * .62
    return result


_SHIFTS = {"warm": (-8, -12), "blue": (10, 15), "neon": (-30, 30),
           "aurora": (10, 20), "crimson": (-5, 5), "gold": (-15, -10),
           "violet": (5, 10), "sunset": (-15, 10), "ice": (10, 20)}
QUIET_LABS = {name: _quiet_variant(labs, _SHIFTS[name]) for name, labs in PALETTE_LABS.items()}


def expressive_labs(name, amount):
    """Related quiet/lively gradients vary hue, chroma, and lightness together."""
    quiet = QUIET_LABS[name]
    return quiet + (PALETTE_LABS[name] - quiet) * min(1.0, max(0.0, amount))


PRESET_RGB = {name: tuple(lab_to_rgb(color) for color in expressive_labs(name, .35))
              for name in PALETTE_LABS}

# Neighbouring families are ordered around the wheel for a continuous loop.
CYCLE_ORDER = ("warm", "gold", "aurora", "ice", "blue", "neon", "violet", "sunset", "crimson")
