"""ar15_final.py - milestone 8: final renders (Cycles, GPU) of the AR-15 kit with the baked masks in the look-dev materials.
    out/renders/
      SM_AR15_MLOK_{left,right,front34,rear34}.png, SM_AR15_M4Quad_{...}.png, *_sheet.png
      exploded_kit.png (+ labelled exploded_kit_labels.png)
      showcase_receiver_bcg.png, showcase_mlok.png, showcase_magazine.png
      sockets_SM_AR15_MLOK.png, sockets_SM_AR15_M4Quad.png (axes + labels)
      wireframe_sheet.png
Called from build_ar15.py --assemble --final (needs the bakes of the same run)."""
import bpy, bmesh, os, json, math, subprocess
import numpy as np
from mathutils import Vector as V, Matrix
import ar15_lib as L
import ar15_spec as SP
import ar15_render as RD

REN = os.path.join(L.OUT, 'renders'); os.makedirs(REN, exist_ok=True)
POST = os.path.join(L.HERE, 'ar15_post.py')
RES = (1600, 900)

def log(*a): L.log(*a)

def post(*args):
    r = subprocess.run(['python', POST] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode: log('post FAILED', r.stderr[-1500:])
    return r.returncode == 0

# ------------------------------------------------------------------------------------------------ materials with masks
def mask_paths(gun):
    B = os.path.join(L.OUT, 'bake'); out = {}
    for slot in SP.ALL_SLOTS:
        d = {}
        for tag, key in (('AO', 'ao'), ('Curv', 'curv'), ('N', 'normal')):
            p = os.path.join(B, '%s_%s_%s.png' % (gun, slot, tag))
            if os.path.exists(p): d[key] = p
        if d: out[slot] = d
    return out

def gun_materials(gun):
    """per-gun copies of the five slot materials carrying that gun's baked masks (render only; the exported slots stay clean)"""
    mats = {}
    masks = mask_paths(gun)
    RD.look_materials(masks)                       # builds the node trees on the shared slot materials
    for slot in SP.SLOTS:
        m = L.slot_mat(slot); c = m.copy(); c.name = '%s__%s' % (slot, gun); mats[slot] = c
    RD.look_materials(None)                        # shared slots back to plain look
    return mats

def assign(objs, mats):
    saved = []
    for o in objs:
        for s in o.material_slots:
            base = s.material.name.split('__')[0] if s.material else None
            if base in mats: saved.append((s, s.material)); s.material = mats[base]
    return saved

def restore(saved):
    for s, m in saved: s.material = m

# ------------------------------------------------------------------------------------------------ helpers
def cycles(samples=96, res=RES):
    sc = RD.studio('CYCLES', res, samples=samples)
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = 'OPTIX'
    except TypeError: pass
    sc.cycles.max_bounces = 6; sc.cycles.glossy_bounces = 3; sc.cycles.transparent_max_bounces = 4
    sc.view_settings.view_transform = 'AgX'
    try: sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError: pass
    return sc

def shot(objs, view, path, mood='studio', lens=85.0, fill=1.0, target=None, margin=1.0, res=RES, energy=1.0, bg=True):
    lo, hi = L.world_bounds(objs); radius = float(np.linalg.norm(hi - lo)) / 2
    c, d = RD.frame(objs, view, res, margin=margin, lens=lens, fill=fill, target=target)
    RD.light_rig(d, c, radius, mood=mood)
    for o in bpy.data.objects:
        if o.name.startswith('_L_'): o.data.energy *= energy
    if bg: RD.backdrop(RD.R['cam'].location, c, radius)
    RD.render(path, res); RD.clear_rig()
    return path

def only(objs):
    keep = set(o.name for o in objs)
    for o in bpy.data.objects:
        if o.type in ('MESH', 'CURVE', 'FONT') and not o.name.startswith('_'):
            o.hide_render = o.name not in keep
    for o in objs: o.hide_render = False

# ------------------------------------------------------------------------------------------------ shots
def assembled(guns):
    out = []
    for g in guns.values():
        o = g['obj']; mats = gun_materials(o.name); saved = assign([o], mats); only([o])
        views = []
        for v in ('left', 'right', 'front34', 'rear34'):
            p = shot([o], v, os.path.join(REN, '%s_%s.png' % (o.name, v))); views.append(p); out.append(p)
        restore(saved)
        post('sheet', os.path.join(REN, '%s_sheet.png' % o.name), '%s - %s tris, 5 slots, %d UCX hulls' % (o.name, format(g['tris'], ','), len(g['hulls'])), *views)
        log('RENDER assembled %s' % o.name)
    return out

EXPLODE = {   # G mm offsets for the exploded view (the whole kit, both handguards)
    'SM_AR15_LowerReceiver': (0, 0, -95), 'SM_AR15_Trigger': (0, 0, -170), 'SM_AR15_Hammer': (0, -10, -140),
    'SM_AR15_Selector': (75, 0, -95), 'SM_AR15_MagCatch': (-70, 0, -105), 'SM_AR15_BoltCatch': (70, 20, -60),
    'SM_AR15_LowerPins': (120, 0, -95), 'SM_AR15_Grip': (0, -20, -230),
    'SM_AR15_UpperReceiver': (0, 0, 0), 'SM_AR15_DustCover': (-70, 0, 0), 'SM_AR15_DustCoverRod': (-100, 0, -10),
    'SM_AR15_ForwardAssist': (-80, -60, 20), 'SM_AR15_ChargingHandle': (0, -140, 75), 'SM_AR15_BCG': (0, -40, 70),
    'SM_AR15_Bolt': (0, 70, 70),
    'SM_AR15_Barrel': (0, 230, 0), 'SM_AR15_BarrelNut': (0, 150, 0), 'SM_AR15_GasBlockLP': (0, 230, 95),
    'SM_AR15_GasTube': (0, 150, 60), 'SM_AR15_FrontSightBase': (0, 230, -95), 'SM_AR15_Birdcage': (0, 330, 0),
    'SM_AR15_DeltaRing': (0, 150, -60), 'SM_AR15_HandguardMLOK': (0, 230, 165), 'SM_AR15_HandguardQuad': (0, 230, -190),
    'SM_AR15_BufferTube': (0, -150, 0), 'SM_AR15_CastleNut': (0, -110, 0), 'SM_AR15_Stock': (0, -250, 0),
    'SM_AR15_BUIS': (0, -40, 125), 'SM_AR15_Mag30': (0, 30, -250),
    'SM_AR15_Barrel16': (0, 260, 48), 'SM_AR15_FrontBUIS': (0, 230, 225), 'SM_AR15_MagRound': (0, 30, -165),
}

def mag_materials():
    """look-dev copies for the magazine + cartridge (their own atlases, the loaded-magazine bake)"""
    mm = {}
    for slot in ('Receiver', 'Steel', 'Polymer', 'Brass'):
        RD.look_materials({slot: mask_paths('SM_AR15_Mag30').get(slot, {})}); c = L.slot_mat(slot).copy(); c.name = '%s__mag' % slot; mm[slot] = c
    RD.look_materials(None)
    return mm

def mag_objs():
    return [L.PARTS[n].obj for n in ('SM_AR15_Mag30', 'SM_AR15_MagRound') if n in L.PARTS]

def exploded(guns):
    parts = list(L.PARTS.values())
    objs = [P.obj for P in parts]
    mlok_mats = gun_materials('SM_AR15_MLOK'); quad_mats = gun_materials('SM_AR15_M4Quad')
    saved = []
    for P in parts:
        saved += assign([P.obj], quad_mats if P.configs == {'QUAD'} else mlok_mats)
    if 'SM_AR15_Mag30' in L.PARTS: saved += assign(mag_objs(), mag_materials())
    moves = []
    for P in parts:
        off = EXPLODE.get(P.name, (0, 0, 0)); dv = V((off[0] * L.MM, -off[1] * L.MM, off[2] * L.MM))
        P.obj.location = P.obj.location + dv; moves.append((P.obj, dv))
    bpy.context.view_layer.update()
    only(objs)
    view = (0.80, -0.30, 0.45)
    p = shot(objs, view, os.path.join(REN, 'exploded_kit.png'), res=(1600, 1000), fill=1.22)
    # label anchors: each part's visible centre projected to the image
    labels = []
    for P in parts:
        co = np.array([(P.obj.matrix_world @ v.co)[:] for v in P.obj.data.vertices])
        c = V(tuple(np.percentile(co, 50, axis=0)))
        x, y, z = RD.project([c])[0]
        labels.append(dict(xy=[x, y], text=P.label.split(' (')[0], color=[255, 200, 90]))
    J = dict(image=p, out=os.path.join(REN, 'exploded_kit_labels.png'), title='AR-15 kit - exploded (%d parts, both handguards, magazine)' % len(parts),
             labels=labels, font=15, radial=150)
    jp = os.path.join(REN, '_exploded_labels.json'); json.dump(J, open(jp, 'w'), indent=1); post('labels', jp)
    for o, dv in moves: o.location = o.location - dv
    bpy.context.view_layer.update()
    restore(saved)
    log('RENDER exploded')

def showcases(guns):
    out = []
    # 1) moody close-up: receiver + BCG, ejection-port side, cover open, carrier drawn back 26 mm
    g = guns['MLOK']['obj']; mats = gun_materials(g.name)
    parts = [P for P in L.PARTS.values() if 'MLOK' in P.configs]
    objs = [P.obj for P in parts]; saved = assign(objs, mats); only(objs)
    dc = L.PARTS['SM_AR15_DustCover']; piv = L.g2b(dc.pivot)
    R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-98.0), 4, 'Y') @ Matrix.Translation(-piv)
    old_dc = dc.obj.matrix_world.copy(); dc.obj.matrix_world = R @ old_dc
    bcg = [L.PARTS['SM_AR15_BCG'].obj, L.PARTS['SM_AR15_Bolt'].obj]
    for o in bcg: o.location.y += 0.026
    bpy.context.view_layer.update()
    tgt = L.g2b((-14.0, -66.0, 2.0))
    focus = [L.PARTS[n].obj for n in ('SM_AR15_UpperReceiver', 'SM_AR15_LowerReceiver', 'SM_AR15_DustCover')]
    p = os.path.join(REN, 'showcase_receiver_bcg.png')
    cam_dir = V((-0.86, -0.18, 0.40)).normalized()
    RD.frame(focus, tuple(cam_dir), RES, lens=85.0, fill=1.9, target=tuple(tgt))
    side = cam_dir.cross(V((0, 0, 1))).normalized()
    RD.clear_rig()
    RD.area_rect('_L_key', tgt + (cam_dir * 0.75 + V((0, 0, 0.55)) + side * 0.35).normalized() * 0.55, tgt, 6.5, 0.30, 0.18, (1.0, 0.93, 0.84))
    RD.area_rect('_L_port', tgt + (cam_dir * 1.0 - side * 0.25 + V((0, 0, 0.10))).normalized() * 0.40, tgt, 2.2, 0.06, 0.06, (1.0, 0.95, 0.9))
    RD.area_rect('_L_rim', tgt + (-cam_dir * 0.7 + V((0, 0, 0.8)) - side * 0.2).normalized() * 0.6, tgt, 9.0, 0.06, 0.9, (0.75, 0.85, 1.0))
    RD.area_rect('_L_kick', tgt + (side * 1.0 + V((0, 0, 0.2)) - cam_dir * 0.2).normalized() * 0.6, tgt, 3.0, 0.05, 0.6, (1.0, 0.9, 0.8))
    RD.backdrop(RD.R['cam'].location, tgt, 0.2, tone=(0.050, 0.052, 0.058), edge=(0.006, 0.006, 0.007))
    # the BCG in a nickel-boron skin for this shot (shows the skin path; the kit default is phosphate)
    nib = L.slot_mat('BCG').copy(); nib.name = 'BCG__NiB'; bs = nib.node_tree.nodes.get('Principled BSDF')
    if bs:
        for l in list(bs.inputs['Base Color'].links): nib.node_tree.links.remove(l)
        bs.inputs['Base Color'].default_value = (0.50, 0.50, 0.47, 1.0); bs.inputs['Metallic'].default_value = 1.0
        for l in list(bs.inputs['Metallic'].links): nib.node_tree.links.remove(l)
    saved_nib = []
    for o in bcg:
        for sl in o.material_slots: saved_nib.append((sl, sl.material)); sl.material = nib
    RD.render(p, RES); RD.clear_rig(); out.append(p)
    for sl, m in saved_nib: sl.material = m
    dc.obj.matrix_world = old_dc
    for o in bcg: o.location.y -= 0.026
    bpy.context.view_layer.update()
    # 2) M-LOK handguard close-up
    tgt = L.g2b((0.0, 150.0, 0.0))
    p = os.path.join(REN, 'showcase_mlok.png'); cam_dir = V((0.62, -0.25, 0.38)).normalized()
    RD.frame([L.PARTS['SM_AR15_HandguardMLOK'].obj], tuple(cam_dir), RES, lens=60.0, fill=1.6, target=tuple(tgt))
    RD.light_rig(cam_dir, tgt, 0.2, mood='studio'); RD.backdrop(RD.R['cam'].location, tgt, 0.3)
    RD.render(p, RES); RD.clear_rig(); out.append(p)
    restore(saved)
    # 3) the gun with the magazine inserted (M4Quad, 3/4 front)
    g = guns['QUAD']['obj']; mats = gun_materials(g.name); mags = mag_objs()
    saved = assign([g], mats) + assign(mags, mag_materials()); only([g] + mags)
    p = shot([g] + mags, (-0.70, -0.52, 0.30), os.path.join(REN, 'showcase_magazine.png'), fill=0.96); out.append(p)
    restore(saved)
    log('RENDER showcases')
    return out

def arrow_mesh(name, M, length=0.012):
    """RGB axes (X red, Y green, Z blue) as thin boxes, in a world matrix M"""
    objs = []
    for k, col in enumerate(((1, 0.1, 0.1), (0.1, 1, 0.1), (0.2, 0.4, 1))):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        s = [0.0007, 0.0007, 0.0007]; s[k] = length
        off = [0, 0, 0]; off[k] = length / 2
        bmesh.ops.transform(bm, matrix=Matrix.Translation(off) @ Matrix.Diagonal((*s, 1)), verts=bm.verts)
        me = bpy.data.meshes.new('%s_%d' % (name, k)); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new('_ax_%s_%d' % (name, k), me); bpy.context.scene.collection.objects.link(o); o.matrix_world = M
        o.data.materials.append(RD.aux_mat('_axis%d' % k, col, emit=col)); objs.append(o)
    return objs

def socket_sheet(guns):
    for cfg, g in guns.items():
        o = g['obj']; mats = gun_materials(o.name); saved = assign([o], mats); only([o])
        axes = []; labels = []
        for s in g['sockets']:
            X, Y, Z = [V((a[0], -a[1], a[2])) for a in (s['x_axis'], s['y_axis'], s['z_axis'])]
            M = Matrix((X, Y, Z)).transposed().to_4x4(); M.translation = V((s['loc'][0] / 100, -s['loc'][1] / 100, s['loc'][2] / 100))
            small = s['name'].startswith(('Rail_', 'Mlok_'))
            axes += arrow_mesh(s['name'], M, 0.006 if small else 0.016)
        for a in axes: a.hide_render = False
        view = (0.62, -0.42, 0.40)
        p = os.path.join(REN, 'sockets_%s.png' % o.name)
        lo, hi = L.world_bounds([o]); radius = float(np.linalg.norm(hi - lo)) / 2
        c, d = RD.frame([o], view, (1600, 1000), fill=0.95)
        RD.light_rig(d, c, radius); RD.backdrop(RD.R['cam'].location, c, radius)
        for x in bpy.data.objects:
            if x.name.startswith('_L_'): x.data.energy *= 0.6
        RD.render(p, (1600, 1000)); RD.clear_rig()
        for s in g['sockets']:
            if s['name'].startswith(('Rail_', 'Mlok_')) and not s['name'].endswith('_01'): continue
            pt = V((s['loc'][0] / 100, -s['loc'][1] / 100, s['loc'][2] / 100))
            x, y, z = RD.project([pt])[0]
            labels.append(dict(xy=[x, y], text=s['name'] if not s['name'].endswith('_01') else s['name'][:-3] + '_NN', color=[120, 220, 255]))
        J = dict(image=p, out=p.replace('.png', '_labels.png'), title='%s sockets (%d): X red, Y green, Z blue; rail / M-LOK slot sockets small' % (o.name, len(g['sockets'])),
                 labels=labels, font=13)
        jp = os.path.join(REN, '_sock_%s.json' % cfg); json.dump(J, open(jp, 'w'), indent=1); post('labels', jp)
        for a in axes:
            me = a.data; bpy.data.objects.remove(a); bpy.data.meshes.remove(me)
        restore(saved)
    log('RENDER sockets')

def wire_sheet(guns):
    """wireframe over shaded: a wireframe-modifier copy in emissive cyan over the shaded gun"""
    out = []
    g = guns['MLOK']['obj']; mats = gun_materials(g.name); saved = assign([g], mats)
    w = g.copy(); w.data = g.data.copy(); bpy.context.scene.collection.objects.link(w); w.name = '_wire'
    m = w.modifiers.new('wf', 'WIREFRAME'); m.thickness = 0.00012; m.use_replace = True; m.use_even_offset = False
    w.data.materials.clear(); w.data.materials.append(RD.aux_mat('_wiremat', (0.15, 0.85, 1.0), emit=(0.25, 0.85, 1.0)))
    only([g, w])
    for name, tgt, d, fill in (('receiver', (-10.0, -90.0, -10.0), (-0.75, -0.3, 0.35), 2.6), ('handguard', (0.0, 140.0, 0.0), (0.6, -0.35, 0.35), 2.0),
                               ('stock_grip', (0.0, -260.0, -60.0), (0.7, 0.3, 0.3), 2.2), ('full', None, (0.62, -0.45, 0.32), 0.96)):
        p = os.path.join(REN, '_wire_%s.png' % name)
        if tgt is None: shot([g], d, p, fill=fill)
        else:
            t = L.g2b(tgt); RD.frame([g], d, RES, lens=70.0, fill=fill, target=tuple(t))
            RD.light_rig(V(d).normalized(), t, 0.2); RD.backdrop(RD.R['cam'].location, t, 0.3); RD.render(p, RES); RD.clear_rig()
        out.append(p)
    restore(saved); L.kill(w)
    post('sheet', os.path.join(REN, 'wireframe_sheet.png'), 'SM_AR15_MLOK topology: %s tris (wireframe over shaded)' % format(guns['MLOK']['tris'], ','), *out)
    log('RENDER wireframe')

# ------------------------------------------------------------------------------------------------ pass 3: game parts
def _import(path):
    before = set(bpy.data.objects); bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]

def _sock_matrix(s):
    """socket (F frame, cm) -> Blender placement matrix for a child mesh authored in that socket's frame"""
    D = Matrix.Diagonal((1.0, -1.0, 1.0))
    RF = Matrix((s['x_axis'], s['y_axis'], s['z_axis'])).transposed()
    M = (D @ RF @ D).to_4x4(); M.translation = V((s['loc'][0], -s['loc'][1], s['loc'][2])) / 100.0
    return M

def game_renders(J):
    """the default build and the quad build rendered from the EXPORTED game FBX files, each placed by its attach socket
    (identity for the gun-frame parts), plus the assembly sheet: parts floating apart with labels, then together"""
    cycles(96)
    col = L.coll('AR15_GameRender'); meshes = {m['name']: m for m in J['meshes']}
    socks = {}
    def sock(mesh, name):
        if mesh not in socks: socks[mesh] = {s['name']: s for s in json.load(open(os.path.join(L.OUT, meshes[mesh]['sockets'])))['sockets']}
        return socks[mesh][name]
    cache = {}
    def mat(slot, tex):
        if tex['atlas'] in cache: return cache[tex['atlas']]
        mk = {k: os.path.join(L.OUT, tex[t]) for k, t in (('ao', 'ao'), ('curv', 'curv'), ('normal', 'n')) if t in tex}
        RD.look_materials({slot: mk}); m = L.slot_mat(slot).copy(); m.name = 'G_%s' % tex['atlas']; RD.look_materials(None)
        cache[tex['atlas']] = m; return m
    def load(name, barrel):
        objs = _import(os.path.join(L.OUT, meshes[name]['fbx']))
        for o in objs:
            if col not in o.users_collection:
                for c in list(o.users_collection): c.objects.unlink(o)
                col.objects.link(o)
        main = [o for o in objs if o.type == 'MESH' and not o.name.startswith('UCX_')][0]
        for o in objs:
            if o.name.startswith('UCX_'): o.hide_render = True; o.hide_viewport = True
        for sl in main.material_slots:
            base = sl.material.name.split('.')[0]; sl.material = mat(base, meshes[name]['textures'][base])
        fr = meshes[name]['frame']
        if fr == 'muzzle': main.matrix_world = _sock_matrix(sock(barrel, 'Muzzle'))
        elif fr == 'optic': main.matrix_world = _sock_matrix(sock('SM_AR15_Lower', 'Optic_Socket'))
        elif fr == 'magazine': main.matrix_world = _sock_matrix(sock('SM_AR15_Lower', 'MagazineSocket'))
        return main
    out = []
    builds = {}
    for key, names, barrel in (('default', J['default_build'], 'SM_AR15_Barrel16'), ('m4quad', J['m4quad_build'], 'SM_AR15_Barrel145')):
        builds[key] = {n: load(n, barrel) for n in names}
    def show(objs):
        for o in bpy.data.objects:
            if o.type in ('MESH', 'CURVE', 'FONT') and not o.name.startswith('_'): o.hide_render = o not in objs
        for o in objs: o.hide_render = False
    bpy.context.view_layer.update()
    d = list(builds['default'].values()); q = list(builds['m4quad'].values())
    show(d)
    for v in ('left', 'right', 'front34', 'rear34'):
        p = shot(d, v, os.path.join(REN, 'game_default_%s.png' % v)); out.append(p)
    post('sheet', os.path.join(REN, 'game_default_sheet.png'),
         'Default build from the exported game parts at their attach sockets: %s tris' % format(J['assembled_tris']['default'], ','), *out)
    show(q)
    p = shot(q, 'front34', os.path.join(REN, 'game_m4quad_front34.png')); pq = shot(q, 'left', os.path.join(REN, 'game_m4quad_left.png'))
    post('sheet', os.path.join(REN, 'game_m4quad_sheet.png'),
         'M4Quad build from the same parts (14.5 in barrel, quad + FSB, rear BUIS): %s tris' % format(J['assembled_tris']['m4quad'], ','), p, pq)
    # assembly sheet: floating apart with labels, then together (same camera)
    show(d)
    EXP = {'SM_AR15_Upper': (0, 0, 60), 'SM_AR15_Barrel16': (0, 70, 60), 'SM_AR15_HG_MLOK': (0, 140, 130), 'SM_AR15_Muzzle_A2': (0, 160, 60),
           'SM_AR15_Sights_BUIS_Set': (0, 30, 205), 'SM_AR15_Stock': (0, -120, 0), 'SM_AR15_Mag30_Loaded': (0, 20, -130)}
    view = (0.80, -0.30, 0.45)
    base = {o: o.matrix_world.copy() for o in d}
    for n, o in builds['default'].items():
        off = EXP.get(n, (0, 0, 0)); o.matrix_world = Matrix.Translation(V((off[0], -off[1], off[2])) * L.MM) @ base[o]
    bpy.context.view_layer.update()
    pe = shot(d, view, os.path.join(REN, 'game_assembly_apart.png'), res=(1600, 1000), fill=1.15)
    labels = []
    for n, o in builds['default'].items():
        co = np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]); c = V(tuple(np.percentile(co, 50, axis=0)))
        x, y, z = RD.project([c])[0]; labels.append(dict(xy=[x, y], text=n, color=[255, 200, 90]))
    jp = os.path.join(REN, '_game_labels.json')
    json.dump(dict(image=pe, out=pe.replace('.png', '_labels.png'), title='Game parts, default build: floating apart (each is attached at identity / its socket)',
                   labels=labels, font=15, radial=140), open(jp, 'w'), indent=1); post('labels', jp)
    for o in d: o.matrix_world = base[o]
    bpy.context.view_layer.update()
    pt = shot(d, view, os.path.join(REN, 'game_assembly_together.png'), res=(1600, 1000), fill=1.15)
    post('sheet', os.path.join(REN, 'game_assembly_sheet.png'), 'Assembly: the game parts apart (left) and together (right) - same camera',
         pe.replace('.png', '_labels.png'), pt)
    for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    log('RENDER game parts')
    return out

def run(guns, which=None):
    cycles(96)
    steps = [('assembled', assembled), ('exploded', exploded), ('showcases', showcases), ('sockets', socket_sheet), ('wire', wire_sheet)]
    for name, fn in steps:
        if which and name not in which: continue
        try: fn(guns)
        except Exception:
            import traceback; traceback.print_exc(); log('RENDER %s FAILED' % name)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_EEVEE'
    for o in bpy.data.objects:
        if not o.name.startswith('_') and o.type == 'MESH' and not o.name.startswith('UCX_'): o.hide_render = False
