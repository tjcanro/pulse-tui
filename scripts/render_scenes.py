#!/usr/bin/env python3
"""Record the actual terminal scene renderer, using a procedural stereo score.

Offline development tool, not an app mode. Pillow/ffmpeg are preview tools only.
"""
import argparse
import html
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from preview_score import stereo_score
from render_showcase import TerminalImage, BACKGROUND
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options, SCENE_LABELS, PALETTES, CAMERAS

DESCRIPTIONS = {
    'ribbons': 'Broad sheets and narrow strands taper, weave over and under each other, and carry travelling bends, twists, ribs and edge marks.',
    'orbit': 'A dense central field of broken arcs. Fading fragments expand from the center toward the margins; bass launches outward light fronts.',
    'filaments': 'Finite strands stream through an S-shaped current at varied speeds, with rolling eddies and fading heads and tails.',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/media/scenes')
    parser.add_argument('--seconds', type=int, default=8)
    parser.add_argument('--stills-only', action='store_true')
    parser.add_argument('--palette', choices=PALETTES, default='warm')
    parser.add_argument('--camera', choices=CAMERAS, default='choreo')
    parser.add_argument('--scenes', nargs='+', choices=tuple(DESCRIPTIONS), default=list(DESCRIPTIONS))
    parser.add_argument('--columns', type=int, default=160)
    parser.add_argument('--rows', type=int, default=48)
    args = parser.parse_args()
    if args.columns<28 or args.rows<12 or args.seconds<1:
        parser.error('Use at least 28 columns, 12 rows, and one second')
    ffmpeg = shutil.which('ffmpeg')
    if not args.stills_only and not ffmpeg:
        parser.error('ffmpeg is required for video previews')
    args.output.mkdir(parents=True, exist_ok=True)
    cols, rows, fps, start = args.columns, args.rows, 24, 12
    painter = TerminalImage(cols, rows)
    for name, description in DESCRIPTIONS.items():
        if name not in args.scenes:
            continue
        audio, renderer = Scene(), Renderer()
        options = Options(scene=name, palette=args.palette, camera=args.camera, hud=False)
        pipe = None
        if not args.stills_only:
            pipe = subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo',
                '-pixel_format', 'rgb24', '-video_size', f'{cols*8}x{rows*16}',
                '-framerate', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
                '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart', str(args.output/(name+'.mp4'))], stdin=subprocess.PIPE)
        gif_frames = []
        try:
            for frame in range((start+args.seconds)*fps):
                now = frame/fps
                audio.update(stereo_score(now), now, 1/fps)
                still = frame == (start+args.seconds//2)*fps
                if not still and (now<start or pipe is None):
                    continue
                image = painter.draw(renderer.frame(audio, now, options, cols, rows,
                                                     'GENERATED SPECTRA', fps))
                if pipe:
                    pipe.stdin.write(image.tobytes())
                    if frame % 3 == 0:
                        gif_frames.append(image)
                if still:
                    image.save(args.output/(name+'.png'))
        finally:
            if pipe:
                pipe.stdin.close()
                if pipe.wait()!=0:
                    raise RuntimeError('Could not encode '+name)
        if gif_frames:
            # Each GIF retains its own stable palette for flicker-free previews.
            samples = Image.new('RGB', (640, 384*4), BACKGROUND)
            for i, image in enumerate(gif_frames[::max(1, len(gif_frames)//4)][:4]):
                samples.paste(image.resize((640,384)), (0, i*384))
            palette = samples.quantize(colors=48)
            frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in gif_frames]
            frames[0].save(args.output/(name+'.gif'), save_all=True, append_images=frames[1:],
                           loop=0, duration=125, disposal=2, optimize=True)
        print('Rendered '+name, flush=True)
    # Preserve existing scene clips when regenerating only selected geometry.
    cards, thumbs = [], []
    for name, description in DESCRIPTIONS.items():
        poster = args.output/(name+'.png')
        if not poster.exists():
            continue
        with Image.open(poster) as original:
            small = original.copy()
        small.thumbnail((640,384))
        tile = Image.new('RGB', (640,420), BACKGROUND)
        ImageDraw.Draw(tile).text((12,9), SCENE_LABELS[name].upper(), font=painter.text, fill=(245,192,120))
        tile.paste(small, ((640-small.width)//2, 36+(384-small.height)//2))
        thumbs.append(tile)
        if (args.output/(name+'.mp4')).exists() and not args.stills_only:
            media = f'<video controls muted loop playsinline poster="{name}.png"><source src="{name}.mp4" type="video/mp4"></video>'
        else:
            media = f'<img src="{name}.png" alt="{SCENE_LABELS[name]}">'
        cards.append(f'<article><h2>{SCENE_LABELS[name]}</h2>{media}<p>{html.escape(description)}</p><code>party --scene {name}</code><p><a href="{name}.png">Still</a></p></article>')
    contact = Image.new('RGB', (640, 420*len(thumbs)), BACKGROUND)
    for i, thumb in enumerate(thumbs):
        contact.paste(thumb, (0, 420*i))
    contact.save(args.output/'comparison.png')
    (args.output/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pulse · live terminal scenes</title>
<style>body{margin:0;background:#080510;color:#e6d9ee;font:16px/1.6 system-ui}main{max-width:1400px;margin:auto;padding:32px}h1,h2{color:#f6c47c}video,img{width:100%;height:auto;display:block}article{border:1px solid #382d40;border-radius:12px;padding:20px;margin:28px 0}a,code{color:#8ae4ee}p{max-width:1000px}</style><main><h1>Pulse · three new terminal scenes</h1><p>Actual Braille-renderer output at 24 fps, driven by the same generated stereo spectrum score. These are implementation previews, not AI concept images or recordings of songs. Palette is Warm for comparison with the reference; Auto and all existing palettes also work.</p><p>Press <code>s</code> for the next scene or <code>Shift+s</code> for the previous one: Terrain → Endless Ribbons → Orbital Fragments → Filament Current. <code>v</code> changes looks, <code>p</code> colors, <code>c</code> cameras, and <code>[</code>/<code>]</code> detail. Scene switching preserves your settings.</p>'''+''.join(cards)+'''<p><a href="comparison.png">Comparison still</a>. Runtime dependencies remain CAVA and NumPy; no player integration or shader support is needed.</p></main></html>''')
    print(args.output/'index.html')


if __name__ == '__main__':
    main()
