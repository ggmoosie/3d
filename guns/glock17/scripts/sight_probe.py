"""sight_probe.py - the ADS sockets from the v4 game slide (export/game/SM_G17_Slide.fbx), UE cm (x gun-left, y muzzle, z up):
Aim = centre of the rear-sight U-notch at its top edge, FrontSight = top centre of the front post.  Ray casts straight down."""
import bpy, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(HERE, 'export', 'game', 'SM_G17_Slide.fbx'))
vs, fs = [], []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    M = o.matrix_world; n0 = len(vs); vs += [M @ v.co * 100.0 for v in o.data.vertices]; fs += [tuple(i + n0 for i in p.vertices) for p in o.data.polygons]
bvh = BVHTree.FromPolygons(vs, fs)
def top(x, y):   # UE (x, y) -> highest surface z (cm) by a ray straight down from above
    h = bvh.ray_cast(Vector((x, -y, 9.0)), Vector((0, 0, -1)), 9.0); return h[0].z if h[0] is not None else None
ys = [round(-6.0 + 0.01 * k, 2) for k in range(int((14.0 + 6.0) / 0.01))]
prof = {y: (top(0.0, y), top(0.30, y), top(-0.30, y)) for y in ys}
slide_top = max(v[0] for y, v in prof.items() if v[0] is not None and -2 < y < 10)
# rear sight: the run of y where the blades (x +-0.30) stand > 2 mm above the slide flat; front: the post at x 0 near the muzzle
base = sorted(v[0] for y, v in prof.items() if v[0] is not None and 0 < y < 9)[len([1 for y, v in prof.items() if v[0] is not None and 0 < y < 9]) // 2]
rear = [y for y in ys if y < 2 and prof[y][1] is not None and prof[y][1] > base + 0.2]
front = [y for y in ys if y > 9 and prof[y][0] is not None and prof[y][0] > base + 0.15]
r0, r1 = min(rear), max(rear); f0, f1 = min(front), max(front)
rc = round((r0 + r1) / 2, 3); fc = round((f0 + f1) / 2, 3)
# notch: half width at the top edge (x where the top surface at the rear-sight centre rises to the blade top)
bt = max(top(0.30, rc), top(-0.30, rc)); nb = top(0.0, rc)
xs = [k * 0.005 for k in range(0, 80)]; hw = next((x for x in xs if top(x, rc) is not None and top(x, rc) > bt - 0.01), None)
ft = max(top(0.0, y) for y in front)
# front post top centre (x 0): flat top -> the centre of its top run in y
ftop = [y for y in front if top(0.0, y) > ft - 0.01]; fyc = round((min(ftop) + max(ftop)) / 2, 3)
aim = [0.0, rc, round(bt, 3)]; fs_ = [0.0, fyc, round(ft, 3)]
import math
ang = math.degrees(math.atan2(fs_[2] - aim[2], fs_[1] - aim[1]))
out = dict(base_slide_top_cm=round(base, 3), rear_sight_y=[r0, r1], rear_blade_top=round(bt, 3), notch_bottom=round(nb, 3), notch_half_width=hw,
           front_sight_y=[f0, f1], front_top=round(ft, 3), front_top_y=[min(ftop), max(ftop)], Aim=aim, FrontSight=fs_, sight_radius_cm=round(fs_[1] - aim[1], 3),
           line_pitch_deg=round(ang, 3), bore_z=3.95, line_height_above_bore_at_aim=round(aim[2] - 3.95, 3))
json.dump(out, open(os.path.join(HERE, 'work', 'sight_sockets.json'), 'w'), indent=1)
print('SIGHTS', json.dumps(out))
