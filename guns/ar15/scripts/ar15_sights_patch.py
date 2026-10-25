"""ar15_sights_patch.py - pass 4, INCREMENTAL: the flip-up sights rebuilt as polymer MBUS-3-style sights (parts_sights.py).
Only the sight meshes change; every other game mesh, its UVs and the textures it uses stay exactly as imported:

    1. rebuild the kit parts (deterministic) and copy every other part's UVs from out/AR15_master.blend (vertex-checked)
    2. unwrap both sights; pack their Polymer faces into free space of Kit_Polymer and their Steel faces into free space of
       Kit_Steel, at the kit texel density (the pass-3 sights' Kit_Receiver / Kit_Steel islands and the pass-3b leaf
       islands are no longer referenced; nothing else moves)
    3. bake AO + curvature (and the Polymer normal: moulded stipple where a maker's mark would sit) in the default build,
       composite them into out/bake/game/Kit_Polymer_{AO,Curv,N}.png and Kit_Steel_{AO,Curv}.png inside the new islands
       only (+1 px); repack the masks; list which game textures actually changed (hash before / after)
    4. export SM_AR15_Sights_BUIS_Set, _Rear and the new _Set_Stowed (+ LOD1/LOD2; optic frame; same sockets); update
       game_parts.json and the export manifest
    5. beauty sheets (out/renders/mbus_rear_sheet.png, mbus_front_sheet.png) and the sight picture from the Eye socket and
       from 18 cm through both builds (out/renders/buis_sightpicture.png)
    6. re-verify every exported FBX

    "D:/Blender/blender.exe" -b --factory-startup --python Tools/bpy/ar15/ar15_sights_patch.py [-- --review | --renders]
--review: steps 1 + 5 (beauty sheets only, plain look, 24 samples) into out/progress/mbus/ for geometry iteration.
--renders: only step 5 with the UVs of the saved master (use after a full build_ar15.py --assemble run).
(The incremental pass-4 delivery was superseded by the full pass-4b rebuild, see Docs/AR15_BUILD.md section 24.)
A later full build (build_ar15.py --assemble) re-packs every atlas from scratch with the same sight design."""
import sys, os, json, math, time, subprocess, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import bpy, bmesh
import numpy as np
from mathutils import Vector as V, Matrix
import ar15_lib as L
import ar15_spec as SP

MASTER = os.path.join(L.OUT, 'AR15_master.blend')
POST = os.path.join(L.HERE, 'ar15_post.py')
GBAKE = os.path.join(L.OUT, 'bake', 'game')
TMP = os.path.join(L.OUT, 'bake', '_sights_tmp'); os.makedirs(TMP, exist_ok=True)
SIGHTS = ('SM_AR15_BUIS', 'SM_AR15_FrontBUIS')
MESHES = ('SM_AR15_Sights_BUIS_Set', 'SM_AR15_Sights_BUIS_Rear', 'SM_AR15_Sights_BUIS_Set_Stowed')
SLOT_ATLAS = (('Polymer', 'Kit_Polymer'), ('Steel', 'Kit_Steel'))
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def log(*a): L.log(*a)

def post(*args):
    r = subprocess.run(['python', POST] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode: log('post FAILED', r.stderr[-1500:])
    return r.stdout

def uv_arr(me):
    a = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get('uv', a); return a.reshape(-1, 2)

def faces_of(o, slot):
    idx = [i for i, m in enumerate(o.data.materials) if m and m.name.split('.')[0] == slot]
    return [p.index for p in o.data.polygons if p.material_index in idx]

def copy_uvs(skip=SIGHTS):
    """UVs of every part except `skip` from the master, vertex-checked"""
    with bpy.data.libraries.load(MASTER, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in L.PARTS and n not in skip]
    old = {}
    for o in dst.objects:
        n = o.name
        if len(n) > 4 and n[-4] == '.' and n[-3:].isdigit(): n = n[:-4]
        old[n] = o
    for name, P in L.PARTS.items():
        if name in skip: continue
        o, me = old[name], P.obj.data
        if not me.uv_layers: me.uv_layers.new(name='UVMap')
        a = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', a)
        b = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', b)
        assert len(a) == len(b) and np.abs(a - b).max() < 1e-6 and len(o.data.loops) == len(me.loops), 'geometry changed: ' + name
        me.uv_layers.active.data.foreach_set('uv', uv_arr(o.data).ravel())
    for o in dst.objects: L.kill(o)
    for lib in list(bpy.data.libraries): bpy.data.libraries.remove(lib)      # the master can be saved over later
    log('UVs copied from the master for %d parts' % (len(L.PARTS) - len(skip)))

def tris_of(o, faces):
    uv = uv_arr(o.data); out = []
    for f in faces:
        p = o.data.polygons[f]; ls = list(p.loop_indices)
        for k in range(1, len(ls) - 1): out.append([uv[ls[0]], uv[ls[k]], uv[ls[k + 1]]])
    return out

def _islands(me, uv):
    """UV islands of a mesh: faces joined where they share a vertex with the same UV"""
    parent = list(range(len(me.polygons)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    seen = {}
    for p in me.polygons:
        for li in p.loop_indices:
            key = (me.loops[li].vertex_index, round(float(uv[li, 0]), 7), round(float(uv[li, 1]), 7))
            if key in seen:
                r0, r1 = find(seen[key]), find(p.index)
                if r0 != r1: parent[r1] = r0
            else: seen[key] = p.index
    out = {}
    for p in me.polygons: out.setdefault(find(p.index), []).append(p.index)
    return list(out.values())

# ------------------------------------------------------------------------------------------------ 2. UVs into free atlas space
def place_slot(slot, atlas, at):
    """unwrap the sights' `slot` faces and pack them AT the atlas texel density into its free space: the largest free square
    (other parts' islands = occupied) takes as many islands as fit, is marked used, and the next square is searched until
    every island is placed"""
    import ar15_assemble as A
    occ = []
    for n, Q in L.PARTS.items():
        if n in SIGHTS or Q.atlas != 'kit' or slot not in Q.info['slots'] or A.atlas_of(n, slot) != atlas: continue
        occ += tris_of(Q.obj, faces_of(Q.obj, slot))
    # temp mesh: the slot faces of both sights, in part order (BUIS faces first, then FrontBUIS)
    bm = bmesh.new(); counts = []
    for n in SIGHTS:
        me = L.PARTS[n].obj.data.copy(); b = bmesh.new(); b.from_mesh(me)
        si = [i for i, m in enumerate(me.materials) if m and m.name.split('.')[0] == slot]
        bmesh.ops.delete(b, geom=[f for f in b.faces if f.material_index not in si], context='FACES'); b.to_mesh(me); b.free()
        counts.append(len(me.polygons)); bm.from_mesh(me); bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new('_slot_uv'); bm.to_mesh(me); bm.free()
    t = bpy.data.objects.new('_slot_uv', me); bpy.context.scene.collection.objects.link(t)
    A.unwrap_part(t)
    D = at[atlas]['texel_px_per_cm']; size = at[atlas]['texture']
    k = D * 100.0 / size                                     # metres -> atlas UV units
    uvt = uv_arr(me) * k
    isl = _islands(me, uvt)
    def bbox_area(fs):
        ls = np.concatenate([np.arange(me.polygons[f].loop_start, me.polygons[f].loop_start + me.polygons[f].loop_total) for f in fs])
        ext = uvt[ls].max(0) - uvt[ls].min(0); return float(ext[0] * ext[1]), float(ext.max())
    isl.sort(key=lambda fs: -bbox_area(fs)[0])
    final = uvt.copy(); squares = []; remaining = list(isl)
    while remaining:
        tp = os.path.join(TMP, 'occ.npy'); np.save(tp, np.array(occ, np.float32))
        sq = json.loads(post('freesquare', tp, 1024, 3).strip().splitlines()[-1])
        cap = sq['size'] ** 2 * 0.5
        batch = []; used = 0.0
        for fs in remaining:
            ar, ex = bbox_area(fs)
            if ex > sq['size'] * 0.95: continue
            if used + ar <= cap or not batch: batch.append(fs); used += ar
        if not batch: raise RuntimeError('%s: no free square large enough for the biggest island' % atlas)
        while True:                                            # pack the batch; drop its smallest island while it overflows
            faces = sorted(f for fs in batch for f in fs)
            sub = me.copy(); b2 = bmesh.new(); b2.from_mesh(sub)
            fi = b2.faces.layers.int.new('_fi')
            for f in b2.faces: f[fi] = f.index
            keep = set(faces); b2.faces.ensure_lookup_table()
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES')
            b2.to_mesh(sub); b2.free()
            so = bpy.data.objects.new('_slot_sub', sub); bpy.context.scene.collection.objects.link(so)
            su = uv_arr(sub); fmap = np.empty(len(sub.polygons), np.int64); sub.attributes['_fi'].data.foreach_get('value', fmap)
            for j, p in enumerate(sub.polygons):
                q = me.polygons[fmap[j]]
                su[p.loop_start:p.loop_start + p.loop_total] = uvt[q.loop_start:q.loop_start + q.loop_total] / sq['size']
            sub.uv_layers.active.data.foreach_set('uv', su.ravel())
            A.select_only([so], so)
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.pack_islands(rotate=True, scale=False, margin_method='FRACTION', margin=0.0012 / sq['size'], shape_method='CONCAVE')
            bpy.ops.object.mode_set(mode='OBJECT')
            su = uv_arr(sub); lo, hi = su.min(0), su.max(0)
            if float((hi - lo).max()) <= 1.0 or len(batch) == 1: break
            L.kill(so); batch = batch[:-1]
        su = (su - lo) / max(1.0, float((hi - lo).max()))
        su = np.array((sq['u0'], sq['v0'])) + su * sq['size']
        for j, p in enumerate(sub.polygons):
            q = me.polygons[fmap[j]]
            final[q.loop_start:q.loop_start + q.loop_total] = su[p.loop_start:p.loop_start + p.loop_total]
            ls = list(p.loop_indices)
            for kk in range(1, len(ls) - 1): occ.append([su[ls[0]], su[ls[kk]], su[ls[kk + 1]]])
        L.kill(so)
        done = set(id(fs) for fs in batch); remaining = [fs for fs in remaining if id(fs) not in done]
        squares.append(dict(sq, islands=len(batch)))
        log('  %s batch: %d islands into a %d px square at (%.3f, %.3f)' % (atlas, len(batch), sq['px'], sq['u0'], sq['v0']))
    # back onto the parts' slot loops (same face order as the temp object)
    j0 = 0; area3 = 0.0; uva = 0.0
    import ar15_assemble as A2
    for n, cnt in zip(SIGHTS, counts):
        o = L.PARTS[n].obj; mo = o.data
        if not mo.uv_layers: mo.uv_layers.new(name='UVMap')
        pu = uv_arr(mo); sf = faces_of(o, slot); assert len(sf) == cnt
        for j, f in enumerate(sf):
            p = mo.polygons[f]; q = me.polygons[j0 + j]
            pu[p.loop_start:p.loop_start + p.loop_total] = final[q.loop_start:q.loop_start + q.loop_total]
        mo.uv_layers.active.data.foreach_set('uv', pu.ravel()); j0 += cnt
        area3 += sum(mo.polygons[f].area for f in sf) * 1e4
        uva += A2.tri_uv_area(mo, uv_arr(mo), np.array(sf)).sum()
    dens = size * math.sqrt(uva / area3)
    L.kill(t)
    log('%s: %d faces, %.1f cm2, %d islands in %d free squares of %s at %.2f px/cm (kit %.2f)' % (slot, sum(counts), area3, len(isl), len(squares), atlas, dens, D))
    return dict(atlas=atlas, squares=squares, density_px_per_cm=round(dens, 2), faces=sum(counts), area_cm2=round(area3, 2), islands=len(isl))

# ------------------------------------------------------------------------------------------------ 3. bakes
def _place(names, shift16=False):
    import ar15_assemble as A
    objs = []
    for n in names:
        c = L.PARTS[n].obj.copy(); c.data = L.PARTS[n].obj.data.copy(); bpy.context.scene.collection.objects.link(c)
        if shift16 and n == 'SM_AR15_Birdcage': c.data.transform(Matrix.Translation((0.0, -SP.BARREL16_EXT * L.MM, 0.0)))
        objs.append(c)
    A.select_only(objs, objs[0])
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]): bpy.ops.object.join()
    return objs[0]

def hashes():
    return {f: hashlib.md5(open(os.path.join(GBAKE, f), 'rb').read()).hexdigest() for f in sorted(os.listdir(GBAKE)) if f.endswith('.png')}

def bake_sights(at):
    import ar15_bake as B, ar15_game as G
    B.setup_cycles(64)
    occ = _place(G.LOWER + G.UPPER + ['SM_AR15_Barrel16'] + G.BARREL_COMMON + ['SM_AR15_HandguardMLOK', 'SM_AR15_Stock', 'SM_AR15_Birdcage'], True)
    tgt = _place(list(SIGHTS))
    sizes = {s: at[a]['texture'] for s, a in SLOT_ATLAS}
    tmp = lambda tag: {s: os.path.join(TMP, 'sights_%s_%s.png' % (s, tag)) for s, a in SLOT_ATLAS}
    B.bake_object(tgt, 'AO', sizes, 'SP', slots=['Polymer', 'Steel'], samples=96, tag='AO', occluders=[occ], names=tmp('AO'))
    B.bake_object(tgt, 'EMIT', sizes, 'SP', shader=B.curvature_shader, slots=['Polymer', 'Steel'], samples=24, tag='Curv', occluders=[occ], names=tmp('Curv'))
    B.bake_object(tgt, 'NORMAL', sizes, 'SP', shader=B.polymer_bump_shader, slots=['Polymer'], samples=8, tag='N', occluders=[occ], names=tmp('N'))
    for slot, atlas in SLOT_ATLAS:
        tris = []
        for n in SIGHTS: tris += tris_of(L.PARTS[n].obj, faces_of(L.PARTS[n].obj, slot))
        tp = os.path.join(TMP, 'sights_%s_tris.npy' % slot); np.save(tp, np.array(tris, np.float32))
        for tag in (('AO', 'Curv', 'N') if slot == 'Polymer' else ('AO', 'Curv')):
            dst = os.path.join(GBAKE, '%s_%s.png' % (atlas, tag))
            post('composite', dst, tmp(tag)[slot], tp, dst, 1)
    log('BAKE sights composited into Kit_Polymer / Kit_Steel: %s' % post('packmasks', GBAKE).strip())
    L.kill(occ); L.kill(tgt)
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

# ------------------------------------------------------------------------------------------------ 4. export
def fold_info():
    import ar15_game as G
    return G.fold_info()

def export_sights(at):
    import ar15_assemble as A, ar15_game as G
    game = G.build_meshes(); socks = G.sockets(game)
    G.write_sockets({n: game[n] for n in MESHES}, socks)
    mp = os.path.join(L.OUT, '_export_manifest.json'); M = json.load(open(mp))
    jp = os.path.join(L.OUT, 'game_parts.json'); J = json.load(open(jp))
    rel = lambda p: os.path.relpath(p, L.OUT).replace('\\', '/')
    fi = fold_info()
    note = ('pass 4: polymer flip-up sights in the MBUS-3 style (no logo / lettering); Polymer faces packed into free space of '
            'Kit_Polymer, Steel faces into free space of Kit_Steel (re-import bake/game/Kit_Polymer_Masks.png, Kit_Polymer_N.png and '
            'Kit_Steel_Masks.png with these meshes); Kit_Receiver is no longer used by the sights')
    for n in MESHES:
        D = game[n]; o = D['obj']; clash, old = G._named(n, o)
        path = os.path.join(G.GDIR, n + '.fbx'); A.export_fbx([o], path); co = A.coords(o)
        M['game'][n] = dict(fbx=path, tris=D['tris'], slots=D['slots'], hulls=[], lo=co.min(0).tolist(), hi=co.max(0).tolist(), frame=D['frame'])
        G._unname(n, o, clash, old)
        lt = []; lps = []
        for ratio, lab in ((0.5, 'LOD1'), (0.2, 'LOD2')):
            lo_, info = A.make_lod(D, ratio, lab); lo_.name = '%s_%s' % (n, lab); lo_.hide_render = True
            lp = os.path.join(G.GLOD, '%s_%s.fbx' % (n, lab)); A.export_fbx([lo_], lp); lps.append(lp)
            M['game_lods']['%s_%s' % (n, lab)] = dict(fbx=lp, lod=True, **info); lt.append(info['tris'])
        entry = next((m for m in J['meshes'] if m['name'] == n), None)
        if entry is None:
            entry = dict(name=n); i = next(k for k, m in enumerate(J['meshes']) if m['name'] == 'SM_AR15_Sights_BUIS_Rear')
            J['meshes'].insert(i + 1, entry)
        entry.update(label=D['label'], fbx=rel(path), lods=[rel(p) for p in lps], sockets=rel(os.path.join(G.GSOCK, 'sockets_%s.json' % n)),
                     slots=D['slots'], tris=D['tris'], lod_tris=lt, frame=D['frame'], frame_note=G.FRAME_TEXT[D['frame']], parts=D['parts'],
                     attach=dict(parent=D['attach'][0], socket=D['attach'][1]), collision=None, textures=G.textures(D, at),
                     socket_names=[s['name'] for s in socks[n]], note=note,
                     fold={k: v for k, v in fi.items() if k == 'rear' or 'FrontBUIS' in D['parts']})
        if n.endswith('_Stowed'): entry['stowed'] = True
        log('EXPORT %-30s tris %5d  LOD %s  slots %s' % (n, D['tris'], lt, ','.join(D['slots'])))
    for k in ('default', 'm4quad'):
        J['assembled_tris'][k] = sum(game[n]['tris'] for n in (J['default_build'] if k == 'default' else J['m4quad_build']))
    json.dump(M, open(mp, 'w'), indent=1); json.dump(J, open(jp, 'w'), indent=1)
    return game, {n: socks[n] for n in game}

# ------------------------------------------------------------------------------------------------ 5. renders
_MATS = {}
def atlas_mat(slot, atlas):
    """render copy of a slot material carrying an atlas's game masks (AO, curvature, normal)"""
    import ar15_render as RD
    if atlas in _MATS: return _MATS[atlas]
    mk = {k: os.path.join(GBAKE, '%s_%s.png' % (atlas, t)) for k, t in (('ao', 'AO'), ('curv', 'Curv'), ('normal', 'N'))
          if os.path.exists(os.path.join(GBAKE, '%s_%s.png' % (atlas, t)))}
    RD.look_materials({slot: mk}); m = L.slot_mat(slot).copy(); m.name = 'SP_' + atlas; RD.look_materials(None); _MATS[atlas] = m; return m

def _copy_obj(o, name, masks, hg='MLOK_Handguard'):
    c = o.copy(); c.data = o.data.copy(); c.name = name; bpy.context.scene.collection.objects.link(c)
    if masks:
        for s in c.material_slots:
            b = s.material.name.split('.')[0]
            s.material = atlas_mat(b, hg if b == 'Handguard' else 'Kit_%s' % b)
    return c

def beauty(masks, outdir, samples):
    """per sight: shooter-side 3/4, side, front (from the muzzle), rear (shooter's view), stowed 3/4 and stowed side; studio"""
    import ar15_render as RD, ar15_final as F, ar15_game as G
    F.cycles(samples, (1200, 900))
    if not masks: RD.look_materials(None)
    sheets = []
    # Blender view directions (subject -> camera): +X = gun left, -Y = muzzle
    for n, tag, title, views in (
            ('SM_AR15_BUIS', 'rear', 'Rear flip-up sight (polymer, MBUS-3 style): large 4.8 mm aperture on the sight line, 1.8 mm aperture rotated out of line',
             [('dep', '34', (-0.58, 0.62, 0.50)), ('dep', 'side', (-1.0, 0.02, 0.08)), ('dep', 'front', (0.10, -1.0, 0.16)),
              ('dep', 'eye', (0.0, 1.0, 0.07)), ('fold', 'stowed34', (0.50, -0.62, 0.55)), ('fold', 'stowedside', (-1.0, 0.02, 0.12))]),
            ('SM_AR15_FrontBUIS', 'front', 'Front flip-up sight (polymer, MBUS-3 style): 1.5 mm square post on the sight line, elevation drum, ears',
             [('dep', '34', (0.58, 0.62, 0.45)), ('dep', 'side', (1.0, 0.02, 0.08)), ('dep', 'front', (-0.10, -1.0, 0.14)),
              ('dep', 'eye', (0.0, 1.0, 0.07)), ('fold', 'stowed34', (0.55, -0.60, 0.55)), ('fold', 'stowedside', (1.0, 0.02, 0.12))])):
        dep = _copy_obj(L.PARTS[n].obj, 'bty_%s_dep' % tag, masks)
        fo = G.fold_copy(n); fold = _copy_obj(fo, 'bty_%s_fold' % tag, masks); L.kill(fo)
        paths = []
        for which, vname, d in views:
            objs = [dep if which == 'dep' else fold]; F.only(objs)
            p = os.path.join(outdir, 'mbus_%s_%s.png' % (tag, vname))
            F.shot(objs, d, p, lens=100.0, fill=0.84, res=(1200, 900)); paths.append(p)
        out_p = os.path.join(outdir, 'mbus_%s_sheet.png' % tag)
        post('sheetw', out_p, title, 3, 760, 'top: deployed 3/4, side, front (muzzle side) / bottom: shooter side, stowed 3/4, stowed side.  '
             'Own model; no maker logo or lettering (stipple texture panels instead).', *[paths[i] for i in (0, 1, 2, 3, 4, 5)])
        sheets.append(out_p); L.kill(dep); L.kill(fold)
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.name.startswith('_'): o.hide_render = False
    log('RENDER beauty sheets -> %s' % ', '.join(sheets))
    return sheets

def sight_picture():
    """the sight picture from the Eye socket (75 mm behind the rear aperture) and from the game's 18 cm eye relief, through
    the M-LOK set (rear + flip-up front post) and the M4Quad set (rear + A2 FSB post); a target board at 10 m"""
    import ar15_render as RD, ar15_final as F, ar15_game as G, parts_rear as PR
    F.cycles(64, (800, 560))
    def build(names, shift16):
        objs = []
        for n in names:
            c = _copy_obj(L.PARTS[n].obj, 'spx_' + n, True, 'M4Quad_Handguard' if 'Quad' in n else 'MLOK_Handguard')
            if shift16 and n == 'SM_AR15_Birdcage': c.data.transform(Matrix.Translation((0.0, -SP.BARREL16_EXT * L.MM, 0.0)))
            objs.append(c)
        return objs
    sets = {'mlok': build(G.LOWER + G.UPPER + ['SM_AR15_Barrel16'] + G.BARREL_COMMON + ['SM_AR15_HandguardMLOK', 'SM_AR15_Stock',
                                                                                        'SM_AR15_Birdcage', 'SM_AR15_BUIS', 'SM_AR15_FrontBUIS'], True),
            'quad': build(G.LOWER + G.UPPER + ['SM_AR15_Barrel'] + G.BARREL_COMMON + ['SM_AR15_HandguardQuad', 'SM_AR15_DeltaRing',
                                                                                     'SM_AR15_FrontSightBase', 'SM_AR15_Stock', 'SM_AR15_Birdcage', 'SM_AR15_BUIS'], False)}
    # target board at 10 m on the sight line: white card, black 20 cm bull, grey 50 cm ring
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    me = bpy.data.meshes.new('_target'); bm.to_mesh(me); bm.free()
    tgt = bpy.data.objects.new('_target', me); bpy.context.scene.collection.objects.link(tgt)
    tgt.location = L.g2b((0.0, 10000.0, SP.SIGHT_Z)); tgt.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    tm = bpy.data.materials.new('_targetmat'); tm.use_nodes = True; nt = tm.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeVectorMath'); sep.operation = 'LENGTH'; nt.links.new(tc.outputs['Object'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].color = (0.01, 0.01, 0.01, 1); ramp.color_ramp.elements[1].position = 0.1; ramp.color_ramp.elements[1].color = (0.75, 0.75, 0.72, 1)
    e2 = ramp.color_ramp.elements.new(0.25); e2.color = (0.35, 0.35, 0.33, 1); e3 = ramp.color_ramp.elements.new(0.27); e3.color = (0.75, 0.75, 0.72, 1)
    nt.links.new(sep.outputs['Value'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], em.inputs['Color']); em.inputs['Strength'].default_value = 1.6
    nt.links.new(em.outputs['Emission'], out.inputs['Surface']); me.materials.append(tm)
    cam = RD.R['cam']; cd = cam.data; cd.type = 'PERSP'; cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0
    cd.lens = 18.0 / math.tan(math.radians(14.0)); cd.clip_start = 0.004; cd.clip_end = 50.0          # 28 deg horizontal FOV
    paths = []; ay = PR.BUIS_APERTURE_Y
    pdir = os.path.join(L.OUT, 'progress', 'sightpicture'); os.makedirs(pdir, exist_ok=True)
    for key in ('mlok', 'quad'):
        for o in bpy.data.objects:
            if o.type == 'MESH': o.hide_render = not (o in sets[key] or o is tgt)
        for dist, tag in ((75.0, 'eye'), (180.0, '18cm')):
            e = L.g2b((0.0, ay - dist, SP.SIGHT_Z)); cam.location = e
            cam.rotation_euler = V((0.0, -1.0, 0.0)).to_track_quat('-Z', 'Y').to_euler()
            RD.clear_rig()
            RD.area_rect('_L_key', e + V((0.25, 0.10, 0.45)), L.g2b((0.0, ay + 60.0, SP.SIGHT_Z - 10.0)), 40.0, 0.5, 0.3, (1.0, 0.97, 0.92))
            RD.area_rect('_L_fill', e + V((-0.3, 0.2, 0.1)), L.g2b((0.0, ay + 60.0, SP.SIGHT_Z)), 8.0, 0.6, 0.6, (0.9, 0.94, 1.0))
            p = os.path.join(pdir, 'sp_%s_%s.png' % (key, tag)); RD.render(p, (800, 560)); RD.clear_rig()
            paths.append(p)
    out_p = os.path.join(L.OUT, 'renders', 'buis_sightpicture.png')
    post('sheet', out_p, 'Polymer flip-up sights, 4.8 mm aperture - left: Eye socket (75 mm), right: 18 cm; top: M-LOK set (flip-up front post), bottom: M4Quad set (A2 FSB post)', *paths)
    for k in sets:
        for o in sets[k]: L.kill(o)
    L.kill(tgt)
    for o in bpy.data.objects:
        if o.type == 'MESH': o.hide_render = False
    log('RENDER sight picture -> %s' % out_p)
    return out_p

# ------------------------------------------------------------------------------------------------ main
def main():
    t0 = time.time()
    L.reset_scene()
    import parts_lower, parts_upper, parts_barrel, parts_handguard, parts_rear
    for m in (parts_lower, parts_upper, parts_barrel, parts_handguard, parts_rear): m.build()
    for n in SIGHTS:
        I = L.PARTS[n].info; log('SIGHT %-18s tris %5d  nm %d  inv %d  %s' % (n, I['tris'], I['nm'], I['inv'], I['errs'] or 'OK'))
    if '--renders' in ARGS:               # after a full build: beauty sheets + sight picture from the saved master's UVs
        copy_uvs(skip=()); beauty(True, os.path.join(L.OUT, 'renders'), 64); sight_picture()
        log('SIGHTS RENDERS done in %.1fs' % (time.time() - t0)); return
    if '--review' in ARGS:
        d = os.path.join(L.OUT, 'progress', 'mbus'); os.makedirs(d, exist_ok=True)
        beauty(False, d, 24); log('SIGHTS REVIEW done in %.1fs' % (time.time() - t0)); return
    at = json.load(open(os.path.join(L.OUT, 'assembly_report.json')))['atlases']
    copy_uvs()
    info = {slot: place_slot(slot, atlas, at) for slot, atlas in SLOT_ATLAS}
    h0 = hashes()
    bake_sights(at)
    h1 = hashes(); changed = sorted(f for f in h1 if h0.get(f) != h1[f])
    log('game textures changed: %s' % ', '.join(changed))
    game, gsocks = export_sights(at)
    rd = os.path.join(L.OUT, 'renders')
    sheets = beauty(True, rd, 64)
    sp = sight_picture()
    import ar15_sockets as SK, ar15_verify as VF
    socks = {'SM_AR15_MLOK': SK.layout('MLOK', L.PARTS), 'SM_AR15_M4Quad': SK.layout('QUAD', L.PARTS)}; socks.update(gsocks)
    rep = dict(uv=info, textures_changed=changed, beauty=sheets, sight_picture=sp,
               tris={n: L.PARTS[n].info['tris'] for n in SIGHTS}, meshes={n: game[n]['tris'] for n in MESHES}, fold=fold_info(),
               mbus_height=dict(spec_aperture_over_rail_mm=36.1, ours_mm=round(SP.SIGHT_Z - SP.RAIL_TOP, 2),
                                delta_mm=round(SP.SIGHT_Z - SP.RAIL_TOP - 36.1, 2)))
    json.dump(rep, open(os.path.join(L.OUT, 'sights_patch_report.json'), 'w'), indent=1)
    VF.verify(os.path.join(L.OUT, '_export_manifest.json'), socks)
    log('SIGHTS PATCH (pass 4) done in %.1fs' % (time.time() - t0))

if __name__ == '__main__':
    main()
