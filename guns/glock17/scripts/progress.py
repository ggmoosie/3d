"""progress.py - progress sheet: beauty renders (+ exploded) + the latest matched diff sheet(s) -> review/progress_<hhmm>.jpg,
and one line appended to review/PROGRESS.md.
usage: python progress.py "<stage title>" "<one-line what changed>" img1[::label] img2 ... --diff diff1_sheet.jpg [diff2 ...]"""
import sys, os, time
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); REV = os.path.join(HERE, 'review')
title, line = sys.argv[1], sys.argv[2]
rest = sys.argv[3:]
diffs = rest[rest.index('--diff') + 1:] if '--diff' in rest else []
imgs = rest[:rest.index('--diff')] if '--diff' in rest else rest
try: F = ImageFont.truetype('arial.ttf', 26); f = ImageFont.truetype('arial.ttf', 20)
except Exception: F = f = ImageFont.load_default()
W = 3000; cols = 3; cw = W // cols
tiles = []
for a in imgs:
    p, lab = (a.split('::') + [''])[:2]
    im = Image.open(p).convert('RGB'); im = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS); tiles.append((im, lab or os.path.basename(p)))
rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
rh = [max(t[0].height for t in r) for r in rows]
dims = []
for d in diffs:
    im = Image.open(d).convert('RGB'); im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS); dims.append((im, os.path.basename(d)))
H = 60 + sum(rh) + sum(im.height + 36 for im, _ in dims)
S = Image.new('RGB', (W, H), (24, 24, 26)); d = ImageDraw.Draw(S)
stamp = time.strftime('%Y-%m-%d %H:%M')
d.text((14, 14), 'G17 Gen5 v4 - %s - %s' % (title, stamp), fill=(255, 210, 120), font=F)
y = 60
for r, h in zip(rows, rh):
    for i, (im, lab) in enumerate(r):
        S.paste(im, (i * cw, y)); d.text((i * cw + 10, y + 8), lab, fill=(200, 40, 40), font=f)
    y += h
for im, lab in dims:
    d.text((10, y + 6), 'matched-camera diff: ' + lab, fill=(255, 210, 120), font=f); S.paste(im, (0, y + 36)); y += im.height + 36
hhmm = time.strftime('%H%M'); out = os.path.join(REV, 'progress_%s.jpg' % hhmm)
S.save(out, quality=90)
with open(os.path.join(REV, 'PROGRESS.md'), 'a', encoding='utf-8') as fh:
    if fh.tell() == 0: fh.write('# G17 Gen5 v4 progress\n\n')
    fh.write('- %s `progress_%s.jpg` (%s): %s\n' % (stamp, hhmm, title, line))
print('PROGRESS', out, S.size)
