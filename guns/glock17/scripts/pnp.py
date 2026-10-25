"""pnp.py - robust camera solve for a camera_match.py JSON (system python): DLT (3x4 projection from >= 6 points)
-> decomposition (K, R, t) -> Levenberg-Marquardt on rotation, position and focal with the principal point fixed at
the image centre (camera_match.py's model).  Many random restarts around the DLT pose; the best solution is written
back into the JSON as 'x0' (rodrigues, position, focal mm), so bl_refcam.py can build the camera.
With --shift the principal point is solved too (cropped product images): 'x0' then has 9 values (+ cx, cy in px), which
bl_refcam.py turns into Blender lens shift.
usage: python pnp.py <match.json> [--drop name,name] [--fix-focal F] [--shift]"""
import sys, json, math
import numpy as np
from PIL import Image
J = json.load(open(sys.argv[1])); W, H = Image.open(J['reference']).size
drop = set(sys.argv[sys.argv.index('--drop') + 1].split(',')) if '--drop' in sys.argv else set()
SHIFT = '--shift' in sys.argv
FIXF = float(sys.argv[sys.argv.index('--fix-focal') + 1]) if '--fix-focal' in sys.argv else None
pts = [p for p in J['points'] if p['name'] not in drop]
P_all = np.array([p['world'] for p in pts]); UV_all = np.array([p['px'] for p in pts], float)
sol = np.array([not p.get('check') for p in pts]); P, UV = P_all[sol], UV_all[sol]
SENSOR = 36.0
def rod(r):
    th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K
def irod(R):
    ang = math.acos(max(-1, min(1, (np.trace(R) - 1) / 2)))
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if np.linalg.norm(w) < 1e-9:
        if ang < 1e-6: return np.zeros(3)
        wv, V = np.linalg.eigh((R + R.T) / 2); v = V[:, np.argmax(wv)]; return v * ang
    return w / np.linalg.norm(w) * ang
NP = 9 if SHIFT else 7
def project(x, P):
    R = rod(x[:3]); t = x[3:6]; f = x[6] / SENSOR * W; pc = (P - t) @ R; z = -pc[:, 2]
    z = np.where(np.abs(z) < 1e-9, 1e-9, z)
    cx, cy = (x[7], x[8]) if len(x) > 7 else (W / 2, H / 2)
    return np.stack([cx + f * pc[:, 0] / z, cy - f * pc[:, 1] / z], 1), z
def resid(x, P=None, UV=None):
    P = P if P is not None else globals()['P']; UV = UV if UV is not None else globals()['UV']
    uv, z = project(x, P); return np.concatenate([(uv - UV).ravel(), 1e3 * np.minimum(z, 0)])
def lm(x, iters=400):
    lam = 1e-2; free = np.ones(len(x), bool); free[6] = FIXF is None
    if len(x) > 7 and '--cy-only' in sys.argv: free[7] = False
    for it in range(iters):
        r = resid(x); Jm = np.zeros((len(r), len(x)))
        for k in np.where(free)[0]:
            h = 1e-6 * max(1.0, abs(x[k])); xp = x.copy(); xp[k] += h; Jm[:, k] = (resid(xp) - r) / h
        idx = np.where(free)[0]; A = Jm[:, idx].T @ Jm[:, idx]; g = Jm[:, idx].T @ r
        step = np.zeros(len(x)); step[idx] = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
        xn = x + step; xn[6] = min(max(8.0, xn[6]), 3000.0)
        if (resid(xn) ** 2).sum() < (r ** 2).sum(): x, lam = xn, lam * 0.3
        else: lam *= 10
        if lam > 1e12 or np.linalg.norm(step) < 1e-12: break
    return x
# ---- DLT: camera_match convention -> pixel (u, v) with v down; build normalized DLT
def dlt(P, UV):
    A = []
    for (X, Y, Z), (u, v) in zip(P, UV):
        A.append([X, Y, Z, 1, 0, 0, 0, 0, -u * X, -u * Y, -u * Z, -u]); A.append([0, 0, 0, 0, X, Y, Z, 1, -v * X, -v * Y, -v * Z, -v])
    _, _, Vt = np.linalg.svd(np.array(A)); M = Vt[-1].reshape(3, 4)
    Kr, Rr = np.linalg.qr(np.linalg.inv(M[:, :3]))                     # M[:, :3] = K R  ->  inv = R^T K^-1
    K = np.linalg.inv(Rr); R = Kr.T
    S = np.diag(np.sign(np.diag(K))); K = K @ S; R = S @ R
    if np.linalg.det(R) < 0: R = -R; M = -M
    C = -np.linalg.inv(M[:, :3]) @ M[:, 3]
    f = abs(K[0, 0] / K[2, 2])
    # pixel model: u = W/2 + f*xc/(-zc), v = H/2 - f*yc/(-zc) with camera looking down -Z; DLT camera looks down +Z with v down
    Rb = np.diag([1, -1, -1]) @ R                                         # rows = camera axes in world (x right, y up, z back)
    return np.concatenate([irod(Rb.T), C, [f * SENSOR / W]])
best = None
rng = np.random.default_rng(3)
try:
    x0 = dlt(P_all[sol], UV_all[sol])
except Exception as e:
    x0 = None; print('DLT failed', e)
cands = []
if x0 is not None: cands.append(x0)
if 'x0' in J: cands.append(np.array(J['x0']))
for c in list(cands):
    for k in range(40):
        y = c.copy(); y[:3] = irod(rod(rng.normal(0, 0.25, 3)) @ rod(c[:3])); y[3:6] = c[3:6] * rng.uniform(0.7, 1.4); y[6] = c[6] * rng.uniform(0.5, 2.0)
        cands.append(y)
for c in cands:
    c = c.copy()
    if SHIFT and len(c) == 7: c = np.concatenate([c, [W / 2, H / 2]])
    if not SHIFT: c = c[:7]
    if FIXF: c[6] = FIXF
    x = lm(c); e = float(np.sqrt(((project(x, P)[0] - UV) ** 2).sum(1).mean()))
    if best is None or e < best[0]: best = (e, x)
e, x = best
uv, _ = project(x, P_all)
for p, a, b in zip(pts, uv, UV_all):
    print('PNP point %-16s %s %6.1f px  (model %5.0f,%5.0f photo %5.0f,%5.0f)' % (p['name'], 'CHECK' if p.get('check') else 'solve', np.linalg.norm(a - b), a[0], a[1], b[0], b[1]))
print('PNP rms %.2f px (%.2f %% of width) focal %.1f mm  cam %s  pp %s' % (e, 100 * e / W, x[6], np.round(x[3:6], 4).tolist(), np.round(x[7:], 1).tolist() if len(x) > 7 else 'centre'))
J['x0'] = x.tolist(); J['pnp_rms_px'] = e
json.dump(J, open(sys.argv[1], 'w'), indent=1)
