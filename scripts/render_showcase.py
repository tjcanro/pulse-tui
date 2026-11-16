#!/usr/bin/env python3
"""Render the actual TUI's presets to PNG/MP4/GIF using a labeled test score.

Development-only tool; requires Pillow and ffmpeg. It never adds synthetic audio
to the live application, whose --demo option remains removed.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import html
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pulse_tui.looks import LOOKS
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options
from preview_score import stereo_score

from PIL import Image, ImageDraw, ImageFont

BACKGROUND = (8, 5, 16)
ANSI = re.compile(r'(\x1b\[[0-9;]*m)')
DESCRIPTIONS = {
    'classic': 'Before: the original moving wireframe with adaptive colors.',
    'crests': 'Step 1: bright crest accents and quieter valley wires.',
    'memory': 'Step 2: the previous sixteen seconds travel toward the horizon.',
    'cinematic': 'Recommended: history, stereo, crests, musical camera, and section waves.',
    'ember': 'Softer amber/red terrain, broad ripples, and a gentler camera.',
    'neon': 'Sharper magenta/cyan ridges, finer geometry, and a closer camera.',
    'deep-space': 'Blue, spacious, and slow: longer trails with a restrained camera.',
    'surge': 'Experiment: stronger release waves and more aggressive camera movement.',
    'aurora': 'Emerald/teal/cyan, long history, and gentle camera motion.',
    'crimson': 'Cherry/scarlet/orange with strong crest accents.',
    'gold': 'Bronze/gold/lemon, restrained motion, and warm crests.',
    'velvet': 'Plum/orchid/rose with softer motion.',
    'sunset': 'Pink/coral/amber with a lively cinematic camera.',
    'glacier': 'Steel blue/ice white, spacious and slow.',
}


class TerminalImage:
    """Use actual Braille glyph masks, not an invented pixel approximation."""
    def __init__(self, cols, rows):
        self.width, self.height = cols * 8, rows * 16
        fonts = [Path('/System/Library/Fonts/Apple Symbols.ttf'),
                 Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')]
        font = next((p for p in fonts if p.exists()), None)
        if font is None:
            raise SystemExit('Install a Braille-capable font, or configure TerminalImage font paths.')
        self.braille = ImageFont.truetype(str(font), 16)
        text = Path('/System/Library/Fonts/Menlo.ttc')
        self.text = ImageFont.truetype(str(text if text.exists() else font), 12)

    @lru_cache(maxsize=8192)
    def tile(self, char, color):
        image = Image.new('RGB', (8, 16), BACKGROUND)
        braille = 0x2800 <= ord(char) <= 0x28ff
        ImageDraw.Draw(image).text((0, 0 if braille else 1), char,
                                  font=self.braille if braille else self.text, fill=color)
        return image

    def draw(self, lines):
        image = Image.new('RGB', (self.width, self.height), BACKGROUND)
        color = (170, 155, 200)
        for y, line in enumerate(lines):
            x = 0
            for token in ANSI.split(line):
                if token.startswith('\x1b['):
                    values = token[2:-1].split(';')
                    if values[:2] == ['38', '2']:
                        color = tuple(map(int, values[2:5]))
                else:
                    for char in token:
                        if char != ' ':
                            image.paste(self.tile(char, color), (x * 8, y * 16))
                        x += 1
        return image


def gallery(destination, names):
    cards = []
    for name in names:
        cards.append(f'''<article><h2>{html.escape(name.title())}</h2>
<video controls muted loop playsinline preload="none" poster="{name}.png"><source src="{name}.mp4" type="video/mp4"></video>
<p>{html.escape(DESCRIPTIONS[name])}</p><code>party --look {name}</code></article>''')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pulse · visual experiments</title>
<style>body{margin:0;background:#080510;color:#d9d5e9;font:16px/1.6 system-ui,sans-serif}
main{max-width:1440px;margin:0 auto;padding:40px 24px}h1{font-size:36px;margin:0}h2{color:#b9d9ff}
.intro{max-width:850px;color:#b2aac6}video,img{width:100%;display:block;background:#080510}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:24px}
article{border:1px solid #29213c;padding:16px;border-radius:14px}code{color:#75e4f0}
.hero{border:1px solid #5d4585;border-radius:16px;padding:20px;margin:24px 0 40px}
p{margin:12px 0}a{color:#91d7ff}@media(max-width:500px){.grid{grid-template-columns:1fr}}</style>
<main><h1>Pulse · visual experiments</h1><p class="intro">Actual terminal-renderer output at 24 fps.
Every clip uses the same deterministic stereo test score, including a buildup and release.
These silent recordings show generated spectra, not a captured song. Play matching clips from
the start to compare their motion. No shader or browser graphics support is needed.</p>
<div class="hero"><h2>Selected default: Cinematic</h2>
<video controls muted loop playsinline preload="metadata" poster="cinematic.png"><source src="cinematic.mp4" type="video/mp4"></video>
<p>A deliberate balance: camera motion stays slower than the pulses, with no beat shake.
The more aggressive experiment is preserved as Surge.</p><code>party</code></div>
<h2>Stages and alternatives</h2><div class="grid">''' + '\n'.join(cards) + '''</div>
<p>Press <code>v</code> in the running app to cycle all looks. <code>p</code> cycles colors;
<code>c</code> cycles cameras. The source snapshot before these additions is preserved separately.</p>
<p><a href="comparison.png">Open the full contact sheet</a> · <a href="cinematic.gif">Open the animated GIF</a></p></main></html>'''
    (destination / 'index.html').write_text(document)


def inline_gif(destination):
    """Render at the GIF's native terminal size, avoiding video/dither artifacts."""
    scene, renderer = Scene(), Renderer()
    options = Options.for_look('cinematic')
    painter = TerminalImage(96, 32)
    frames = []
    for frame in range(24 * 24):
        now = frame / 24
        scene.update(stereo_score(now), now, 1 / 24)
        if now >= 16 and frame % 2 == 0:
            frames.append(painter.draw(renderer.frame(scene, now, options, 96, 32, 'RENDER / STEREO SCORE', 24)))
    samples = Image.new('RGB', (384, 256 * 8), BACKGROUND)
    for i, image in enumerate(frames[::12]):
        samples.paste(image.resize((384, 256)), (0, i * 256))
    palette = samples.quantize(colors=32)
    indexed = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in frames]
    indexed[0].save(destination / 'cinematic.gif', save_all=True, append_images=indexed[1:],
                    loop=0, duration=[80, 80, 90] * 32, optimize=True, disposal=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/media/showcase')
    parser.add_argument('--looks', nargs='+', choices=tuple(LOOKS), default=list(LOOKS))
    parser.add_argument('--stills-only', action='store_true')
    parser.add_argument('--seconds', type=int, default=12)
    args = parser.parse_args()
    ffmpeg = shutil.which('ffmpeg')
    if not args.stills_only and not ffmpeg:
        parser.error('ffmpeg is required for video rendering')
    args.output.mkdir(parents=True, exist_ok=True)
    cols, rows, fps, start = 128, 42, 24, 12
    painter = TerminalImage(cols, rows)
    thumbnails = []
    for name in args.looks:
        scene, renderer = Scene(), Renderer()
        options = Options.for_look(name)
        pipe = None
        if not args.stills_only:
            pipe = subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format', 'rgb24',
                                     '-video_size', f'{cols*8}x{rows*16}', '-framerate', str(fps), '-i', '-',
                                     '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                                     '-movflags', '+faststart', str(args.output / f'{name}.mp4')], stdin=subprocess.PIPE)
        poster = None
        try:
            for frame in range((start + args.seconds) * fps):
                now = frame / fps
                scene.update(stereo_score(now), now, 1 / fps)
                record = frame >= start * fps and pipe is not None
                still = frame == int((start + args.seconds * .85) * fps)
                if not record and not still:
                    continue
                image = painter.draw(renderer.frame(scene, now, options, cols, rows, 'RENDER / STEREO SCORE', fps))
                if record:
                    pipe.stdin.write(image.tobytes())
                if still:
                    poster = image
                    image.save(args.output / f'{name}.png')
        finally:
            if pipe:
                pipe.stdin.close()
                if pipe.wait() != 0:
                    raise RuntimeError(f'Video encoding failed: {name}')
        thumbs = poster.resize((512, 336), Image.Resampling.LANCZOS)
        tile = Image.new('RGB', (536, 390), BACKGROUND)
        draw = ImageDraw.Draw(tile)
        draw.text((12, 8), name.upper() + ('  /  SELECTED' if name == 'cinematic' else ''), font=painter.text, fill=(140, 220, 245))
        tile.paste(thumbs, (12, 38))
        thumbnails.append(tile)
        print(f'Rendered {name}', flush=True)
    contact = Image.new('RGB', (536 * 4, 390 * ((len(thumbnails) + 3) // 4)), BACKGROUND)
    for i, thumb in enumerate(thumbnails):
        contact.paste(thumb, ((i % 4) * 536, (i // 4) * 390))
    contact.save(args.output / 'comparison.png')
    if not args.stills_only and 'cinematic' in args.looks:
        inline_gif(args.output)
    gallery(args.output, args.looks)
    print(args.output / 'index.html', flush=True)


if __name__ == '__main__':
    main()
