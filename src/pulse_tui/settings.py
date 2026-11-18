"""Shared audio format, terminal colors, and interactive options."""
from __future__ import annotations

import dataclasses
from .looks import LOOKS, apply_look

BARS = 64
BG = "\x1b[48;2;8;5;16m"
RESET = "\x1b[0m"
CAMERAS = ("choreo", "flight", "orbit", "overhead", "fixed")
SCENES = ("terrain", "ribbons", "orbit", "filaments")
SCENE_LABELS = {"terrain": "Terrain", "ribbons": "Endless Ribbons",
                "orbit": "Orbital Fragments", "filaments": "Filament Current"}
PALETTES = ("auto", "cycle", "warm", "blue", "neon", "aurora", "crimson", "gold", "violet", "sunset", "ice")


@dataclasses.dataclass
class Options:
    camera: str = "choreo"
    gain: float = 1.3
    density: float = 2.0
    paused: bool = False
    hud: bool = True
    yaw: float = 0.0
    elevation: float = 0.0
    palette: str = "auto"
    look: str = "cinematic"
    history: bool = True
    highlights: bool = True
    stereo: bool = True
    sections: bool = True
    scene: str = "terrain"

    @classmethod
    def for_look(cls, name="cinematic", **overrides):
        options = cls()
        apply_look(options, name)
        for key, value in overrides.items():
            setattr(options, key, value)
        return options
