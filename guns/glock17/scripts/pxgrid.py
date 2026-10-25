"""pxgrid.py - zoomed crop of a (private) reference photo with a labelled pixel grid, for reading landmark / edge pixels.
usage: python pxgrid.py <image> x0 y0 x1 y1 [scale] [step] [out.png]   (out defaults to v4/work/pxgrid.png; never commit)"""
import sys, os
from PIL import Image, ImageDraw, ImageFont
p = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6])
s = int(sys.argv[6]) if len(sys.argv) > 6 else 4; step = int(sys.argv[7]) if len(sys.argv) > 7 else 10
out = sys.argv[8] if len(sys.argv) > 8 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', 'pxgrid.png')
im = Image.open(p)
if im.mode == 'RGBA': im = Image.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 255)), im)
im = im.convert('RGB').crop((x0, y0, x1, y1)); im = im.resize((im.width * s, im.height * s), Image.NEAREST)
d = ImageDraw.Draw(im)
try: f = ImageFont.truetype('arial.ttf', 11)
except Exception: f = ImageFont.load_default()
for x in range((x0 // step + 1) * step, x1, step):
    X = (x - x0) * s; big = x % (step * 5) == 0
    d.line([(X, 0), (X, im.height)], fill=(255, 0, 0) if big else (255, 160, 160), width=1)
    if big: d.text((X + 2, 2), str(x), fill=(255, 0, 0), font=f)
for y in range((y0 // step + 1) * step, y1, step):
    Y = (y - y0) * s; big = y % (step * 5) == 0
    d.line([(0, Y), (im.width, Y)], fill=(0, 0, 255) if big else (160, 160, 255), width=1)
    if big: d.text((2, Y + 2), str(y), fill=(0, 0, 255), font=f)
im.save(out); print(out, im.size)
