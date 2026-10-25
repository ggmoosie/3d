"""trace.py - photo -> G-frame mapping and silhouette trace from the near-orthographic right-side reference (system python).

The G frame is the game frame in mm with UE axes (+X gun left, +Y muzzle, +Z up; origin = contract frame origin).
The photo (g5_right_side.png, alpha = gun) is a long-lens product render, slightly perspective (slide rear 164 px tall, front
159.5 px).  A homography maps photo pixels to the gun's mid-plane (y, z):
  * the slide outline (top silhouette line, bottom edge line, rear face, front face) is a rectangle in the gun,
  * the rectangle's length/height ratio is the photo's at mid-slide, its size is set so the overall silhouette length
    (rearmost point -> barrel crown) is 202 mm (the real OAL),
  * the barrel crown centre lands on the contract muzzle (y 137.4) and the bore axis (z 39.5).
Writes work/trace.json (homography, contours in G mm) and work/trace_grid.png (photo with a 5 mm G grid; private, local only).
usage: python trace.py"""
import json, os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'refs_user', 'g5_right_side.png')
OAL = 202.0
MUZZLE = (137.4, 39.5)          # contract Muzzle socket (y, z), bore axis z

im = Image.open(REF); A = np.asarray(im).astype(np.float32)
alpha = A[..., 3] / 255.0; H_, W_ = alpha.shape
gray = A[..., :3].mean(2)

def col_top(x):
    """sub-pixel first alpha>0.5 crossing from the top in column x"""
    c = alpha[:, x]; i = int(np.argmax(c > 0.5))
    if i == 0: return None
    return (i - 1) + (0.5 - c[i - 1]) / max(1e-6, c[i] - c[i - 1])

# ---- slide top line: silhouette top over plain slide-top stretches (no sights, no port hood, no nose)
xs_top = [x for x in list(range(270, 700, 4)) + list(range(950, 1440, 4))]
top = np.array([(x, col_top(x)) for x in xs_top]); kt = np.polyfit(top[:, 0], top[:, 1], 1)
# ---- slide bottom edge: first dark row (the slide/frame parting shadow line) below the slide side face, per column
def bottom_edge(x):
    c = gray[230:256, x]; i = int(np.argmax(c < 45)); return 230 + i - 0.5
xs_bot = list(range(170, 250, 4)) + list(range(560, 700, 4)) + list(range(950, 1150, 4)) + list(range(1460, 1490, 2))
bot = np.array([(x, bottom_edge(x)) for x in xs_bot]); kb = np.polyfit(bot[:, 0], bot[:, 1], 1)
res_b = bot[:, 1] - np.polyval(kb, bot[:, 0]); keep = np.abs(res_b) < 1.5; kb = np.polyfit(bot[keep, 0], bot[keep, 1], 1)
# ---- rear face (x where alpha crosses in rows 110..205) and front face (rows 225..245, below the barrel)
def row_left(v):
    r = alpha[v, :]; i = int(np.argmax(r > 0.5)); return (i - 1) + (0.5 - r[i - 1]) / max(1e-6, r[i] - r[i - 1])
def row_right(v):
    r = alpha[v, ::-1]; i = int(np.argmax(r > 0.5)); xi = (i - 1) + (0.5 - r[i - 1]) / max(1e-6, r[i] - r[i - 1]); return W_ - 1 - xi
rear = np.array([(row_left(v), v) for v in range(110, 205, 3)])
front = np.array([(row_right(v), v) for v in range(226, 244, 2)])
xr = float(np.median(rear[:, 0])); xf = float(np.median(front[:, 0]))
print('top line v = %.5f x + %.2f   bottom line v = %.5f x + %.2f   rear x %.2f  front x %.2f' % (kt[0], kt[1], kb[0], kb[1], xr, xf))
corners_px = np.array([(xr, np.polyval(kt, xr)), (xf, np.polyval(kt, xf)), (xf, np.polyval(kb, xf)), (xr, np.polyval(kb, xr))])
h_rear = corners_px[3, 1] - corners_px[0, 1]; h_front = corners_px[2, 1] - corners_px[1, 1]
print('slide px: length %.1f  height rear %.1f front %.1f' % (xf - xr, h_rear, h_front))

def homography(src, dst):
    M = []
    for (x, y), (u, v) in zip(src, dst):
        M.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u]); M.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, Vt = np.linalg.svd(np.array(M)); Hm = Vt[-1].reshape(3, 3); return Hm / Hm[2, 2]

def apply(Hm, pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ Hm.T; return p[:, :2] / p[:, 2:3]

# silhouette contours (outer + holes), px
cs = measure.find_contours(alpha, 0.5)
cs = sorted(cs, key=len, reverse=True)
def solve(scale_len):
    L = scale_len; Hh = L * (0.5 * (h_rear + h_front)) / (xf - xr)
    dst = np.array([(0.0, Hh), (L, Hh), (L, 0.0), (0.0, 0.0)])          # (y, z): rear-top, front-top, front-bottom, rear-bottom
    Hm = homography(corners_px, dst)
    # crown: rightmost silhouette at the bore rows; bore row = middle of the protruding barrel run
    cols = [x for x in range(int(xf) + 2, W_) if alpha[:, x].max() > 0.5]
    xc = max(cols); runs = np.nonzero(alpha[:, int(xf) + 4] > 0.5)[0]; vbore = 0.5 * (runs.min() + runs.max())
    crown = apply(Hm, [(xc + 0.5, vbore)])[0]
    T = np.array([[1, 0, MUZZLE[0] - crown[0]], [0, 1, MUZZLE[1] - crown[1]], [0, 0, 1]]); Hm = T @ Hm
    outer = apply(Hm, cs[0][:, ::-1])
    oal = MUZZLE[0] - outer[:, 0].min()
    return Hm, oal, (xc, vbore), dst
# similarity (the matched camera is ~orthographic: focal 2600 mm; a projective fit to the slide's slight 0.4 mm
# top/bottom convergence put 10 px errors on the grip): rotation = mean slide axis, uniform scale = OAL 202 mm, crown on the
# contract muzzle
ang = math.atan(0.5 * (kt[0] + kb[0]))
cols = [x for x in range(int(xf) + 2, W_) if alpha[:, x].max() > 0.5]
xc = max(cols); runs = np.nonzero(alpha[:, int(xf) + 4] > 0.5)[0]; vbore = 0.5 * (runs.min() + runs.max())
crown_px = (xc + 0.5, vbore)
ca, sa = math.cos(-ang), math.sin(-ang)
outer_px = cs[0][:, ::-1]
q = (outer_px - np.array(crown_px)) @ np.array([[ca, -sa], [sa, ca]]).T
k = OAL / (q[:, 0].max() - q[:, 0].min())
# G = (Y0 + k*(R(p - c)).x , Z0 - k*(R(p - c)).y) as a 3x3 matrix
Rm = np.array([[ca, -sa], [sa, ca]]); A2 = np.diag([k, -k]) @ Rm
t = np.array([MUZZLE[0], MUZZLE[1]]) - A2 @ np.array(crown_px)
Hm = np.array([[A2[0, 0], A2[0, 1], t[0]], [A2[1, 0], A2[1, 1], t[1]], [0, 0, 1.0]])
oal = OAL; L = (xf - xr) * k
cg = apply(Hm, corners_px)
Hh = 0.5 * ((cg[0, 1] - cg[3, 1]) + (cg[1, 1] - cg[2, 1]))
print('similarity: rot %.3f deg, %.5f mm/px; slide length %.2f mm, height %.2f mm (rear %.2f front %.2f)' % (math.degrees(ang), k, L, Hh, cg[0, 1] - cg[3, 1], cg[1, 1] - cg[2, 1]))
Hinv = np.linalg.inv(Hm); Hinv /= Hinv[2, 2]
print('slide corners G (y,z):', np.round(cg, 2).tolist())
zt_mean = 0.5 * (cg[0, 1] + cg[1, 1]); zb_mean = 0.5 * (cg[2, 1] + cg[3, 1])
contours = [apply(Hm, c[:, ::-1]).tolist() for c in cs if len(c) > 40]
mmpx = [float(np.linalg.norm(apply(Hm, [(x + 1, 160)])[0] - apply(Hm, [(x, 160)])[0])) for x in (200, 800, 1500)]
print('mm/px at x 200/800/1500:', np.round(mmpx, 5))
json.dump(dict(H=Hm.tolist(), Hinv=Hinv.tolist(), slide=dict(y0=float(cg[0, 0]), y1=float(cg[1, 0]), z_top_rear=float(zt_mean),
          z_bot_rear=float(zb_mean), length=L, height=Hh), oal=oal, crown_px=list(crown_px), contours=contours,
          top_line=list(kt), bottom_line=list(kb), xr=xr, xf=xf),
          open(os.path.join(HERE, 'work', 'trace.json'), 'w'))

# grid overlay: G mm grid (5 mm, labelled every 10) projected into the photo
img = Image.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 255)), im.convert('RGBA')).convert('RGB')
big = img.resize((W_ * 2, H_ * 2), Image.LANCZOS); d = ImageDraw.Draw(big)
try: f = ImageFont.truetype('arial.ttf', 14)
except Exception: f = ImageFont.load_default()
for y in range(-70, 145, 5):
    p = apply(Hinv, [(y, -95), (y, 70)]) * 2
    d.line([tuple(p[0]), tuple(p[1])], fill=(255, 0, 0) if y % 10 == 0 else (255, 170, 170), width=1)
    if y % 10 == 0:
        for zz in (-90, -40, 10, 60):
            q = apply(Hinv, [(y, zz)])[0] * 2; d.text((q[0] + 2, q[1]), str(y), fill=(220, 0, 0), font=f)
for z in range(-95, 75, 5):
    p = apply(Hinv, [(-70, z), (145, z)]) * 2
    d.line([tuple(p[0]), tuple(p[1])], fill=(0, 0, 255) if z % 10 == 0 else (170, 170, 255), width=1)
    if z % 10 == 0:
        for yy in (-65, 0, 60, 120):
            q = apply(Hinv, [(yy, z)])[0] * 2; d.text((q[0] + 2, q[1] + 1), str(z), fill=(0, 0, 220), font=f)
big.save(os.path.join(HERE, 'work', 'trace_grid.png'))
print('TRACE ok; contours', [len(c) for c in contours])
