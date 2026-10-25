"""ar15_split_check.py - port-side renders: the shipped Upper | UpperBody + BCG at rest | BCG 9 cm back (the cycle's rear point).
blender -b --python ar15_split_check.py  ->  out/game/split/check_<n>.png"""
import bpy, os, math
from mathutils import Vector as V
HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, 'out', 'game')
OUTD = os.path.join(G, 'split')


def imp(p):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=p, axis_forward='-Y', axis_up='Z')
    return [o for o in bpy.data.objects if o not in before and o.type == 'MESH'][0]


def matcol(o, cols):
    for i, slot in enumerate(o.material_slots):
        n = slot.material.name.split('.')[0] if slot.material else ''
        n = n if n in cols else ('BCG' if 'bcg' in o.name.lower() else ['Receiver', 'Steel', 'BCG'][min(i, 2)])
        m = bpy.data.materials.new('chk_' + n + str(i))
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        c, r, mt = cols.get(n, ((0.5, 0.5, 0.5), 0.5, 0.0))
        b.inputs['Base Color'].default_value = (*c, 1)
        b.inputs['Roughness'].default_value = r
        b.inputs['Metallic'].default_value = mt
        slot.material = m


COLS = {'Receiver': ((0.035, 0.036, 0.04), 0.45, 0.6), 'Steel': ((0.30, 0.30, 0.32), 0.35, 1.0), 'BCG': ((0.55, 0.45, 0.25), 0.3, 1.0)}


def scene(objs_setup, name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        sc.cycles.device = 'GPU'
    except Exception:
        pass
    sc.render.resolution_x, sc.render.resolution_y = 1200, 600
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.35, 0.36, 0.38, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 0.6
    for fn, off in objs_setup:
        o = imp(os.path.join(G, fn))
        o.location += off
        matcol(o, COLS)
    # camera on the gun's right (UE -X = Blender -X), level with the port, looking +X
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 70
    target = V((-0.005, 0.045, 0.12))
    cam.location = V((-0.42, -0.02, 0.22))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for loc, en in ((V((-0.6, 0.3, 0.6)), 300), (V((-0.4, -0.4, 0.3)), 150)):
        L = bpy.data.objects.new('l', bpy.data.lights.new('l', 'AREA'))
        L.data.energy = en
        L.data.size = 0.5
        L.location = loc
        L.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
        sc.collection.objects.link(L)
    sc.render.filepath = os.path.join(OUTD, name)
    bpy.ops.render.render(write_still=True)


scene([('SM_AR15_Upper.fbx', V())], 'check_1_shipped.png')
scene([('split/SM_AR15_UpperBody.fbx', V()), ('split/SM_AR15_BCG.fbx', V())], 'check_2_body_bcg_rest.png')
scene([('split/SM_AR15_UpperBody.fbx', V()), ('split/SM_AR15_BCG.fbx', V((0, 0.094, 0)))], 'check_3_bcg_back.png')
