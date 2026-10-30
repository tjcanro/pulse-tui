"""Shared audio format, terminal colors, and interactive options."""
from __future__ import annotations

import dataclasses

BARS = 64
BG = "\x1b[48;2;8;5;16m"
RESET = "\x1b[0m"
CAMERAS = ("flight", "orbit", "overhead", "fixed")


@dataclasses.dataclass

class Options:
    camera: str = "flight"
    gain: float = 1.3
    density: float = 2.0
    paused: bool = False
    hud: bool = True
    yaw: float = 0.0
    elevation: float = 0.0
