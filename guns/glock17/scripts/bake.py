"""bake.py - G17 v4 texture bakes, high-poly (lookdev materials incl. the grip-texture height) -> game meshes (Cycles GPU).
Per assembly (selected-to-active, cage extrusion 0.6 mm, ray 1.6 mm):
  T_G17_<Part>_Normal   tangent space, OpenGL (UE flips green on import; contract convention)
  T_G17_<Part>_BaseColor sRGB, from the lookdev base colour (stud tops, white sight paint, steel/polymer values)
  T_G17_<Part>_ORM      R = AO (this assembly's own shells only, so parts that come apart carry no foreign shadows),
                        G = roughness, B = metallic
Frame + slide 4096, barrel / magazine / backstrap 2048 (user request for the hero first-person weapon), 16 px dilation.  Saves work/G17_V4_Game.blend with M_G17_<Part> using the maps, and export/textures/*.png.
usage: blender -b work/G17_V4_Low.blend --python bake.py -- [ao_samples] [parts=Frame,Slide,...]"""
import bpy, sys, os, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lookdev as LD
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
AO_S = int(argv[0]) if argv else 64
PARTS = (argv[1] if len(argv) > 1 else 'Frame,Slide,Barrel,Backstrap,Magazine').split(',')
TEX = os.path.join(HERE, 'export', 'textures'); os.makedirs(TEX, exist_ok=True)
ASM = {'Frame': ['frame', 'trigger', 'pin0', 'pin1', 'slidestop', 'takedown', 'magcatchL', 'magcatchR', 'lockblock', 'housing'],
       'Slide': ['slide', 'rsight', 'fsight', 'extractor', 'plate'], 'Barrel': ['barrel', 'guiderod'],
       'Backstrap': ['backstrap'], 'Magazine': ['magbody', 'follower', 'baseplate']}
sc = bpy.context.scene
def log(*a): print('[bake]', *a, flush=True)
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = d.type == 'OPTIX'
    sc.cycles.device = 'GPU'
except Exception as e: log('GPU unavailable', e)
sc.render.engine = 'CYCLES'; sc.cycles.use_denoising = False
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.0006; bk.max_ray_distance = 0.0016
bk.margin = 16; bk.margin_type = 'EXTEND'; bk.use_clear = True
if sc.world is None: sc.world = bpy.data.worlds.new('_bw')
sc.world.light_settings.distance = 0.006                     # AO reach 6 mm
hcol = bpy.data.collections['HIGH']; hcol.hide_render = False
for o in hcol.objects: o.hide_set(False); o.hide_viewport = False
# lookdev materials on the high shells (same as the review renders)
for o in hcol.objects:
    mt = o.data.materials[0]
    if mt.name.startswith('PV_'):
        look = LD.IDMAT[int(mt.name.split('_')[1])]; kind = LD.kind_of(o.name, look)
        o.data.materials[0] = LD.material('LD_%s_%s' % (look, kind), look, kind)

def principled(m): return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
def outnode(m): return next(n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
def emit_setup(m, what):
    """temporarily route base colour / roughness / metallic into an emission shader; returns a restore callback"""
    nt = m.node_tree; b = principled(m); out = outnode(m); old = out.inputs['Surface'].links[0].from_socket
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 1.0
    if what == 'color':
        inp = b.inputs['Base Color']
        if inp.links: nt.links.new(inp.links[0].from_socket, em.inputs['Color'])
        else: em.inputs['Color'].default_value = inp.default_value
    else:   # 'orm': R 1, G roughness, B metallic
        cc = nt.nodes.new('ShaderNodeCombineColor'); cc.inputs['Red'].default_value = 1.0
        for ch, nm in (('Green', 'Roughness'), ('Blue', 'Metallic')):
            inp = b.inputs[nm]
            if inp.links: nt.links.new(inp.links[0].from_socket, cc.inputs[ch])
            else: cc.inputs[ch].default_value = inp.default_value
        nt.links.new(cc.outputs[0], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    def restore():
        nt.links.new(old, out.inputs['Surface'])
        for n in list(nt.nodes):
            if n == em or (what == 'orm' and n.bl_idname == 'ShaderNodeCombineColor' and n.outputs[0].links and n.outputs[0].links[0].to_node == em): nt.nodes.remove(n)
        if em.name in nt.nodes: nt.nodes.remove(em)
    return restore

def new_img(name, size, noncolor, fill):
    if name in bpy.data.images: bpy.data.images.remove(bpy.data.images[name])
    im = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False); im.generated_color = fill
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im
def bake_into(low, highs, img, kind, samples):
    sc.cycles.samples = samples
    m = low.data.materials[0]; m.use_nodes = True; nt = m.node_tree
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img; nt.nodes.active = tn
    for x in bpy.context.view_layer.objects: x.select_set(False)
    for h in highs: h.select_set(True)
    low.select_set(True); bpy.context.view_layer.objects.active = low
    if kind == 'NORMAL': bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
    else: bpy.ops.object.bake(type=kind)
    nt.nodes.remove(tn)

SIZES = {'Frame': 4096, 'Slide': 4096, 'Barrel': 2048, 'Backstrap': 2048, 'Magazine': 2048}
EMIT_S = 24                                                   # AO / bevel shader nodes are stochastic
import bmesh, math
def repack(o, size):
    """re-pack the existing islands with a 16 px margin at the final texture size (island shapes unchanged)"""
    for x in bpy.context.view_layer.objects: x.select_set(False)
    o.hide_set(False); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='FRACTION', margin=16.0 / size, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT'); o['tex_size'] = size
def rebuild_lods(o):
    lcol = bpy.data.collections['LODS']
    for k, r in (('LOD1', 0.45), ('LOD2', 0.18)):
        old = bpy.data.objects.get(o.name + '_' + k)
        if old: bpy.data.objects.remove(old, do_unlink=True)
        me = o.data.copy(); l = bpy.data.objects.new(o.name + '_' + k, me); lcol.objects.link(l)
        m = l.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = r; m.use_collapse_triangulate = True
        with bpy.context.temp_override(object=l, active_object=l): bpy.ops.object.modifier_apply(modifier=m.name)
        l.data.materials.clear(); l.data.materials.append(o.data.materials[0])
report = {}
for asm in PARTS:
    repack(bpy.data.objects['SM_G17_' + asm], SIZES[asm])
for asm in PARTS:
    t0 = time.time(); low = bpy.data.objects['SM_G17_' + asm]; size = int(low.get('tex_size', 1024))
    highs = [bpy.data.objects['HI_' + s] for s in ASM[asm] if ('HI_' + s) in bpy.data.objects]
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = not (o in highs or o is low)
    low.hide_render = False                                   # must render for the bake, but is invisible to every ray type
    for k in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
        setattr(low, k, False)
    short = 'G17_' + asm
    nrm = new_img('T_%s_Normal' % short, size, True, (0.5, 0.5, 1, 1)); bake_into(low, highs, nrm, 'NORMAL', 8)
    restores = [emit_setup(h.data.materials[0], 'color') for h in highs]
    col = new_img('T_%s_BaseColor' % short, size, False, (0, 0, 0, 1)); bake_into(low, highs, col, 'EMIT', EMIT_S)
    for r in restores: r()
    restores = [emit_setup(h.data.materials[0], 'orm') for h in highs]
    orm = new_img('T_%s_ORM' % short, size, True, (1, 0.6, 0, 1)); bake_into(low, highs, orm, 'EMIT', EMIT_S)
    for r in restores: r()
    ao = new_img('_ao_' + asm, size, True, (1, 1, 1, 1)); bake_into(low, highs, ao, 'AO', AO_S)
    A = np.empty(size * size * 4, np.float32); ao.pixels.foreach_get(A)
    O = np.empty_like(A); orm.pixels.foreach_get(O); O[0::4] = A[0::4]; orm.pixels.foreach_set(O)
    bpy.data.images.remove(ao)
    for im in (col, orm, nrm):
        im.filepath_raw = os.path.join(TEX, im.name + '.png'); im.file_format = 'PNG'; im.save()
    # final game material
    m = low.data.materials[0]; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'): nt.nodes.remove(n)
    b = principled(m)
    tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = col; nt.links.new(tc.outputs['Color'], b.inputs['Base Color'])
    to = nt.nodes.new('ShaderNodeTexImage'); to.image = orm; sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(to.outputs['Color'], sp.inputs[0])
    nt.links.new(sp.outputs['Green'], b.inputs['Roughness']); nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = nrm; nm = nt.nodes.new('ShaderNodeNormalMap'); nm.space = 'TANGENT'
    nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    rebuild_lods(low)
    report[asm] = dict(size=size, highs=len(highs), seconds=round(time.time() - t0, 1)); log('BAKED', asm, report[asm])
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = not (o.name.startswith('SM_G17_') and '_LOD' not in o.name)
        for k in ('visible_camera', 'visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
            setattr(o, k, True)                                   # undo the bake-time ray invisibility
hcol.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'work', 'G17_V4_Game.blend'))
json.dump(report, open(os.path.join(HERE, 'work', 'bake_report.json'), 'w'), indent=1)
log('BAKE_DONE')
