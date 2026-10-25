"""silcam.py - camera refinement on the silhouette (system python): maximise IoU between the photo's object mask and the
model's projected silhouette (dense surface points splatted + closed), starting from a camera_match.py solution.
Same camera model as camera_match.py (Rodrigues rotation, position, focal on a 36 mm sensor-width).  Also reports the
landmark residuals of the refined camera, which separates bad landmarks from real shape differences.
usage: python silcam.py <match.json> <high.npz> <out.json> [--lm-weight w] [--parts frame,slide,...]"""
import sys, json, math, os
import numpy as np
from PIL import Image
from scipy import ndimage, optimize
a = [x for x in sys.argv[1:] if not x.startswith('--')]
J = json.load(open(a[0])); D = np.load(a[1]); out = a[2]
LW = float(sys.argv[sys.argv.index('--lm-weight') + 1]) if '--lm-weight' in sys.argv else 0.0
ref = np.asarray(Image.open(J['reference']).convert('RGB')).astype(np.float32); H0, W0 = ref.shape[:2]
SC = 0.5; W, H = int(W0 * SC), int(H0 * SC)
# photo mask: distance from the border colour, as ref_compare.py does
i0 = max(2, int(0.015 * min(H0, W0))); i1 = i0 + 6
border = np.concatenate([ref[i0:i1].reshape(-1, 3), ref[-i1:-i0].reshape(-1, 3), ref[:, i0:i1].reshape(-1, 3), ref[:, -i1:-i0].reshape(-1, 3)])
bg = np.median(border, 0); dist = np.linalg.norm(ref - bg, axis=2)
pm = ndimage.median_filter(dist > 30.0, 5)
pm = np.asarray(Image.fromarray(pm.astype(np.uint8) * 255).resize((W, H), Image.BILINEAR)) > 127
names = sorted({k.split('__')[0] for k in D.files})
pts = np.concatenate([D[n + '__V'] for n in names if n not in ('guiderod', 'follower', 'lockblock', 'housing')]).astype(np.float64)
pts = pts[::2] * np.array([0.001, -0.001, 0.001])                       # G mm -> Blender m
SENSOR = 36.0
def rod(r):
    th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K
def project(x, P, w, h):
    R = rod(x[:3]); t = x[3:6]; f = x[6] / SENSOR * w; pc = (P - t) @ R; z = -pc[:, 2]
    return np.stack([w / 2 + f * pc[:, 0] / z, h / 2 - f * pc[:, 1] / z], 1)
def render_mask(x):
    uv = project(x, pts, W, H); u = np.round(uv[:, 0]).astype(int); v = np.round(uv[:, 1]).astype(int)
    ok = (u >= 0) & (u < W) & (v >= 0) & (v < H); m = np.zeros((H, W), bool); m[v[ok], u[ok]] = True
    m = ndimage.binary_closing(m, iterations=2); return ndimage.binary_fill_holes(m) if False else m
LMP = np.array([p['world'] for p in J['points']]); LMUV = np.array([p['px'] for p in J['points']], float)
solve = np.array([not p.get('check') for p in J['points']])
def lm_err(x):
    uv = project(x, LMP, W0, H0); return np.linalg.norm(uv - LMUV, axis=1)
def cost(x):
    m = render_mask(x); iou = (m & pm).sum() / max(1, (m | pm).sum())
    return (1 - iou) + LW * float(np.sqrt((lm_err(x)[solve] ** 2).mean())) / W0
x0 = np.array(J['x0']) if 'x0' in J else None
if x0 is None: sys.exit('silcam: put the camera_match solution vector in json key x0')
print('start IoU %.4f' % (1 - cost(x0) + LW * 0), 'lm rms %.1f' % np.sqrt((lm_err(x0)[solve] ** 2).mean()))
best = x0
for it in range(3):
    r = optimize.minimize(cost, best, method='Powell', options=dict(maxiter=4000, xtol=1e-5, ftol=1e-6))
    best = r.x; print('pass', it, 'cost %.4f' % r.fun)
m = render_mask(best); iou = (m & pm).sum() / max(1, (m | pm).sum())
e = lm_err(best)
for p, ee, uv in zip(J['points'], e, project(best, LMP, W0, H0)):
    print('SIL point %-16s %s err %6.1f px  (model %4.0f,%4.0f photo %4.0f,%4.0f)' % (p['name'], 'check' if p.get('check') else 'solve', ee, uv[0], uv[1], p['px'][0], p['px'][1]))
print('SIL IoU %.4f  landmark rms %.1f px  focal %.1f' % (iou, np.sqrt((e[solve] ** 2).mean()), best[6]))
json.dump(dict(x=best.tolist(), iou=float(iou), W=W0, H=H0), open(out, 'w'))
