"""bl_render.py - lookdev renders of the G17 v4 (Cycles GPU, AgX, softbox studio + soft HDRI-like gradient world).
usage: blender -b <blend> --python bl_render.py -- <outdir> <views> [samples] [res_x] [--explode] [--prefix p]
views: right,left,q_fl,q_fr,q_rl,top_rear,fp_hip,fp_ads,explode,...  (comma list)
Works on the high-poly (HI_* objects with preview materials, re-assigned to the lookdev values below) and on the game meshes
(SM_G17_* with their baked material).  Real values: slide nDLC base 0.035 / metal 1 / rough 0.40, polymer 0.03 / rough 0.68."""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector as V, Matrix
argv = sys.argv[sys.argv.index('--') + 1:]
outdir = argv[0]; views = argv[1].split(','); flags = [a for a in argv[2:] if a.startswith('--')]
nums = [a for a in argv[2:] if not a.startswith('--') and a.replace('.', '').isdigit()]
samples = int(nums[0]) if nums else 128; resx = int(nums[1]) if len(nums) > 1 else 1600
prefix = argv[argv.index('--prefix') + 1] if '--prefix' in argv else 'r'
sc = bpy.context.scene
os.makedirs(outdir, exist_ok=True)

def enable_gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for t in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = t; prefs.get_devices()
            if [d for d in prefs.devices if d.type == t]:
                for d in prefs.devices: d.use = d.type == t
                return t
        except TypeError: pass
gpu = enable_gpu()
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU' if gpu else 'CPU'; sc.cycles.samples = samples
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'; sc.cycles.max_bounces = 10
sc.cycles.glossy_bounces = 6; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.01
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Base Contrast'
except TypeError: pass
TRANSP = '--transparent' in argv
sc.render.film_transparent = TRANSP; sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA' if TRANSP else 'RGB'

# ------------------------------------------------------------------ lookdev materials for the high-poly shells (lookdev.py: real values + grip texture)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lookdev as LD
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith('HI_') and o.data.materials and o.data.materials[0].name.startswith('PV_'):
        look = LD.IDMAT[int(o.data.materials[0].name.split('_')[1])]; kind = LD.kind_of(o.name, look)
        o.data.materials[0] = LD.material('LD_%s_%s' % (look, kind), look, kind)
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'): bpy.data.objects.remove(o)
GAMEMODE = '--game' in flags
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('UCX') and
          ((o.name.startswith('SM_G17_') and '_LOD' not in o.name) if GAMEMODE else o.name.startswith('HI_'))]
if not meshes: meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('SM_G17_') and '_LOD' not in o.name]
for c in bpy.data.collections: c.hide_render = False
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = o not in meshes
        for k in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(o, k, True)

# ------------------------------------------------------------------ studio: backdrop colour seen by the camera, softboxes for light + reflections
w = bpy.data.worlds.get('_Studio') or bpy.data.worlds.new('_Studio'); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld'); lp = nt.nodes.new('ShaderNodeLightPath'); mix = nt.nodes.new('ShaderNodeMixShader')
env = nt.nodes.new('ShaderNodeBackground'); cam_bg = nt.nodes.new('ShaderNodeBackground')
tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); ramp = nt.nodes.new('ShaderNodeValToRGB')
mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1.0; mr.inputs['From Max'].default_value = 1.0
nt.links.new(tc.outputs['Generated'], sep.inputs[0]); nt.links.new(sep.outputs['Z'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], ramp.inputs['Fac'])
ramp.color_ramp.elements[0].position = 0.15; ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.105, 1)     # floor
ramp.color_ramp.elements[1].position = 0.62; ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)        # tent walls / ceiling
e = ramp.color_ramp.elements.new(0.50); e.color = (0.75, 0.75, 0.76, 1)
nt.links.new(ramp.outputs['Color'], env.inputs['Color']); env.inputs['Strength'].default_value = float(os.environ.get('G17_ENV', '0.4'))
cam_bg.inputs['Color'].default_value = (0.80, 0.80, 0.80, 1); cam_bg.inputs['Strength'].default_value = 1.0
nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac']); nt.links.new(env.outputs[0], mix.inputs[1]); nt.links.new(cam_bg.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs['Surface'])

def bounds(objs):
    P = []
    for o in objs:
        M = np.array(o.matrix_world); co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)[::50]; P.append(co @ M[:3, :3].T + M[:3, 3])
    P = np.concatenate(P); return P.min(0), P.max(0)
lo, hi = bounds(meshes); ctr = V(((lo + hi) / 2).tolist()); rad = float(np.linalg.norm(hi - lo)) / 2
def softbox(name, d, size, power, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA'); l.shape = 'RECTANGLE'; l.size, l.size_y = size; l.energy = power; l.color = color
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = ctr + V(d)
    o.rotation_euler = (ctr - o.location).to_track_quat('-Z', 'Y').to_euler(); return o
# Blender axes: gun muzzle -Y, gun left +X, up +Z.  Big key overhead-front, strip rims on both sides, low fill.
K = float(os.environ.get('G17_KEY', '0.6')); SP = float(os.environ.get('G17_SIDE', '0.42'))
softbox('key', (0.10, -0.10, 0.75), (0.9, 0.6), 7.0 * K)            # overhead key: top / chamfer highlights
softbox('sideR', (-0.9, -0.05, 0.18), (1.4, 0.7), 22.0 * SP)       # tent walls: broad reflections in the slide flanks
softbox('sideL', (0.9, -0.05, 0.18), (1.4, 0.7), 18.0 * SP)
softbox('rimL', (0.55, 0.55, 0.30), (0.15, 0.9), 3.0 * K)
softbox('rimR', (-0.55, 0.55, 0.30), (0.15, 0.9), 3.0 * K)
softbox('rear', (0.0, 0.9, 0.35), (0.8, 0.5), 4.0 * K)
softbox('front', (0.0, -0.9, 0.25), (0.8, 0.5), 4.0 * K)

cam_d = bpy.data.cameras.new('_rc'); cam = bpy.data.objects.new('_rc', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.clip_start = 0.002; cam_d.clip_end = 20; cam_d.sensor_width = 36
def B(x, y, z): return V((x / 1000.0, -y / 1000.0, z / 1000.0))       # G mm -> Blender
# camera direction FROM the gun TO the camera in G axes (x left, y muzzle, z up); fov; aspect
VIEWS = {'right': ((-1, 0, 0.0), 13, (16, 11)), 'left': ((1, 0, 0.0), 13, (16, 11)),
         'q_fl': ((0.62, 0.70, 0.36), 22, (4, 3)), 'q_fr': ((-0.62, 0.70, 0.30), 22, (4, 3)),
         'q_rl': ((0.55, -0.70, 0.45), 22, (4, 3)), 'top_rear': ((-0.30, -0.62, 0.72), 24, (1, 1)),
         'front': ((0, 1, 0.05), 16, (1, 1)), 'rear': ((0, -1, 0.05), 16, (1, 1)), 'bottom': ((0.2, 0.1, -1), 18, (4, 3)),
         'explode': ((0.75, 0.35, 0.30), 30, (16, 11))}
FP = {'fp_hip': ((42, -175, 92), (-4, 140, 18), 52), 'fp_ads': ((0, -250, 54.6), (0, 400, 52.9), 40),
      'fp_game': ((58, -215, 98), (-10, 120, 12), 62), 'fp_left': ((95, -170, 60), (-5, 40, -10), 55),
      'fp_close': ((38, -150, 80), (-2, 200, 25), 60)}

EXPLODE = {'Slide': (0, 30, 50), 'Barrel': (0, 62, 95), 'Magazine': (0, -36, -88), 'Backstrap': (0, -40, -8), 'Frame': (0, 0, 0)}
def asm_of(o):
    n = o.name
    for k in EXPLODE:
        if ('_' + k) in n or n.startswith('HI_') and o.users_collection and o.users_collection[0].name.endswith(k): return k
    return 'Frame'
base_loc = {o.name: o.location.copy() for o in meshes}
def explode(on):
    for o in meshes:
        d = EXPLODE[asm_of(o)] if on else (0, 0, 0)
        o.location = base_loc[o.name] + B(*d)
    bpy.context.view_layer.update()

import json
def refcam(view):
    """matched photo camera (pnp.py vector, lens shift for an off-centre principal point)"""
    J = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'work', 'match_%s_p2.json' % view)))
    _im = bpy.data.images.load(J['reference'], check_existing=True); W, H = _im.size
    x = J['x0']
    import numpy as _np
    r = _np.array(x[:3]); th = _np.linalg.norm(r); k = r / th; K = _np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    R = _np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K
    cam.matrix_world = Matrix([list(R[i]) + [x[3 + i]] for i in range(3)] + [[0, 0, 0, 1]])
    cam_d.type = 'PERSP'; cam_d.sensor_fit = 'HORIZONTAL'; cam_d.sensor_width = 36.0; cam_d.lens = x[6]
    cx, cy = (x[7], x[8]) if len(x) > 7 else (W / 2, H / 2)
    cam_d.shift_x = (W / 2 - cx) / W; cam_d.shift_y = (cy - H / 2) / W
    sc.render.resolution_x = resx; sc.render.resolution_y = int(round(resx * H / W))
for v in views:
    explode(v == 'explode')
    cam_d.shift_x = cam_d.shift_y = 0.0
    if v.startswith('m_'):
        refcam(v[2:])
    elif v in VIEWS:
        d, fov, (ax, ay) = VIEWS[v]
        sc.render.resolution_x = resx; sc.render.resolution_y = int(resx * ay / ax)
        cam_d.type = 'PERSP'; cam_d.angle = math.radians(fov)
        l2, h2 = bounds(meshes) if v == 'explode' else (lo, hi)
        c2 = V(((np.array(l2) + np.array(h2)) / 2).tolist()); r2 = float(np.linalg.norm(np.array(h2) - np.array(l2))) / 2
        dd = V((d[0], -d[1], d[2])).normalized()
        fv = 2 * math.atan(math.tan(math.radians(fov) / 2) * min(1.0, ay / ax))
        dist = r2 / math.sin(fv / 2) * (0.80 if v != 'explode' else 0.66)
        cam.location = c2 + dd * dist; cam.rotation_euler = (-dd).to_track_quat('-Z', 'Y').to_euler()
    else:
        loc, tgt, fov = FP[v]; sc.render.resolution_x = resx; sc.render.resolution_y = int(resx * 9 / 16)
        cam_d.type = 'PERSP'; cam_d.angle = math.radians(fov)
        cam.location = B(*loc); cam.rotation_euler = (B(*tgt) - B(*loc)).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(outdir, '%s_%s.png' % (prefix, v))
    bpy.ops.render.render(write_still=True)
    print('RENDERED', v, sc.render.filepath, flush=True)
explode(False)
