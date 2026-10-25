"""ar15_bake.py - Cycles mask bakes for the assembled AR-15 meshes, per material slot (headless, GPU when available):
  <gun>_<slot>_AO.png    ambient occlusion (self-occlusion of the assembled gun, 3 cm rays)
  <gun>_<slot>_Curv.png  curvature: 0.5 = flat, > 0.5 convex edges (Bevel-node edge detector, un-occluded), < 0.5 concave creases
  <gun>_Receiver_N.png   tangent-space normal map: engraved markings (SAFE / SEMI / AUTO, roll marks) - bump from the
                         markings mask (ar15_post.py markings), only on the receiver's left faces
  <gun>_Polymer_N.png    A2 grip: diamond checkering on both side panels + back-strap grooves (procedural bump)
Mask PNGs are linear (Non-Color) 8-bit; normal maps are OpenGL-style tangent space as Blender bakes them (UE: flip green).
See MATERIALS.md for how the master material uses them."""
import bpy, os, math, json, subprocess, time
import numpy as np
import ar15_lib as L
import ar15_spec as SP

BAKE = os.path.join(L.OUT, 'bake')
MARKINGS = os.path.join(BAKE, '_markings_mask.png')
MARK_LEN, MARK_H = 200.0, 80.0               # markings mask covers G Y 0 .. -200 mm, Z 0 .. -80 mm at 10 px/mm

def log(*a): L.log(*a)

def setup_cycles(samples):
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'
    import ar15_render as RD
    gpu = RD.enable_gpu(); sc.cycles.device = 'GPU' if gpu else 'CPU'
    sc.cycles.samples = samples; sc.cycles.use_denoising = False
    sc.render.bake.margin = 8; sc.render.bake.margin_type = 'EXTEND'
    if sc.world is None: sc.world = bpy.data.worlds.new('_BakeWorld')
    sc.world.light_settings.distance = 0.03
    return gpu

def new_image(name, size, non_color=True, fill=(0, 0, 0, 1)):
    if name in bpy.data.images: bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.generated_color = fill
    if non_color: img.colorspace_settings.name = 'Non-Color'
    return img

def stash_tree(m):
    """remember the material's nodes / links so the temporary bake shader can be removed afterwards"""
    return set(n.name for n in m.node_tree.nodes)

def restore_tree(m, keep):
    for n in list(m.node_tree.nodes):
        if n.name not in keep: m.node_tree.nodes.remove(n)

def gcoords(nt):
    """shader nodes giving the G-frame position (mm) as separate Y and Z floats + the X float"""
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    def lin(src, mul, add):
        m = nt.nodes.new('ShaderNodeMath'); m.operation = 'MULTIPLY_ADD'
        nt.links.new(src, m.inputs[0]); m.inputs[1].default_value = mul; m.inputs[2].default_value = add; return m.outputs[0]
    X = lin(sep.outputs['X'], 1000.0, -SP.G2F[0]); Y = lin(sep.outputs['Y'], -1000.0, -SP.G2F[1]); Z = lin(sep.outputs['Z'], 1000.0, -SP.G2F[2])
    return X, Y, Z

def math_node(nt, op, a, b=None, clamp=False):
    m = nt.nodes.new('ShaderNodeMath'); m.operation = op; m.use_clamp = clamp
    if isinstance(a, (int, float)): m.inputs[0].default_value = a
    else: nt.links.new(a, m.inputs[0])
    if b is not None:
        if isinstance(b, (int, float)): m.inputs[1].default_value = b
        else: nt.links.new(b, m.inputs[1])
    return m.outputs[0]

def curvature_shader(m):
    """temporary emission shader: 0.5 + 0.5 * convex - 0.5 * concave"""
    nt = m.node_tree; out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    bev = nt.nodes.new('ShaderNodeBevel'); bev.samples = 8; bev.inputs['Radius'].default_value = 0.0009
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    nt.links.new(bev.outputs['Normal'], dot.inputs[0]); nt.links.new(geo.outputs['Normal'], dot.inputs[1])
    edge = math_node(nt, 'MULTIPLY', math_node(nt, 'SUBTRACT', 1.0, dot.outputs['Value']), 9.0, clamp=True)
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion'); ao.only_local = True; ao.samples = 16; ao.inputs['Distance'].default_value = 0.0025
    open_ = math_node(nt, 'POWER', ao.outputs['AO'], 3.0)
    convex = math_node(nt, 'MULTIPLY', edge, open_)
    concave = math_node(nt, 'MAXIMUM', math_node(nt, 'MULTIPLY', edge, math_node(nt, 'SUBTRACT', 1.0, open_)),
                        math_node(nt, 'MULTIPLY', math_node(nt, 'SUBTRACT', 1.0, ao.outputs['AO']), 0.6))
    v = math_node(nt, 'ADD', 0.5, math_node(nt, 'MULTIPLY', math_node(nt, 'SUBTRACT', convex, concave), 0.5), clamp=True)
    em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(v, em.inputs['Color']); nt.links.new(em.outputs['Emission'], out.inputs['Surface'])

def receiver_bump_shader(m):
    """temporary shader: engraved markings on the receiver's left (+X) faces, 0.3 mm deep, from the PIL markings mask"""
    nt = m.node_tree; out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    X, Y, Z = gcoords(nt)
    # mask image: u = -Y / 200 mm (so text reads front-to-rear as seen from the left), v = (Z + 80) / 80 mm
    uu = nt.nodes.new('ShaderNodeMath'); uu.operation = 'MULTIPLY'; nt.links.new(Y, uu.inputs[0]); uu.inputs[1].default_value = -1.0 / MARK_LEN
    vv = nt.nodes.new('ShaderNodeMath'); vv.operation = 'MULTIPLY_ADD'; nt.links.new(Z, vv.inputs[0]); vv.inputs[1].default_value = 1.0 / MARK_H; vv.inputs[2].default_value = 1.0
    comb = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(uu.outputs[0], comb.inputs['X']); nt.links.new(vv.outputs[0], comb.inputs['Y'])
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(MARKINGS, check_existing=True)
    tex.image.colorspace_settings.name = 'Non-Color'; tex.extension = 'EXTEND'; tex.interpolation = 'Cubic'   # white border = surface
    nt.links.new(comb.outputs['Vector'], tex.inputs['Vector'])
    geo = nt.nodes.new('ShaderNodeNewGeometry'); sepn = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Normal'], sepn.inputs['Vector'])
    facing = math_node(nt, 'GREATER_THAN', sepn.outputs['X'], 0.9)
    outer = math_node(nt, 'GREATER_THAN', X, 13.2)
    mask = math_node(nt, 'MULTIPLY', facing, outer)
    h = math_node(nt, 'SUBTRACT', 1.0, math_node(nt, 'MULTIPLY', mask, math_node(nt, 'SUBTRACT', 1.0, tex.outputs['Color'])))   # 1 = surface, 0 = engraved
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Distance'].default_value = 0.0003; bump.inputs['Strength'].default_value = 1.0
    nt.links.new(h, bump.inputs['Height'])
    bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse'); nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

def polymer_bump_shader(m):
    """temporary shader: A2 grip diamond checkering (1.55 mm pitch pyramids) on the side panels + back-strap grooves; the
    flip-up sights' stipple panels (pass 4)"""
    import parts_lower as PL
    nt = m.node_tree; out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    X, Y, Z = gcoords(nt)
    ay, az = PL.GRIP_AXIS                                   # down the grip, (Y, Z)
    oy, oz = PL.FRONT[0]                                    # grip top front
    # s = along the axis from the top front, d = perpendicular toward the front strap
    dy = nt.nodes.new('ShaderNodeMath'); dy.operation = 'SUBTRACT'; nt.links.new(Y, dy.inputs[0]); dy.inputs[1].default_value = oy
    dz = nt.nodes.new('ShaderNodeMath'); dz.operation = 'SUBTRACT'; nt.links.new(Z, dz.inputs[0]); dz.inputs[1].default_value = oz
    s = math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', dy.outputs[0], ay), math_node(nt, 'MULTIPLY', dz.outputs[0], az))
    d = math_node(nt, 'ADD', math_node(nt, 'MULTIPLY', dy.outputs[0], -az), math_node(nt, 'MULTIPLY', dz.outputs[0], ay))
    p = 1.55
    def tri(x):   # triangle wave 0..1..0 with period 1
        fr = math_node(nt, 'FRACT', x); return math_node(nt, 'SUBTRACT', 1.0, math_node(nt, 'ABSOLUTE', math_node(nt, 'SUBTRACT', math_node(nt, 'MULTIPLY', fr, 2.0), 1.0)))
    a = math_node(nt, 'MULTIPLY', math_node(nt, 'ADD', s, d), 1.0 / p); b = math_node(nt, 'MULTIPLY', math_node(nt, 'SUBTRACT', s, d), 1.0 / p)
    pyr = math_node(nt, 'MULTIPLY', tri(a), tri(b))
    def inrange(v, lo, hi): return math_node(nt, 'MULTIPLY', math_node(nt, 'GREATER_THAN', v, lo), math_node(nt, 'LESS_THAN', v, hi))
    geo = nt.nodes.new('ShaderNodeNewGeometry'); sepn = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Normal'], sepn.inputs['Vector'])
    side = math_node(nt, 'GREATER_THAN', math_node(nt, 'ABSOLUTE', sepn.outputs['X']), 0.82)
    panel = math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', inrange(s, 14.0, 98.0), inrange(d, -33.0, -6.0)), side)
    ingrip = inrange(Y, -232.0, -132.0)
    check = math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', pyr, panel), ingrip)
    # back strap: faces looking backward along -d (Blender normal y > 0.55 = UE -Y), grooves along the axis, 1.8 mm pitch
    back = math_node(nt, 'GREATER_THAN', sepn.outputs['Y'], 0.55)
    gro = tri(math_node(nt, 'MULTIPLY', X, 1.0 / 1.8))
    strap = math_node(nt, 'MULTIPLY', math_node(nt, 'MULTIPLY', gro, math_node(nt, 'MULTIPLY', back, inrange(s, 12.0, 100.0))), ingrip)
    h = math_node(nt, 'MAXIMUM', check, strap)
    # pass 4: generic stippled recessed panels on the flip-up sights where a maker's mark would sit (no logo / lettering);
    # regions are G boxes on |X|, Y, Z + the face-normal axis, published by parts_sights.py as Part.stipple
    regs = []
    for n in ('SM_AR15_BUIS', 'SM_AR15_FrontBUIS'):
        Q = L.PARTS.get(n); regs += list(getattr(Q, 'stipple', None) or []) if Q else []
    if regs:
        tc = nt.nodes.new('ShaderNodeTexCoord'); vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'F1'
        vo.inputs['Scale'].default_value = 1000.0; nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])      # ~1 mm cells (4 px)
        dome = math_node(nt, 'SUBTRACT', 1.0, math_node(nt, 'MINIMUM', math_node(nt, 'MULTIPLY', vo.outputs['Distance'], 1.9), 1.0))
        ax = math_node(nt, 'ABSOLUTE', X); nab = [math_node(nt, 'ABSOLUTE', sepn.outputs[c]) for c in ('X', 'Y', 'Z')]
        masks = {False: None, True: None}
        for r in regs:
            m_ = math_node(nt, 'MULTIPLY', inrange(ax, *r['ax']), inrange(Y, *r['y']))
            m_ = math_node(nt, 'MULTIPLY', m_, inrange(Z, *r['z']))
            m_ = math_node(nt, 'MULTIPLY', m_, math_node(nt, 'GREATER_THAN', nab[r['n']], 0.8))
            k = bool(r.get('seam')); masks[k] = m_ if masks[k] is None else math_node(nt, 'MAXIMUM', masks[k], m_)
        if masks[True] is not None:           # raised parting lines
            h = math_node(nt, 'MAXIMUM', h, math_node(nt, 'MULTIPLY', masks[True], 0.35))
        if masks[False] is not None:          # recessed panel (-0.5) with stipple domes in it (+0.25); added last (negative)
            panel = math_node(nt, 'SUBTRACT', math_node(nt, 'MULTIPLY', dome, 0.25), 0.5)
            h = math_node(nt, 'ADD', h, math_node(nt, 'MULTIPLY', panel, masks[False]))
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Distance'].default_value = 0.00045; bump.inputs['Strength'].default_value = 1.0
    nt.links.new(h, bump.inputs['Height'])
    bsdf = nt.nodes.new('ShaderNodeBsdfDiffuse'); nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

def bake_object(o, kind, sizes, prefix, shader=None, slots=None, non_color=True, samples=64, tag='AO', occluders=(), names=None):
    """bake every material slot of `o` (or `slots`) into its own image: kind 'AO' | 'EMIT' | 'NORMAL'.  occluders: objects
    that stay in the scene (they shadow `o` but are not baked); names: {slot: output path} instead of <prefix>_<slot>_<tag>"""
    sc = bpy.context.scene; sc.cycles.samples = samples
    imgs = {}; keeps = {}
    mats = [m for m in o.data.materials if m and (slots is None or m.name in slots)]
    for m in mats:
        keeps[m.name] = stash_tree(m)
        if shader: shader(m)
        img = new_image('%s_%s_%s' % (prefix, m.name, tag), sizes[m.name], non_color=non_color, fill=(0.5, 0.5, 1.0, 1) if kind == 'NORMAL' else (0, 0, 0, 1))
        tn = m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image = img; m.node_tree.nodes.active = tn
        imgs[m.name] = img
    # materials that are NOT baked still need an active image node somewhere harmless: bake only selected slots via a
    # throwaway image so Cycles does not complain
    for m in o.data.materials:
        if m and m.name not in imgs:
            keeps[m.name] = stash_tree(m); dummy = new_image('_dummy_%s' % m.name, 64)
            tn = m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image = dummy; m.node_tree.nodes.active = tn
    for x in bpy.context.view_layer.objects: x.select_set(False)
    # only the baked object may occlude: the parts, the other gun, LODs and the skeletal copy share its space
    keep = set(x.name for x in occluders)
    hidden = [x for x in bpy.data.objects if x is not o and x.type == 'MESH' and not x.hide_render and x.name not in keep]
    for x in occluders: x.hide_render = False
    for x in hidden: x.hide_render = True
    o.hide_render = False; o.select_set(True); bpy.context.view_layer.objects.active = o
    t = time.time()
    if kind == 'NORMAL':
        bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', use_clear=True)
    else:
        bpy.ops.object.bake(type=kind, use_clear=True)
    for x in hidden: x.hide_render = False
    paths = {}
    for name, img in imgs.items():
        p = (names or {}).get(name) or os.path.join(BAKE, '%s_%s_%s.png' % (prefix, name, tag))
        img.filepath_raw = p; img.file_format = 'PNG'; img.save(); paths[name] = p
    for m in o.data.materials:
        if m: restore_tree(m, keeps[m.name])
    for img in list(bpy.data.images):
        if img.name.startswith('_dummy_'): bpy.data.images.remove(img)
    log('BAKE %-6s %-18s %s  %.1fs' % (kind, o.name, ','.join(imgs), time.time() - t))
    return paths

def markings_mask():
    post = os.path.join(L.HERE, 'ar15_post.py')
    r = subprocess.run(['python', post, 'markings', MARKINGS], capture_output=True, text=True)
    if r.returncode: log('markings mask FAILED', r.stderr[-1500:])
    return os.path.exists(MARKINGS)

def run(guns):
    t0 = time.time(); os.makedirs(BAKE, exist_ok=True)
    import ar15_assemble as A
    at = A.REPORT['atlases']
    def size_for(gun_name, slot):
        if slot == 'Handguard': return at['MLOK_Handguard' if gun_name == 'SM_AR15_MLOK' else 'M4Quad_Handguard']['texture']
        return at['Kit_%s' % slot]['texture']
    gpu = setup_cycles(64); log('BAKE device: %s' % ('GPU' if gpu else 'CPU'))
    have_marks = markings_mask()
    out = {}
    for g in guns.values():
        o = g['obj']; name = o.name
        sizes = {m.name: size_for(name, m.name) for m in o.data.materials}
        res = {}
        res['AO'] = bake_object(o, 'AO', sizes, name, samples=96, tag='AO')
        res['Curv'] = bake_object(o, 'EMIT', sizes, name, shader=curvature_shader, samples=24, tag='Curv')
        if have_marks:
            res['N_Receiver'] = bake_object(o, 'NORMAL', sizes, name, shader=receiver_bump_shader, slots=['Receiver'], samples=8, tag='N')
        res['N_Polymer'] = bake_object(o, 'NORMAL', sizes, name, shader=polymer_bump_shader, slots=['Polymer'], samples=8, tag='N')
        out[name] = res
    # the magazine (its own atlases)
    mag = L.PARTS.get('SM_AR15_Mag30')
    if mag:
        # the loaded magazine (magazine + top round) in one bake: the round shadows the follower and the lips, the lips the round
        import ar15_assemble as A
        objs = [mag.obj] + ([L.PARTS['SM_AR15_MagRound'].obj] if 'SM_AR15_MagRound' in L.PARTS else [])
        j = A.join_copies(objs, '_bake_mag_loaded')
        sizes = {m.name: at[A.atlas_of('SM_AR15_MagRound' if m.name == 'Brass' else 'SM_AR15_Mag30', m.name)]['texture'] for m in j.data.materials}
        out['SM_AR15_Mag30'] = dict(AO=bake_object(j, 'AO', sizes, 'SM_AR15_Mag30', samples=96, tag='AO'),
                                    Curv=bake_object(j, 'EMIT', sizes, 'SM_AR15_Mag30', shader=curvature_shader, samples=24, tag='Curv'))
        L.kill(j)
    json.dump(out, open(os.path.join(BAKE, 'bakes.json'), 'w'), indent=1)
    r = subprocess.run(['python', os.path.join(L.HERE, 'ar15_post.py'), 'packmasks', BAKE], capture_output=True, text=True)
    log('BAKE ' + (r.stdout.strip() or r.stderr[-400:]))
    log('BAKES done in %.1fs' % (time.time() - t0))
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    return out
