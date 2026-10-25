"""grip_probe.py - measure the v4 game frame (export/game FBX) for the hand-grasp spec, in UE cm (x gun-left, y muzzle, z up):
grip sections (front / rear / half width per height), the trigger blade's finger face (same ray walk as hgrasp.trigger_face), the
trigger-guard opening (keep-out box) and the tang notch.  usage: blender -b --factory-startup --python grip_probe.py"""
import bpy, os, json, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
for p in ('Frame', 'Backstrap', 'Magazine'):
    bpy.ops.import_scene.fbx(filepath=os.path.join(HERE, 'export', 'game', 'SM_G17_%s.fbx' % p))
vs, fs = [], []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name.startswith('UCX'): continue
    M = o.matrix_world; n0 = len(vs)
    vs += [M @ v.co * 100.0 for v in o.data.vertices]            # m -> cm (Blender frame)
    fs += [tuple(i + n0 for i in p.vertices) for p in o.data.polygons]
bvh = BVHTree.FromPolygons(vs, fs)
def ue2b(p): return Vector((p[0], -p[1], p[2]))
def b2ue(p): return Vector((p[0], -p[1], p[2]))
def ray(o_ue, d_ue, L=20.0):
    h = bvh.ray_cast(ue2b(o_ue), ue2b(d_ue).normalized(), L)
    return (b2ue(h[0]), b2ue(h[1])) if h[0] is not None else (None, None)
out = dict(sections={})
# grip sections: from far ahead / behind along y at the mid-plane, from the sides along x at the section's centre
for z in [x * 0.5 for x in range(-16, 3)]:
    f, _ = ray((0, 15, z), (0, -1, 0)); r, _ = ray((0, -20, z), (0, 1, 0))
    if f is None or r is None: continue
    yc = (f.y + r.y) / 2; lft, _ = ray((10, yc, z), (-1, 0, 0)); rgt, _ = ray((-10, yc, z), (1, 0, 0))
    out['sections'][round(z, 2)] = dict(front=round(f.y, 3), rear=round(r.y, 3), left=round(lft.x, 3) if lft else None, right=round(rgt.x, 3) if rgt else None)
    print('SEC z %5.2f  front y %6.2f  rear y %6.2f  x %s..%s' % (z, f.y, r.y, round(rgt.x, 2) if rgt else None, round(lft.x, 2) if lft else None))
# the trigger blade's front (finger) face: rays from inside the guard opening toward the back, walk down
hits = []
for k in range(0, 50):
    z = 1.2 - k * 0.1
    q, n = ray((0, 5.4, z), (0, -1, 0), 4.0)
    if q is None: continue
    if n.y > 0.6 and 2.0 < q.y < 4.6: hits.append((q.y, z, q, n))
print('TRIGGER hits', [(round(a, 2), round(b, 2)) for a, b, _, _ in hits])
if hits:
    y, z, q, n = min(hits, key=lambda r: r[0])
    out['trigger_face'] = dict(face=[0.0, round(q.y, 3), round(z, 3)], normal=[round(n.x, 3), round(n.y, 3), round(n.z, 3)],
                               blade_z=[round(min(r[1] for r in hits), 2), round(max(r[1] for r in hits), 2)])
# guard opening: the guard bar top (rays up from below inside the opening would hit the bar: cast down from the frame underside)
for y in (2.0, 3.0, 4.0, 5.0):
    dn, _ = ray((0, y, 2.5), (0, 0, -1)); up, _ = ray((0, y, -3.5), (0, 0, 1))
    print('GUARD y %.1f  first hit down from z2.5: %s   up from z-3.5: %s' % (y, round(dn.z, 2) if dn else None, round(up.z, 2) if up else None))
for z in (-0.5, 0.0, 0.5, 1.0):
    fw, _ = ray((0, 3.6, z), (0, 1, 0)); bk, _ = ray((0, 2.4, z), (0, -1, 0))
    print('GUARD z %.1f  front inner y %s  rear (grip front / blade) y %s' % (z, round(fw.y, 2) if fw else None, round(bk.y, 2) if bk else None))
# receiver underside above the opening, guard bar top
und = [ray((0, y, -1.0), (0, 0, 1))[0] for y in (3.0, 4.0, 5.0)]
bar = [ray((0, y, 2.0), (0, 0, -1))[0] for y in (5.0, 5.5)]
print('UNDERSIDE', [round(u.z, 2) if u else None for u in und], 'BAR', [round(b.z, 2) if b else None for b in bar])
# tang: the rear-most top of the backstrap: rays from behind at heights
for z in [x * 0.25 for x in range(0, 16)]:
    r, _ = ray((0, -20, z), (0, 1, 0)); print('REAR z %.2f y %s' % (z, round(r.y, 2) if r else None))
json.dump(out, open(os.path.join(HERE, 'work', 'grip_probe.json'), 'w'), indent=1)
print('PROBE_DONE')
