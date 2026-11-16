#!/usr/bin/env python3
"""Render an honest audio-feature comparison and nine quiet/lively palettes."""
import math
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from character_score import character_score
from style_score import vocal_score
from render_showcase import TerminalImage, BACKGROUND
from pulse_tui.colors import AdaptiveColors
from pulse_tui.palettes import PALETTE_LABS, expressive_labs, lab_to_rgb
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options


def main():
    destination = ROOT/'docs/media/character'
    destination.mkdir(parents=True, exist_ok=True)
    painter = TerminalImage(64, 24)
    atlas = Image.new('RGB', (1080, 450), BACKGROUND)
    draw = ImageDraw.Draw(atlas)
    titles = ('Ember', 'Blue', 'Neon', 'Aurora', 'Crimson', 'Gold', 'Velvet', 'Sunset', 'Glacier')
    for i, (name, title) in enumerate(zip(PALETTE_LABS, titles)):
        x, y = (i % 3)*360, (i//3)*150
        draw.text((x+16, y+8), title.upper()+' / '+name, font=painter.text, fill=(200, 190, 220))
        for row, (amount, label) in enumerate([(0, 'quiet'), (1, 'lively')]):
            draw.text((x+16, y+43+row*43), label, font=painter.text, fill=(145, 135, 165))
            for k, lab in enumerate(expressive_labs(name, amount)):
                draw.rectangle((x+75+k*22, y+43+row*43, x+95+k*22, y+68+row*43), fill=lab_to_rgb(lab))
    atlas.save(destination/'atlas.png')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('ffmpeg is required to record the comparison')
    scenes = [Scene(), Scene()]
    renderers = [Renderer(), Renderer()]
    options = Options(hud=False)
    pipe = subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format', 'rgb24',
                             '-video_size', '1024x448', '-framerate', '24', '-i', '-', '-an',
                             '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                             '-movflags', '+faststart', str(destination/'demo.mp4')], stdin=subprocess.PIPE)
    gif = []
    try:
        for frame in range(34*24):
            now = frame/24
            amount = float(np.clip((now-24)/6, 0, 1))
            amount = amount*amount*(3-2*amount)
            for scene, kind in zip(scenes, ('rounded', 'driving')):
                spectrum = character_score(now, kind) + vocal_score(now, amount)
                scene.update(np.stack((spectrum, spectrum)), now, 1/24)
            if now < 22:
                continue
            image = Image.new('RGB', (1024, 448), BACKGROUND)
            draw = ImageDraw.Draw(image)
            for i, (scene, renderer, title) in enumerate(zip(scenes, renderers,
                    ('PITCHED / ROUNDED BASS', 'BROAD / PUNCHY BASS'))):
                rgb = scene.colors.palette()[8]
                text = f'{title}  |  {scene.colors.name.upper()}'
                draw.text((i*512+12, 8), text, font=painter.text, fill=rgb)
                draw.text((i*512+12, 27), 'Same 120 BPM; mids/highs rise without changing the bass.',
                          font=painter.text, fill=(150, 140, 170))
                lines = renderer.frame(scene, now, options, 64, 24, 'TEST SCORE', 24)
                image.paste(painter.draw(lines), (i*512, 48))
            draw.text((12, 430), 'Actual TUI renderer | generated spectra | no artist metadata or genre-labeled recordings',
                      font=painter.text, fill=(150, 140, 170))
            pipe.stdin.write(image.tobytes())
            if 24 <= now < 32 and frame % 2 == 0:
                gif.append(image)
            if frame == 32*24:
                image.save(destination/'comparison.png')
    finally:
        pipe.stdin.close()
        if pipe.wait()!=0:
            raise RuntimeError('Video encoding failed')
    samples=Image.new('RGB',(512,224*8),BACKGROUND)
    for i,image in enumerate(gif[::12]):
        samples.paste(image.resize((512,224)),(0,i*224))
    palette=samples.quantize(colors=48)
    indexed=[image.quantize(palette=palette,dither=Image.Dither.NONE) for image in gif]
    indexed[0].save(destination/'demo.gif',save_all=True,append_images=indexed[1:],loop=0,
                    duration=[80,80,90]*32,optimize=True,disposal=2)
    (destination/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Pulse · audio-only character</title>
<style>body{background:#080510;color:#d6cde4;font:16px/1.6 system-ui;margin:0}main{max-width:1100px;margin:auto;padding:30px}video,img{width:100%;display:block}a,code{color:#7fe0ec}h1,h2{font-weight:600}p{max-width:900px}</style>
<main><h1>Audio-only character · wider color expression</h1>
<p>Same tempo, different low-end timbres. Left: pitched/rounded bass stays warm.
Right: broad, punchy, regular bass favors Neon at 120 BPM. As mids and highs build,
each family becomes brighter and more colorful. These are controlled, generated
spectra rendered by the actual TUI, not recordings or proof of artist recognition.</p>
<video controls muted loop playsinline poster="comparison.png"><source src="demo.mp4" type="video/mp4"></video>
<p><a href="demo.gif">Animated GIF</a> · <a href="comparison.png">Full-size still</a></p>
<h2>Nine quiet-to-lively families</h2><img src="atlas.png" alt="Nine palette families, each shown at quiet and lively expression">
<p>Default: <code>party</code>. More expressive: <code>party --color-response 1.8</code>.
Lock a family with <code>--palette warm</code>, <code>neon</code>, <code>aurora</code>,
<code>crimson</code>, <code>gold</code>, <code>violet</code>, <code>sunset</code>,
<code>ice</code>, or <code>blue</code>. Press <code>p</code> to cycle them.</p>
<p>Automatic decisions estimate bass character, not actual artist or genre identity.
Unknown evidence holds the prior family; vocals above the bass band affect expression only.</p></main></html>''')
    print(destination/'index.html')


if __name__=='__main__':
    main()
