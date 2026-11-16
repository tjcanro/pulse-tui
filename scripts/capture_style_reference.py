"""Procedural PCM -> real CAVA. Silent FIFO only; no audio device/player."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os, sys, threading, time, tempfile
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from pulse_tui.audio import CavaInput
from pulse_tui.colors import AdaptiveColors
RATE = 44100
SECONDS = 28

def pcm(kind):
    t = np.arange(RATE * SECONDS) / RATE

    def env(onsets, period, decay):
        return sum((np.exp(-((t - onset) % period) * decay) for onset in onsets))
    p = t % 0.5
    if kind == 'electronic':
        audio = 0.7 * np.sin(2 * np.pi * (44 * p + 100 / 35 * (1 - np.exp(-35 * p)))) * np.exp(-12 * p) + 0.04 * np.sin(2 * np.pi * 60 * t)
    elif kind == 'hip-hop':
        audio = np.sin(2 * np.pi * 52 * t) * (0.26 + 0.22 * env((0, 0.75, 1.5, 2.75, 3.25), 4, 7))
    elif kind == 'latin':
        onsets = (0, 0.75, 1.5, 2.5, 3.75)
        notes = (82, 102, 75, 104, 92)
        ages = np.stack([(t - o) % 4 for o in onsets])
        idx = ages.argmin(axis=0)
        frequencies = np.array(notes)[idx]
        phase = np.cumsum(frequencies) / RATE
        audio = np.sin(2 * np.pi * phase) * (0.08 + 0.4 * np.exp(-ages.min(axis=0) * 8))
    else:
        audio = np.sin(2 * np.pi * 86 * t) * (0.08 + 0.35 * np.exp(-p * 10))
    # Fixed-seed high-passed noise supplies broad, percussive upper bands.
    noise = np.random.default_rng(481).normal(0, 1, len(t))
    noise = np.r_[0, np.diff(noise)] * 0.5
    period = 0.5 if kind == 'pop' else 0.25
    audio += noise * 0.18 * np.exp(-(t % period) * 40)
    audio += 0.065 * np.sin(2 * np.pi * 260 * t) + 0.035 * np.sin(2 * np.pi * 510 * t)
    audio = np.clip(audio, -1, 1) * 24000
    return np.repeat(audio.astype('<i2')[:, None], 2, axis=1).tobytes()

def capture(kind):
    data = pcm(kind)
    with tempfile.TemporaryDirectory(prefix='pulse-styles-') as tmp:
        fifo = Path(tmp) / 'pcm'
        os.mkfifo(fifo)
        config = Path(tmp) / 'input.conf'
        config.write_text('[input]\nmethod = fifo\nsource = ' + str(fifo) + '\n')
        audio = CavaInput(config)
        start = threading.Event()
        stop = threading.Event()
        clock = []

        def write():
            fd = os.open(fifo, os.O_WRONLY)
            try:
                clock.append(time.monotonic())
                start.set()
                for pos in range(0, len(data), 4096):
                    if stop.is_set():
                        break
                    os.write(fd, data[pos:pos + 4096])
                    delay = clock[0] + (pos + 4096) / (RATE * 4) - time.monotonic()
                    if delay > 0:
                        stop.wait(delay)
            except BrokenPipeError:
                pass
            finally:
                os.close(fd)
        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        rows = []
        times = []
        seq = 0
        try:
            if not start.wait(5):
                raise RuntimeError('FIFO startup timed out')
            for i in range(SECONDS * 24):
                delay = clock[0] + i / 24 - time.monotonic()
                if delay > 0:
                    stop.wait(delay)
                (frame, sequence) = audio.poll()
                rows.append(np.rint(frame.mean(axis=0) * 255).astype('uint8'))
                times.append(i / 24)
            colors = AdaptiveColors()
            for (t, f) in zip(times, rows):
                colors.update(f.astype(float) / 255, t, 1 / 24)
            (b, r) = (colors.character, colors.character.rhythm)
            print(kind, colors.name, b.label, {k: round(getattr(b, k), 2) for k in ('contrast', 'regularity', 'spread', 'glide', 'pulse_rate')}, {k: round(getattr(r, k), 2) for k in ('repeat', 'percussion', 'sub_ratio', 'note_motion', 'high_rate', 'swing', 'brightness')}, r.ready, flush=True)
            return (kind, np.array(rows), np.array(times, dtype='float32'))
        finally:
            stop.set()
            audio.close()
            writer.join(2)
if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(capture, ('hip-hop', 'latin', 'electronic', 'pop')))
    np.savez_compressed(ROOT / 'tests/data/style_reference.npz', **{key: value for (name, rows, times) in results for (key, value) in ((name + '_frames', rows), (name + '_times', times))})
