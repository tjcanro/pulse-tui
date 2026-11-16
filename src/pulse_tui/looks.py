"""Named visual stages and experiments. Classic is a permanent fallback."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Look:
    memory: float = 0.0
    crests: float = 0.0
    motion: float = 0.0
    stereo: float = 0.0
    sections: float = 0.0
    ripple_scale: float = 1.0
    speed: float = 1.0
    palette: str = "auto"
    camera: str = "flight"
    density: float = 2.0
    gain: float = 1.3


LOOKS = {
    "cinematic": Look(memory=.70, crests=1.0, motion=1.0, stereo=1.0,
                      sections=1.0, camera="choreo"),
    "classic": Look(),
    "crests": Look(crests=1.0),
    "memory": Look(memory=.75, crests=1.0),
    "ember": Look(memory=.6, crests=.7, motion=.6, stereo=.7, sections=.65,
                  ripple_scale=1.1, speed=.8, palette="warm", camera="choreo",
                  density=1.75, gain=1.15),
    "neon": Look(memory=.75, crests=1.2, motion=1.1, stereo=1.0, sections=1.0,
                 ripple_scale=.85, speed=1.12, palette="neon", camera="choreo", gain=1.4),
    "deep-space": Look(memory=.9, crests=.75, motion=.4, stereo=.8, sections=.6,
                       speed=.7, palette="blue", camera="choreo", density=1.5, gain=1.1),
    "surge": Look(memory=1.1, crests=1.3, motion=1.7, stereo=1.0, sections=1.4,
                  ripple_scale=.8, speed=1.25, palette="neon", camera="choreo", gain=1.5),
    "aurora": Look(memory=.9, crests=.85, motion=.5, stereo=.9, sections=.7,
                   speed=.8, palette="aurora", camera="choreo", density=1.75),
    "crimson": Look(memory=.65, crests=1.15, motion=.9, stereo=1.0, sections=1.1,
                    palette="crimson", camera="choreo", gain=1.4),
    "gold": Look(memory=.7, crests=.9, motion=.65, stereo=.8, sections=.8,
                 palette="gold", camera="choreo", density=1.75),
    "velvet": Look(memory=.8, crests=.75, motion=.5, stereo=.8, sections=.65,
                   speed=.85, palette="violet", camera="choreo", density=1.75),
    "sunset": Look(memory=.7, crests=1.0, motion=.8, stereo=1.0, sections=.85,
                   palette="sunset", camera="choreo"),
    "glacier": Look(memory=.85, crests=.8, motion=.4, stereo=.8, sections=.6,
                    speed=.75, palette="ice", camera="choreo", density=1.5),
}


def apply_look(options, name):
    """Apply an entire preset; CLI overrides are applied afterwards."""
    look = LOOKS[name]
    options.look = name
    for field in ("camera", "palette", "density", "gain"):
        setattr(options, field, getattr(look, field))
