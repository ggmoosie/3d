"""ingame_sheet.py - the final in-game progress sheet: PIE frames (+ icon, hand-fit renders) -> review/ingame_<hhmm>.jpg, one line in
review/PROGRESS.md.  Frames are copied into review/ingame/ first (full size kept there).
usage: python ingame_sheet.py "<one-line summary>" img1[::label] img2[::label] ..."""
import sys, os, time, shutil
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); REV = os.path.join(HERE, 'review'); IG = os.path.join(REV, 'ingame'); os.makedirs(IG, exist_ok=True)
line = sys.argv[1]; args = sys.argv[2:]
try: F = ImageFont.truetype('arial.ttf', 28); f = ImageFont.truetype('arial.ttf', 22)
except Exception: F = f = ImageFont.load_default()
W = 3200; cols = 3; cw = W // cols; tiles = []
for a in args:
    p, lab = (a.split('::') + [''])[:2]
    dst = os.path.join(IG, os.path.basename(p))
    if os.path.abspath(p) != os.path.abspath(dst): shutil.copy2(p, dst)
    im = Image.open(p).convert('RGB')
    if im.width / im.height > 2.2: im = im.crop(((im.width - int(im.height * 16 / 9)) // 2, 0, (im.width + int(im.height * 16 / 9)) // 2, im.height))
    im = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS); tiles.append((im, lab or os.path.splitext(os.path.basename(p))[0]))
rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]; rh = [max(t[0].height for t in r) for r in rows]
S = Image.new('RGB', (W, 64 + sum(rh) + 8 * len(rows)), (22, 22, 24)); d = ImageDraw.Draw(S)
stamp = time.strftime('%Y-%m-%d %H:%M'); d.text((16, 16), 'G17 Gen5 v4 - in game (UE 5.5 PIE) - %s' % stamp, fill=(255, 210, 120), font=F)
y = 64
for r, h in zip(rows, rh):
    for i, (im, lab) in enumerate(r):
        S.paste(im, (i * cw, y)); d.rectangle((i * cw + 6, y + 6, i * cw + 14 + d.textlength(lab, font=f), y + 38), fill=(0, 0, 0)); d.text((i * cw + 10, y + 8), lab, fill=(255, 140, 60), font=f)
    y += h + 8
name = 'ingame_%s.jpg' % time.strftime('%H%M'); S.save(os.path.join(REV, name), quality=92)
open(os.path.join(REV, 'PROGRESS.md'), 'a', encoding='utf-8').write('- %s `%s` (final: in game): %s\n' % (stamp, name, line))
print('SHEET', os.path.join(REV, name), S.size)
