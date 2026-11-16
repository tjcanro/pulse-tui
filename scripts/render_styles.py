#!/usr/bin/env python3
"""Actual Braille renderer driven by labeled procedural spectra, not songs."""
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from style_score import style_score, vocal_score
from render_showcase import TerminalImage, BACKGROUND
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options

PROFILES = (
    ('acoustic', 'ACOUSTIC-LIKE / EMBER'),
    ('hip-hop', 'HIP-HOP-LIKE / CRIMSON'),
    ('latin', 'LATIN-LIKE / AURORA'),
    ('electronic', 'ELECTRONIC-LIKE / NEON'),
    ('pop', 'POP-LIKE / BLUE'),
    ('swing', 'SWING-LIKE / GOLD'),
    ('soul', 'SOUL-LIKE / VIOLET'),
    ('dance-pop', 'BRIGHT DANCE-POP / SUNSET'),
    ('ambient', 'AMBIENT-LIKE / ICE'),
)


def panel(scene, renderer, painter, now, title, note):
    image = Image.new('RGB', (painter.width, painter.height+52), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((12, 8), title, font=painter.text, fill=scene.colors.palette()[8])
    draw.text((12, 28), note, font=painter.text, fill=(155, 145, 175))
    lines = renderer.frame(scene, now, Options(hud=False), painter.width//8,
                           painter.height//16, 'GENERATED SCORE', 24)
    image.paste(painter.draw(lines), (0, 52))
    return image


def main():
    destination = ROOT/'docs/media/styles'
    destination.mkdir(parents=True, exist_ok=True)
    painter = TerminalImage(68, 23)
    names = ('hip-hop', 'latin', 'electronic', 'pop')
    titles = ('SUB BASS + DENSE HATS', 'SYNCOPATED BASS + PERCUSSION',
              'REGULAR DESCENDING / BROAD KICKS', 'PITCHED BASS + REGULAR PERCUSSION')
    scenes, renderers = [Scene() for _ in names], [Renderer() for _ in names]
    width, height = painter.width*2, (painter.height+52)*2+36
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('ffmpeg is required to render the preview')
    process = subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo',
        '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}', '-framerate', '24',
        '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination/'comparison.mp4')],
        stdin=subprocess.PIPE)
    gif = []
    try:
        for frame in range(38*24):
            now = frame/24
            lively = float(np.clip((now-28)/6, 0, 1))
            for scene, kind in zip(scenes, names):
                spectrum = style_score(now, kind, lively)
                if now >= 32:
                    spectrum += vocal_score(now, .7)
                scene.update(np.stack((spectrum, spectrum)), now, 1/24)
            if now < 26:
                continue
            image = Image.new('RGB', (width, height), BACKGROUND)
            for i, (scene, renderer, title) in enumerate(zip(scenes, renderers, titles)):
                label = 'AUTO: '+scene.colors.name.upper()+' | '+scene.colors.character.label
                tile = panel(scene, renderer, painter, now, title, label)
                image.paste(tile, ((i % 2)*painter.width, (i//2)*(painter.height+52)))
            ImageDraw.Draw(image).text((12, height-26),
                'Actual terminal renderer | procedural spectra, not recorded genres | intensity rises, then vocals enter',
                font=painter.text, fill=(155, 145, 175))
            process.stdin.write(image.tobytes())
            if frame % 3 == 0:
                gif.append(image)
            if frame == 36*24:
                image.save(destination/'comparison.png')
    finally:
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('Video encoding failed')
    # Fixed colors across frames avoid quantizer flicker in the fallback GIF.
    samples = Image.new('RGB', (width//2, height//2*6), BACKGROUND)
    for i, sample in enumerate(gif[::max(1, len(gif)//6)][:6]):
        samples.paste(sample.resize((width//2, height//2)), (0, i*(height//2)))
    palette = samples.quantize(colors=64)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in gif]
    indexed[0].save(destination/'comparison.gif', save_all=True, append_images=indexed[1:],
                    duration=125, loop=0, disposal=2, optimize=True)
    small = TerminalImage(58, 18)
    atlas = Image.new('RGB', (small.width*3, (small.height+52)*3), BACKGROUND)
    for i, (kind, title) in enumerate(PROFILES):
        scene, renderer = Scene(), Renderer()
        for frame in range(26*24):
            now = frame/24
            spectrum = style_score(now, kind)
            scene.update(np.stack((spectrum, spectrum)), now, 1/24)
        image = panel(scene, renderer, small, now, title, 'Auto selected '+scene.colors.name)
        atlas.paste(image, ((i % 3)*small.width, (i//3)*(small.height+52)))
    atlas.save(destination/'profiles.png')
    (destination/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pulse · automatic musical profiles</title>
<style>body{background:#080510;color:#d6cde4;font:16px/1.6 system-ui;margin:0}main{max-width:1400px;margin:auto;padding:32px}video,img{width:100%;display:block}a,code{color:#7fe0ec}h1,h2{font-weight:600}p{max-width:1000px}</style>
<main><h1>Auto · more of the color wheel</h1>
<p>Crimson for sustained sub-bass and dense hats, Aurora for syncopated pitched bass,
Neon for regular broad kicks, and Blue for regular pitched-bass pop-like grooves.
Each panel uses the actual Braille terminal renderer with generated spectra.
Intensity builds, then a moving vocal-like line enters without changing the family.
These are transparent feature examples, not recorded music or a genre-accuracy evaluation.</p>
<video controls muted loop playsinline poster="comparison.png"><source src="comparison.mp4" type="video/mp4"></video>
<p><a href="comparison.gif">Animated GIF</a> · <a href="comparison.png">Full-size still</a></p>
<h2>All nine automatic families</h2><img src="profiles.png" alt="Nine terminal renderings, automatically selected from nine procedural musical patterns">
<p>Default: <code>party</code>. Explicit Auto: <code>party --palette auto</code>.
All analysis is local; no song metadata or player integration. Press <code>p</code>
for Cycle or a fixed palette, and <code>v</code> for complete looks. Genre boundaries
and production overlap: the profiles are heuristics rather than identified genres.</p>
<p>The CAVA capture path and native rasterizer are unchanged.
<a href="../character/index.html">Earlier bass comparison</a> ·
<a href="../showcase/index.html">Earlier visual experiments</a></p></main></html>''')
    print(destination/'index.html')


if __name__ == '__main__':
    main()
