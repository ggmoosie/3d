"""profiles.py - side-profile rasters in the G frame (mm, y muzzle, z up) from the right-side reference silhouette (system python).

The photo alpha is resampled through the trace.py homography onto a 0.05 mm (y, z) grid, smoothed (grip edges more, the
pyramid texture bumps the silhouette by ~0.5 mm), and split into part regions:
  slide  : above the slide bottom line z 29.29 (a clean rectangle fills the ejection-port dip), plus the front lobe (y > 123)
           that wraps the guide rod under the barrel; the sights are separate regions
  frame  : below the slide line, behind the lobe, above the magazine split line, minus the trigger (hand-traced polygons)
  mag    : below the frame bottom line (magazine body + baseplate)
  barrel : the crown protruding beyond the slide face
Writes work/prof.npz: masks (uint8) and signed distance rasters (mm, negative inside) per region + grid origin/res.
Hand-traced pixel polylines (trigger, region split lines) are kept in PX below; everything else comes from the alpha."""
import json, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'work', 'trace.json'))); H = np.array(T['H']); Hinv = np.array(T['Hinv'])
RES = 0.05; Y0, Y1, Z0, Z1 = -72.0, 142.0, -96.0, 60.0
NY, NZ = int(round((Y1 - Y0) / RES)), int(round((Z1 - Z0) / RES))
ZSB = T['slide']['z_bot_rear']; ZST = T['slide']['z_top_rear']; YS0, YS1 = T['slide']['y0'], T['slide']['y1']

def px2g(pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ H.T; return p[:, :2] / p[:, 2:3]
def g2px(pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ Hinv.T; return p[:, :2] / p[:, 2:3]

# ------------------------------------------------------------------ hand-traced pixel polygons (read off pxgrid crops)
PX = dict(
    trigger_shoe=[(798, 380), (788, 428), (786, 446), (785, 460), (793, 485), (805, 505), (818, 518), (820, 537), (817, 543),
                  (800, 540), (776, 528), (762, 508), (751, 486), (741, 479), (740, 470), (734, 464), (690, 454), (696, 438),
                  (686, 426), (700, 392), (720, 376), (790, 374)],
    trigger_safety=[(786, 446), (800, 464), (812, 482), (830, 506), (840, 517), (841, 522), (836, 525), (818, 518), (805, 505),
                    (793, 485), (785, 460)],
    mag_split=[(40, 1038.9), (140, 1038.5), (420, 1036.0), (470, 1035.6)],      # frame bottom edge (frame above, magazine below)
    lobe_x=1439.0,                                                                # dust cover front end / slide front lobe
)

# ------------------------------------------------------------------ resample the alpha on the G grid
im = Image.open(os.path.join(HERE, '..', 'refs_user', 'g5_right_side.png')); A = np.asarray(im)[..., 3].astype(np.float32) / 255.0
A1 = ndimage.gaussian_filter(A, 1.0); A4 = ndimage.gaussian_filter(A, 3.5)
ys = Y0 + (np.arange(NY) + 0.5) * RES; zs = Z1 - (np.arange(NZ) + 0.5) * RES        # row 0 = top (z high)
YY, ZZ = np.meshgrid(ys, zs)
P = g2px(np.c_[YY.ravel(), ZZ.ravel()])
def sample(img, P):
    x = P[:, 0] - 0.5; v = P[:, 1] - 0.5                                         # pixel centres at +0.5
    return ndimage.map_coordinates(img, [v, x], order=1, mode='constant', cval=0.0)
a1 = sample(A1, P).reshape(NZ, NY); a4 = sample(A4, P).reshape(NZ, NY)
# grip region uses the heavier blur (pyramid bumps on the front/back strap silhouette); blend over 3 mm
wg = np.clip((-(ZZ) - 2.0) / 3.0, 0, 1) * np.clip((8.0 - YY) / 3.0, 0, 1)
alpha = a1 * (1 - wg) + a4 * wg
sil = alpha > 0.5

def poly_mask(px_pts):
    g = px2g(px_pts); img = Image.new('L', (NY, NZ), 0)
    ImageDraw.Draw(img).polygon([((y - Y0) / RES, (Z1 - z) / RES) for y, z in g], fill=255)
    return np.asarray(img) > 127
def line_z(px_pts, y):
    g = px2g(px_pts); return np.interp(y, g[:, 0], g[:, 1])

zsplit = line_z(PX['mag_split'], YY)
ylobe = px2g([(PX['lobe_x'], 300)])[0, 0]
trig = poly_mask(PX['trigger_shoe']) | poly_mask(PX['trigger_safety'])
shoe = poly_mask(PX['trigger_shoe']); safety = poly_mask(PX['trigger_safety'])
open_top = line_z([(680, 395), (720, 386), (800, 382), (940, 378)], YY)      # trigger-guard opening top (frame above)

slide_rect = (ZZ >= ZSB) & (ZZ <= ZST) & (YY >= YS0 + 1.5) & (YY <= YS1 - 1.5)
slide = ((sil & (ZZ >= ZSB) & (YY <= YS1 + 0.02)) | slide_rect)
lobe = sil & (YY >= ylobe) & (ZZ < ZSB) & (YY <= YS1 + 0.02)
rear_notch = (YY < YS0 + 0.7) & (ZZ < ZSB + 2.2)                               # frame shows behind the slide's rear-bottom notch
sights = sil & (ZZ > ZST + 0.05)
slide_body = (slide & ~sights & ~rear_notch) | lobe
# Clean analytic slide ends: the traced alpha edge wanders +-1 px along the rear / front faces, which showed as horizontal
# creases on the rear face at first-person distance.  Rear: straight face, 2.3 mm top-rear radius (photo), frame notch kept.
# Front: straight face, elliptical top-front nose (6.0 x 4.4 mm) and lobe bottom-front corner (2.5 x 4.0 mm), photo-measured.
def ell_in(Yc, Zc, a, b): return ((YY - Yc) / a) ** 2 + ((ZZ - Zc) / b) ** 2 <= 1.0
r = 2.3; rear = (YY < YS0 + 4.0) & (ZZ > ZSB - 0.01)
clean_r = (YY >= YS0) & (ZZ <= ZST) & (ZZ >= ZSB) & ~((YY < YS0 + r) & (ZZ > ZST - r) & ~ell_in(YS0 + r, ZST - r, r, r))
slide_body = np.where(rear, clean_r & ~rear_notch, slide_body)
zlb = 16.75                                             # lobe bottom (photo 16.45 .. 17.37 along the lobe)
front = ((YY > YS1 - 7.0) | ((YY >= ylobe) & (ZZ < ZSB))) & (ZZ > zlb - 1.5)
zbot = np.where(YY >= ylobe, zlb, ZSB)
clean_f = (YY <= YS1) & (ZZ <= ZST) & (ZZ >= zbot)
clean_f &= ~((YY > YS1 - 6.0) & (ZZ > ZST - 4.4) & ~ell_in(YS1 - 6.0, ZST - 4.4, 6.0, 4.4))
clean_f &= ~((YY > YS1 - 2.5) & (ZZ < zlb + 4.0) & ~ell_in(YS1 - 2.5, zlb + 4.0, 2.5, 4.0))
slide_body = np.where(front, clean_f, slide_body)
_k = int(round(0.6 / RES)); _disc = np.add.outer(np.arange(-_k, _k + 1) ** 2, np.arange(-_k, _k + 1) ** 2) <= _k * _k
slide_body = ndimage.binary_opening(slide_body, structure=_disc)          # 0.6 mm radius on every convex profile corner
frame = sil & (ZZ < ZSB) & (YY < ylobe) & (ZZ > zsplit)
frame |= sil & rear_notch & (ZZ > zsplit)
frame &= ~(trig & (ZZ < open_top - 0.15))
mag = sil & (ZZ <= zsplit)
barrel = sil & (YY > YS1 + 0.02)
rsight = sights & (YY < 0); fsight = sights & (YY > 0)
slide_body &= ~(barrel & (YY > YS1 + 0.02))

def sdf(m):
    """signed distance (mm), negative inside; half-pixel corrected"""
    din = ndimage.distance_transform_edt(m); dout = ndimage.distance_transform_edt(~m)
    return ((dout - din) * RES + np.where(m, 0.5 * RES, -0.5 * RES)).astype(np.float32) * 1.0
def biggest(m):
    lab, n = ndimage.label(m)
    if n <= 1: return m
    sz = ndimage.sum(m, lab, range(1, n + 1)); return lab == (1 + int(np.argmax(sz)))
frame = biggest(ndimage.binary_opening(frame, iterations=2))
# grip edges: the photo silhouette carries the pyramid texture as ~0.5 mm bumps on the front strap / backstrap.  Opening with a
# 0.9 mm disc removes them (base surface), +0.2 mm restores the mean; only below the frame's upper receiver.
# Per row, the rear/front edge positions are replaced by their base envelope (rolling extreme over 2.2 mm, i.e. the valleys
# between pyramids) smoothed (sigma 1 mm), pushed out 0.2 mm to sit at the mean of the texture.
def smooth_edge(frame, zlo, zhi, side):
    rows = [r for r in range(NZ) if zlo <= zs[r] <= zhi]
    e = []
    for r in rows:
        c = np.nonzero(frame[r])[0]
        if side == 'rear': e.append(ys[c.min()])
        else:
            # front strap: last filled column of the first run (the grip), before any gap
            run_end = c[np.nonzero(np.diff(c) > 1)[0][0]] if np.any(np.diff(c) > 1) else c.max(); e.append(ys[run_end])
    e = np.array(e); k = int(round(1.1 / RES))
    pad = np.pad(e, k, mode='edge'); win = np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1)
    base = win.max(1) if side == 'rear' else win.min(1)
    base = ndimage.gaussian_filter1d(base, 1.0 / RES, mode='nearest')
    base = base - 0.2 if side == 'rear' else base + 0.2
    for r, b, raw in zip(rows, base, e):
        if side == 'rear':
            frame[r, (ys < b)] = False; frame[r, (ys >= b) & (ys <= raw + 4.0)] = True
        else:
            frame[r, (ys > b) & (ys < raw + 4.0)] = False; frame[r, (ys <= b) & (ys >= raw - 4.0)] = True
    return frame
frame = smooth_edge(frame, -69.0, -7.0, "rear")
frame = smooth_edge(frame, -70.0, -16.0, "front")
barrel &= (ZZ > 31.5) & (ZZ < 47.5)
rsight = biggest(rsight); fsight = biggest(fsight)
out = dict(res=RES, y0=Y0, z1=Z1, ny=NY, nz=NZ, zsb=ZSB, zst=ZST, ys0=YS0, ys1=YS1, ylobe=ylobe)
for k, m in dict(slide=slide_body, frame=frame, mag=mag, barrel=barrel, rsight=rsight, fsight=fsight, shoe=shoe & ~safety,
                 safety=safety, trig=trig).items():
    out['m_' + k] = m.astype(np.uint8); out['d_' + k] = sdf(m)
np.savez_compressed(os.path.join(HERE, 'work', 'prof.npz'), **out)

def ext(m):
    zz, yy = np.nonzero(m); return (round(Y0 + yy.min() * RES, 2), round(Y0 + (yy.max() + 1) * RES, 2),
                                    round(Z1 - (zz.max() + 1) * RES, 2), round(Z1 - zz.min() * RES, 2))
for k in ('slide', 'frame', 'mag', 'barrel', 'rsight', 'fsight', 'trig'):
    print('PROFILE %-7s y %8.2f..%8.2f  z %8.2f..%8.2f' % ((k,) + ext(out['m_' + k] > 0)))
print('lobe y %.2f; trigger face (shoe front) at the photo row of z=2:' % ylobe)
row = int((Z1 - 2.0) / RES); cols = np.nonzero(trig[row])[0]; print('   trigger y %.2f..%.2f at z 2.0' % (Y0 + cols.min() * RES, Y0 + cols.max() * RES))
# preview
pv = np.zeros((NZ, NY, 3), np.uint8); pv[sil] = (60, 60, 60)
for k, c in (('slide', (70, 110, 200)), ('frame', (90, 160, 90)), ('mag', (200, 140, 60)), ('barrel', (200, 60, 60)),
             ('rsight', (220, 220, 60)), ('fsight', (220, 220, 60)), ('trig', (200, 80, 200))):
    pv[out['m_' + k] > 0] = c
Image.fromarray(pv).resize((NY // 3, NZ // 3)).save(os.path.join(HERE, 'work', 'prof_preview.png'))
print('PROFILES ok', NY, NZ)
