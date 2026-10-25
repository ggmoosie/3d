"""handfit_check.py - do the existing G17 hand poses still fit the new (v4) grip?  Blender 4.0 headless, read-only on the sources.

The in-game HP_SM_G17_Frame_R/L poses come from the manual capture Tools/Hands/manual/captures/20261018T183521_328388Z (the user's
SM_Pistol hold reused as a rough Glock seed).  This opens that capture, places three weapons at its weapon matrix (the capture's own
SM_Pistol, the Codex G17 frame+backstrap the poses were applied to in game, and the v4 frame+backstrap) and measures, per hand, with the
project's full-skin clip test (Tools/Hands/hclip.py): max penetration by region, plus the palm / finger-pad contact gaps.
Writes v4/work/handfit.json and review/handfit_<view>.png renders (v4 in orange-ish, codex in blue).  Nothing is saved to the capture.
usage: blender -b <capture>/pose.blend --python handfit_check.py"""
import bpy, sys, os, json, math
from mathutils import Matrix, Vector
HERE = os.path.dirname(os.path.abspath(__file__))
T = r"C:/Users/moosi/Documents/Unreal Projects/LootNShoot/Tools/Hands"; sys.path.insert(0, T)
import hclip
CAP = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), 'pose.json')))
W = Matrix(CAP['weapon_matrix_world'])
sc = bpy.context.scene; dg = bpy.context.evaluated_depsgraph_get()
print('[hf] unit scale', sc.unit_settings.scale_length, sc.unit_settings.length_unit)
old = bpy.data.objects['Setup Pistol (existing model)']
def import_parts(files, tag):
    objs = []
    for f in files:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=f, use_custom_normals=True)
        new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH' and not o.name.startswith('UCX')]
        for o in [o for o in bpy.data.objects if o not in before and o.name.startswith('UCX')]: bpy.data.objects.remove(o)
        objs += new
    # join into one weapon object in weapon-local cm, then place it at the capture's weapon matrix
    for o in objs:
        o.data.transform(o.matrix_world); o.matrix_world = Matrix.Identity(4)
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]): bpy.ops.object.join()
    o = objs[0]; o.name = tag
    co = [v.co for v in o.data.vertices]; ext = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
    s = 1.0
    if ext[1] < 1.0: s = 100.0                                         # imported in metres -> the capture works in centimetres
    o.data.transform(Matrix.Scale(s, 4)); o.matrix_world = W
    co = [v.co for v in o.data.vertices]; ext = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
    print('[hf] weapon', tag, 'local extent cm', [round(e, 2) for e in ext]); return o
codex = import_parts([os.path.join(HERE, '..', 'out', 'game', 'SM_G17_Frame.fbx'), os.path.join(HERE, '..', 'out', 'game', 'SM_G17_Backstrap.fbx')], 'W_codex')
v4 = import_parts([os.path.join(HERE, 'export', 'game', 'SM_G17_Frame.fbx'), os.path.join(HERE, 'export', 'game', 'SM_G17_Backstrap.fbx')], 'W_v4')
hands = bpy.data.objects['VisiblePlayerHands']
dg = bpy.context.evaluated_depsgraph_get(); body = hclip.Body(hands, dg)
from mathutils.bvhtree import BVHTree
def gaps(gun_obj, side):
    """distance from palm / finger-pad skin to the weapon surface: how much of the hand actually touches"""
    M = gun_obj.matrix_world; me = gun_obj.data; me.calc_loop_triangles()
    bvh = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(t.vertices) for t in me.loop_triangles])
    out = {}
    for part in ('palm', 'finger:index', 'finger:middle', 'finger:ring', 'finger:pinky', 'finger:thumb'):
        idx = [i for i, b in enumerate(body.dom) if hclip.region_of(b, side)[1] == part]
        ds = []
        for i in idx:
            q, n, fi, d = bvh.find_nearest(body.co[i], 50.0)
            if q is not None: ds.append(d)
        ds.sort()
        if ds: out[part] = dict(min_cm=round(ds[0], 2), p10_cm=round(ds[len(ds) // 10], 2), touching=sum(1 for d in ds if d < 0.15), n=len(ds))
    return out
res = {}
for w in (old, codex, v4):
    g = hclip.Gun(w, 0.3); res[w.name] = {}
    for side in ('r', 'l'):
        c = hclip.clip(body, g, lambda b, s=side: b is not None and b.endswith('_' + s) and hclip.region_of(b, s)[1] in ('palm', 'finger:index', 'finger:middle', 'finger:ring', 'finger:pinky', 'finger:thumb'), side)
        res[w.name][side] = dict(max_pen_cm=round(c['max'], 2), regions={k: round(v, 2) for k, v in list(c['regions'].items())[:6]}, gaps=gaps(w, side))
        print('[hf] %-32s hand %s: %s' % (w.name, side, hclip.summary(c)))
        for part, gq in res[w.name][side]['gaps'].items(): print('[hf]      %-14s min %.2f cm  p10 %.2f  touching %d/%d' % (part, gq['min_cm'], gq['p10_cm'], gq['touching'], gq['n']))
json.dump(res, open(os.path.join(HERE, 'work', 'handfit.json'), 'w'), indent=1)
# renders from the capture's review cameras: v4 vs codex
sc.render.engine = 'BLENDER_EEVEE'; sc.render.resolution_x, sc.render.resolution_y = 960, 720; sc.render.film_transparent = False
def mat(name, col):
    m = bpy.data.materials.new(name); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*col, 1); return m
mv, mc = mat('hf_v4', (0.85, 0.45, 0.15)), mat('hf_codex', (0.2, 0.4, 0.9))
for o, m in ((v4, mv), (codex, mc)):
    o.data.materials.clear(); o.data.materials.append(m)
for o in bpy.data.objects:
    if o.type == 'MESH' and o not in (v4, codex, hands): o.hide_render = True
if sc.world is None: sc.world = bpy.data.worlds.new('w')
sc.world.use_nodes = True; sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.5
for cam in ('Fingers_Right', 'Thumb_Left', 'Underside', 'First_Person_Native_Pose', 'CamPalm_r'):
    if cam not in bpy.data.objects: continue
    sc.camera = bpy.data.objects[cam]
    for which, show, hide in (('v4', v4, codex), ('codex', codex, v4)):
        show.hide_render = False; hide.hide_render = True
        sc.render.filepath = os.path.join(HERE, 'review', 'handfit', 'hf_%s_%s.png' % (cam, which)); bpy.ops.render.render(write_still=True)
print('[hf] HANDFIT_DONE')
