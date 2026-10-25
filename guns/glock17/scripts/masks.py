"""masks.py - texture-panel masks in the G side plane (y, z), traced on the right-side reference (system python).
Writes work/mask_side_R.png, work/mask_side_L.png (grip stud panels; the right one has the blank text plate cut out),
work/mask_thumb.png (frame thumb-rest panel) at 10 px/mm over y -72..142, z -96..60 (row 0 = z 60), and mask_meta.json.
Edges are crisp (1-px antialias only): the photo's panels have hard borders."""
import os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import g17v4_spec as G
HERE = os.path.dirname(os.path.abspath(__file__))
RES = 0.1; Y0, Y1, Z0, Z1 = -72.0, 142.0, -96.0, 60.0
W, H = int((Y1 - Y0) / RES), int((Z1 - Z0) / RES)
def gp(pts_g): return [((y - Y0) / RES, (Z1 - z) / RES) for y, z in pts_g]
def px(pts): return [tuple(p) for p in G.px2g(pts)]
SS = 4
def canvas(): return Image.new('L', (W * SS, H * SS), 0)
def poly(d, pts_g, fill): d.polygon([(u * SS, v * SS) for u, v in gp(pts_g)], fill=fill)
# grip side panel (px on the master photo): top edge v 328 from the seam forward, diagonal smooth transition into the guard,
# down the front strap (beyond the outline: the strap faces take their own mask), bottom edge above the smooth flare band
PANEL = px([(330, 328), (607, 328), (660, 445), (700, 560), (520, 944), (40, 952), (40, 328)])
MC = [(1.05, -1.14), (12.87, -5.11), (9.69, -14.62), (-2.13, -10.64)]
def grown(quad, g):
    c = np.mean(quad, 0); return [tuple(c + (np.array(p) - c) * (1 + g / np.linalg.norm(np.array(p) - c))) for p in quad]
PLATE = [(-45.7 - 0.4, -62.95 - 0.4), (-21.25 + 0.4, -62.95 - 0.4), (-21.25 + 0.4, -52.3 + 0.4), (-45.7 - 0.4, -52.3 + 0.4)]
for side in ('R', 'L'):
    im = canvas(); d = ImageDraw.Draw(im); poly(d, PANEL, 255); poly(d, grown(MC, 0.7), 0)
    if side == 'R': poly(d, PLATE, 0)
    im = im.resize((W, H), Image.LANCZOS); im.save(os.path.join(HERE, 'work', 'mask_side_%s.png' % side))
im = canvas(); d = ImageDraw.Draw(im)
poly(d, [(50.3, 27.8), (84.8, 28.0), (84.9, 24.7), (51.0, 19.7)], 255)
rr = 2.4; c = G.px2g([(777.5, 325.0)])[0]
im = im.resize((W, H), Image.LANCZOS); im.save(os.path.join(HERE, 'work', 'mask_thumb.png'))
json.dump(dict(res=RES, y0=Y0, y1=Y1, z0=Z0, z1=Z1, w=W, h=H, grid_pitch=2.2, grid_angle_deg=22.6,
               stud_top=0.9, stud_base=1.35, stud_height=0.5, strap_z=(-72.0, -14.5), backstrap_z=(-69.5, -4.5)),
          open(os.path.join(HERE, 'work', 'mask_meta.json'), 'w'), indent=1)
print('MASKS', W, H)
