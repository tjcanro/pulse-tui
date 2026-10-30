"""Read controls, send changed rows, and restore terminal state on exit."""
from __future__ import annotations

import os
import select
import sys
import termios
import tty

from .settings import BG, CAMERAS, RESET


class Terminal:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.original = termios.tcgetattr(self.fd)
        self.pending_keys = ""
        self.previous_lines = []
        tty.setcbreak(self.fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l" + BG + "\x1b[2J")
        sys.stdout.flush()
        return self

    def __exit__(self, *_):
        try:
            sys.stdout.write(RESET + "\x1b[?7h\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original)

    def keys(self):
        if select.select([self.fd], [], [], 0)[0]:
            self.pending_keys += os.read(self.fd, 1024).decode(errors="ignore")
        keys, self.pending_keys = self.pending_keys, ""
        # Keep partial arrow sequences until the remaining bytes arrive.
        for suffix in ("\x1b[", "\x1b"):
            if keys.endswith(suffix):
                keys, self.pending_keys = keys[:-len(suffix)], suffix
                break
        return keys

    def draw(self, lines):
        # Skip unchanged rows, including the quiet horizon and paused frames.
        previous = self.previous_lines if len(self.previous_lines) == len(lines) else []
        updates = [f"\x1b[{i + 1};1H{line}\x1b[K" for i, line in enumerate(lines)
                   if i >= len(previous) or line != previous[i]]
        if updates:
            sys.stdout.write(BG + "".join(updates))
            sys.stdout.flush()
        self.previous_lines = lines



def handle_keys(keys, options, scene, now):
    for sequence, yaw, height in (("\x1b[D", -.14, 0), ("\x1b[C", .14, 0),
                                  ("\x1b[A", 0, .6), ("\x1b[B", 0, -.6)):
        while sequence in keys:
            options.yaw += yaw
            options.elevation = min(10, max(-2, options.elevation + height))
            keys = keys.replace(sequence, "", 1)
    for key in keys:
        if key in "qQ\x03":
            return False
        if key == "c":
            options.camera = CAMERAS[(CAMERAS.index(options.camera) + 1) % len(CAMERAS)]
        elif key == " ":
            options.paused = not options.paused
        elif key in "+=":
            options.gain = min(3, round(options.gain + .1, 1))
        elif key == "-":
            options.gain = max(.2, round(options.gain - .1, 1))
        elif key == "]":
            options.density = min(4.0, round(options.density + .25, 2))
        elif key == "[":
            options.density = max(.5, round(options.density - .25, 2))
        elif key == "h":
            options.hud = not options.hud
        elif key in "bmt":
            scene.add(now, "bmt".index(key))
    return True
