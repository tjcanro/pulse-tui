#!/usr/bin/env python3
"""Record a compact four-scene GIF for PRs using the actual Braille renderer.

Development only: Pillow draws terminal glyphs; generated spectra supply the
same fixture to every scene. The live app remains CAVA-only.
"""
import argparse
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from preview_score import stereo_score
from render_showcase import BACKGROUND, TerminalImage
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import Options, SCENES, SCENE_LABELS

PALETTES = dict(terrain='neon', ribbons='warm', orbit='gold', filaments='blue')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/media/scenes/overview.gif')
    parser.add_argument('--seconds', type=int, default=4)
    parser.add_argument('--fps', type=int, choices=(8,12,24), default=12)
    parser.add_argument('--columns', type=int, default=48)
    parser.add_argument('--rows', type=int, default=16)
    args = parser.parse_args()
    if not 1<=args.seconds<=20 or not 28<=args.columns<=100 or not 12<=args.rows<=40:
        parser.error('Use 1–20 seconds, 28–100 columns and 12–40 rows')

    painter = TerminalImage(args.columns, args.rows)
    title = ImageFont.truetype(painter.text.path, 15)
    gap, header, footer = 8, 30, 24
    width = painter.width*2+gap
    height = (painter.height+header)*2+gap+footer
    template = Image.new('RGB', (width,height), BACKGROUND)
    draw = ImageDraw.Draw(template)
    for i,name in enumerate(SCENES):
        x, y = (i%2)*(painter.width+gap), (i//2)*(painter.height+header+gap)
        draw.text((x+10,y+6), SCENE_LABELS[name]+' · '+PALETTES[name].title(),
                  font=title, fill=(240,215,190))
    draw.text((10,height-footer+4), f'Actual terminal renderer · generated stereo spectra · {args.fps} fps',
              font=painter.text, fill=(180,163,192))
    audio, frames = Scene(), []
    renderers = {name:Renderer() for name in SCENES}
    options = {name:Options(scene=name,palette=PALETTES[name],hud=False) for name in SCENES}
    simulation_fps, warmup = 24, 12
    stride = simulation_fps//args.fps
    for frame in range((warmup+args.seconds)*simulation_fps):
        now = frame/simulation_fps
        audio.update(stereo_score(now), now, 1/simulation_fps)
        if now<warmup or frame%stride:
            continue
        canvas = template.copy()
        for i,name in enumerate(SCENES):
            lines = renderers[name].frame(audio,now,options[name],args.columns,args.rows,
                                          'GENERATED SPECTRA',simulation_fps)
            x, y = (i%2)*(painter.width+gap), (i//2)*(painter.height+header+gap)+header
            canvas.paste(painter.draw(lines),(x,y))
        frames.append(canvas)

    # One palette for the entire clip avoids per-frame quantization flicker.
    samples = frames[::max(1,len(frames)//6)][:6]
    strip = Image.new('RGB',(width,height*len(samples)),BACKGROUND)
    for i,frame in enumerate(samples):
        strip.paste(frame,(0,i*height))
    palette = strip.quantize(colors=96)
    indexed = [frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    # GIF delays have 10 ms precision: alternate delays to retain the right FPS.
    delays = [10*(round((i+1)*100/args.fps)-round(i*100/args.fps)) for i in range(len(frames))]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    indexed[0].save(args.output,save_all=True,append_images=indexed[1:],loop=0,
                    duration=delays,disposal=2,optimize=True)
    print(f'{args.output}: {width}×{height}, {len(frames)} frames, '
          f'{sum(delays)/1000:g}s, {args.output.stat().st_size/1024:.0f} KiB')


if __name__ == '__main__':
    main()
