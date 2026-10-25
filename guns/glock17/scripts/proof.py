"""proof.py - bake-loss proof sheet: the same view rendered from the high-poly lookdev and from the baked game meshes,
side by side, plus 1:1 pixel crops of first-person-distance renders (no upscaling, so texel density is judged honestly).
usage: python proof.py out.jpg "title" --pair hi.png game.png label [--pair ...] [--crop hi.png game.png x0,y0,x1,y1 label ...]"""
import sys
from PIL import Image, ImageDraw, ImageFont
out, title = sys.argv[1], sys.argv[2]; a = sys.argv[3:]
pairs, crops = [], []
i = 0
while i < len(a):
    if a[i] == '--pair': pairs.append((a[i + 1], a[i + 2], a[i + 3])); i += 4
    elif a[i] == '--crop': crops.append((a[i + 1], a[i + 2], tuple(int(v) for v in a[i + 3].split(',')), a[i + 4])); i += 5
    else: i += 1
try: F = ImageFont.truetype('arial.ttf', 24); f = ImageFont.truetype('arial.ttf', 19)
except Exception: F = f = ImageFont.load_default()
W = 3000; half = (W - 10) // 2
rows = []
for h, g, lab in pairs:
    A = Image.open(h).convert('RGB'); B = Image.open(g).convert('RGB')
    A = A.resize((half, int(A.height * half / A.width)), Image.LANCZOS); B = B.resize((half, int(B.height * half / B.width)), Image.LANCZOS)
    rows.append(('pair', A, B, lab))
for h, g, box, lab in crops:
    A = Image.open(h).convert('RGB').crop(box); B = Image.open(g).convert('RGB').crop(box)
    rows.append(('crop', A, B, lab))
H = 60 + sum(max(r[1].height, r[2].height) + 34 for r in rows)
S = Image.new('RGB', (W, H), (24, 24, 26)); d = ImageDraw.Draw(S); d.text((14, 14), title, fill=(255, 210, 120), font=F)
y = 60
for kind, A, B, lab in rows:
    d.text((10, y + 6), lab + ('   [1:1 pixels, first-person distance]' if kind == 'crop' else ''), fill=(230, 230, 230), font=f)
    d.text((10, y + 6 + 0), '', fill=(0, 0, 0)); y += 30
    xa = 0 if kind == 'pair' else max(0, half - A.width); S.paste(A, (xa, y)); S.paste(B, (half + 10, y))
    d.text((xa + 8, y + 6), 'high-poly lookdev', fill=(255, 120, 120), font=f); d.text((half + 18, y + 6), 'game mesh + baked textures', fill=(120, 220, 255), font=f)
    y += max(A.height, B.height) + 4
S.save(out, quality=92); print('PROOF', out, S.size)
