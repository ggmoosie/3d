"""delta.py - how far the hand-contact surfaces moved, v4 vs the Codex meshes the hand poses were authored on.
Reads the Codex grip-zone samples (v3/work/contract_samples.npz: UE mm points + outward normals, read-only) and, for each
sample, measures the signed distance to the nearest v4 LOD0 surface along the old normal (+ = new surface outside the old
one, toward the hand; - = inside), plus the plain nearest distance.  Writes work/grip_delta.json.
usage: blender -b work/G17_V4_Game.blend --python delta.py"""
import bpy, os, json
import numpy as np
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
S = np.load(os.path.join(HERE, '..', 'v3', 'work', 'contract_samples.npz'))
def tree(names):
    verts, polys = [], []
    for n in names:
        o = bpy.data.objects[n]; M = o.matrix_world; b = len(verts)
        verts += [tuple((M @ v.co) * 1000.0 * V((1, -1, 1))) for v in o.data.vertices]
        polys += [[b + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons([V(v) for v in verts], polys)
ALL = tree(['SM_G17_Frame', 'SM_G17_Backstrap', 'SM_G17_Slide']); MAG = tree(['SM_G17_Magazine'])
res = {}
for key in sorted(k[:-2] for k in S.files if k.endswith('_p')):
    P = S[key + '_p']; N = S[key + '_n']; t = MAG if key == 'mag_baseplate' else ALL
    d = np.full(len(P), np.nan); near = np.full(len(P), np.nan)
    for i, (p, n) in enumerate(zip(P, N)):
        q, nq, idx, dd = t.find_nearest(V(p), 60.0)
        if q is None: continue
        d[i] = float(np.dot(np.array(q) - p, n)); near[i] = dd
    ok = ~np.isnan(d); a = np.abs(d[ok])
    res[key] = dict(n=int(ok.sum()), mean_abs_mm=round(float(a.mean()), 2), p50_mm=round(float(np.median(d[ok])), 2),
                    p95_abs_mm=round(float(np.percentile(a, 95)), 2), max_out_mm=round(float(d[ok].max()), 2),
                    max_in_mm=round(float(d[ok].min()), 2), nearest_mean_mm=round(float(np.nanmean(near)), 2))
    print('DELTA %-16s n %5d  mean|d| %5.2f  median %+6.2f  p95|d| %5.2f  out %+6.2f  in %+6.2f' % (key, res[key]['n'], res[key]['mean_abs_mm'],
          res[key]['p50_mm'], res[key]['p95_abs_mm'], res[key]['max_out_mm'], res[key]['max_in_mm']))
json.dump(res, open(os.path.join(HERE, 'work', 'grip_delta.json'), 'w'), indent=1)
