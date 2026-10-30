"""Capture processed frequency bands from a separate CAVA process."""
from __future__ import annotations

import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np

from .settings import BARS


class RawFrames:
    """8-bit mono CAVA frames; reads may split or combine arbitrary frames."""
    def __init__(self, bars=BARS):
        self.bars = bars
        self.pending = bytearray()

    def feed(self, data):
        self.pending.extend(data)
        count = len(self.pending) // self.bars
        if not count:
            return None
        start = (count - 1) * self.bars
        latest = np.frombuffer(bytes(self.pending[start:start + self.bars]), dtype=np.uint8)
        del self.pending[:count * self.bars]
        return latest.astype(float) / 255.0



class CavaInput:
    """Run CAVA with an isolated temporary raw-output config, never edit the user's."""
    def __init__(self, config, method=None, source=None):
        executable = shutil.which("cava")
        if not executable:
            raise RuntimeError("CAVA was not found. Install CAVA to capture audio.")
        self.config = configparser.ConfigParser(strict=False)
        self.config.read(config)
        for section in ("general", "input", "output", "smoothing"):
            if not self.config.has_section(section):
                self.config.add_section(section)
        for key, value in {"bars": str(BARS), "framerate": "60", "autosens": "1",
                           "lower_cutoff_freq": "40", "higher_cutoff_freq": "16000",
                           "live-config": "0"}.items():
            self.config.set("general", key, value)
        if not self.config.has_option("input", "method"):
            self.config.set("input", "method", "coreaudio" if sys.platform == "darwin" else "pulse")
        if not self.config.has_option("input", "source"):
            self.config.set("input", "source", "tap" if sys.platform == "darwin" else "auto")
        if method:
            self.config.set("input", "method", method)
        if source:
            self.config.set("input", "source", source)
        # Replace the complete visual-output section so existing orientations cannot interfere.
        self.config.remove_section("output")
        self.config.add_section("output")
        for key, value in {"method": "raw", "raw_target": "/dev/stdout", "data_format": "binary",
                           "bit_format": "8bit", "channels": "mono", "mono_option": "average"}.items():
            self.config.set("output", key, value)
        for key, value in {"monstercat": "0", "waves": "0", "noise_reduction": "35"}.items():
            self.config.set("smoothing", key, value)
        self.directory = tempfile.TemporaryDirectory(prefix="pulse-tui-")
        self.path = Path(self.directory.name) / "cava.conf"
        with self.path.open("w") as f:
            self.config.write(f)
        self.log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen([executable, "-p", str(self.path)], stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=self.log)
        except BaseException:
            self.log.close()
            self.directory.cleanup()
            raise
        self.latest = np.zeros(BARS)
        self.lock = threading.Lock()
        self.sequence = 0
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        self.started = time.monotonic()

    def _read(self):
        decoder = RawFrames()
        try:
            while True:
                data = os.read(self.process.stdout.fileno(), 4096)
                if not data:
                    break
                frame = decoder.feed(data)
                if frame is not None:
                    with self.lock:
                        self.latest = frame
                        self.sequence += 1
        except (OSError, ValueError):
            pass

    def poll(self):
        if self.process.poll() is not None:
            self.log.seek(0)
            message = self.log.read().decode(errors="replace").strip()
            raise RuntimeError("CAVA stopped: " + (message[-1600:] or f"exit {self.process.returncode}"))
        with self.lock:
            return self.latest.copy(), self.sequence

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.thread.join(timeout=2)
        self.process.stdout.close()
        self.log.close()
        self.directory.cleanup()
