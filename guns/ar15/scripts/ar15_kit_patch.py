"""ar15_kit_patch.py - pass 4 + 4b, INCREMENTAL patch of the exported kit (entry point; supersedes running
ar15_sights_patch.py, whose sight / render helpers it reuses):

    pass 4   the flip-up sights rebuilt as polymer MBUS-3-style sights (parts_sights.py) + SM_AR15_Sights_BUIS_Set_Stowed
    pass 4b  the fire-control group fixed from refs 05 / 06 (user: "our trigger assembly is completely backwards"): the
             trigger blade hangs under the trigger pin in the REAR half of the guard opening with a concave finger (front)
             face and the tip curling forward, a disconnector in the trigger's top, the guard opening's rear wall moved back
             to the rear pin, the floor slot moved under the pin, a trigger-tail cut-away on the selector drum

Every part keeps the UVs it had in out/AR15_master.blend wherever its triangles are unchanged (per-triangle match on vertex
positions and slot); only new triangles are unwrapped and packed into free space of their atlas at its texel density.  The
game atlases are re-baked in the default build (context A) and composited back ONLY inside the islands of the parts whose
surroundings changed (REBAKE), so the AO under the old sight bases and the old trigger blade is gone and nothing else moves.
Then: the changed game meshes + LODs, all game socket files, the legacy assembled guns (+LODs, per-gun bakes, sockets), the
skeletal mesh and every part FBX are re-exported; the master blend is saved with the new state (so the next patch matches
against it); renders; VERIFY.

    "D:/Blender/blender.exe" -b --factory-startup --python Tools/bpy/ar15/ar15_kit_patch.py [-- --norender]"""
import sys, os, json, math, time, hashlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import bpy, bmesh
import numpy as np
from mathutils import Vector as V, Matrix
import ar15_lib as L
import ar15_spec as SP
import ar15_sights_patch as SPATCH

MASTER = os.path.join(L.OUT, 'AR15_master.blend')
GBAKE = os.path.join(L.OUT, 'bake', 'game')
TMP = os.path.join(L.OUT, 'bake', '_patch_tmp'); os.makedirs(TMP, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SIGHTS = ('SM_AR15_BUIS', 'SM_AR15_FrontBUIS')
FCG = ('SM_AR15_LowerReceiver', 'SM_AR15_Trigger', 'SM_AR15_Selector')
# parts whose game-atlas islands are re-baked: the changed parts and their neighbours (old sight-base shadows on the
# receiver rail / handguard rail, the old blade's shadow on the guard, the grip front next to the new blade)
REBAKE = SIGHTS + FCG + ('SM_AR15_UpperReceiver', 'SM_AR15_HandguardMLOK', 'SM_AR15_Grip', 'SM_AR15_LowerPins', 'SM_AR15_MagCatch')
GAME_EXPORT = ('SM_AR15_Lower', 'SM_AR15_Sights_BUIS_Set', 'SM_AR15_Sights_BUIS_Rear', 'SM_AR15_Sights_BUIS_Set_Stowed')
def log(*a): L.log(*a)
post, uv_arr, faces_of, tris_of, _islands = SPATCH.post, SPATCH.uv_arr, SPATCH.faces_of, SPATCH.tris_of, SPATCH._islands

def md5s(d, ext='.png'):
    return {f: hashlib.md5(open(os.path.join(d, f), 'rb').read()).hexdigest() for f in sorted(os.listdir(d)) if f.endswith(ext)}

# ------------------------------------------------------------------------------------------------ 1. UV transfer
def _tri_keys(me, mats):
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = np.round(co.reshape(-1, 3) * 1e5).astype(np.int64)
    lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt); assert (lt == 3).all(), 'not triangulated'
    lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    out = []
    for f in range(len(me.polygons)):
        vs = [tuple(co[lv[3 * f + k]]) for k in range(3)]
        out.append((tuple(sorted(vs)), vs))                 # geometry only (render copies of the slot materials have other names)
    return out

def transfer_uvs():
    """per-triangle UV transfer from the master; returns {part: [new face indices]}"""
    with bpy.data.libraries.load(MASTER, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in L.PARTS]
    old = {}
    for o in dst.objects:
        n = o.name
        if len(n) > 4 and n[-4] == '.' and n[-3:].isdigit(): n = n[:-4]
        old[n] = o
    new = {}; stats = {}
    for name, P in L.PARTS.items():
        me = P.obj.data
        if not me.uv_layers: me.uv_layers.new(name='UVMap')
        nm = [m.name.split('.')[0] for m in me.materials]
        o = old.get(name)
        if o is None:
            new[name] = list(range(len(me.polygons))); stats[name] = (0, len(me.polygons)); continue
        om = o.data; ouv = uv_arr(om); omats = [m.name.split('.')[0] for m in om.materials]
        table = {}
        for f, (key, vs) in enumerate(_tri_keys(om, omats)):
            table[key] = {v: ouv[3 * f + k] for k, v in enumerate(vs)}
        nuv = np.zeros((len(me.loops), 2)); miss = []
        for f, (key, vs) in enumerate(_tri_keys(me, nm)):
            hit = table.get(key)
            if hit is None: miss.append(f); continue
            for k, v in enumerate(vs): nuv[3 * f + k] = hit[v]
        me.uv_layers.active.data.foreach_set('uv', nuv.ravel())
        if miss: new[name] = miss
        stats[name] = (len(me.polygons) - len(miss), len(miss))
    for o in dst.objects: L.kill(o)
    for lib in list(bpy.data.libraries): bpy.data.libraries.remove(lib)      # the master can be saved over later
    for n, (a, b) in stats.items():
        if b: log('UV %-26s %6d triangles kept, %5d new' % (n, a, b))
    log('UV transfer: %d parts unchanged, %d with new triangles' % (sum(1 for a, b in stats.values() if not b), len(new)))
    return new, stats

# ------------------------------------------------------------------------------------------------ 2. pack new faces
def place_new(slot, atlas, items, new, at, chunk_mm=70.0, allow_scale=False):
    """unwrap the new `slot` faces of `items` [(part, faces)] and pack them at the atlas texel density into its free space
    (occupied = every other kit face in that atlas): largest free square first, as many islands as fit, repeat"""
    import ar15_assemble as A
    occ = []
    for n, Q in L.PARTS.items():
        if Q.atlas != 'kit' or slot not in Q.info['slots'] or A.atlas_of(n, slot) != atlas: continue
        nf = set(new.get(n, ()))
        occ += tris_of(Q.obj, [f for f in faces_of(Q.obj, slot) if f not in nf])
    bm = bmesh.new(); counts = []
    for n, fs in items:
        me = L.PARTS[n].obj.data.copy(); b = bmesh.new(); b.from_mesh(me); keep = set(fs); b.faces.ensure_lookup_table()
        bmesh.ops.delete(b, geom=[f for f in b.faces if f.index not in keep], context='FACES'); b.to_mesh(me); b.free()
        counts.append(len(me.polygons)); bm.from_mesh(me); bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new('_new_uv'); bm.to_mesh(me); bm.free()
    t = bpy.data.objects.new('_new_uv', me); bpy.context.scene.collection.objects.link(t)
    A.unwrap_part(t, chunk_mm=chunk_mm)
    D = at[atlas]['texel_px_per_cm']; size = at[atlas]['texture']; k = D * 100.0 / size
    uvt = uv_arr(me) * k
    isl = _islands(me, uvt)
    def bbox_area(fs):
        ls = np.concatenate([np.arange(me.polygons[f].loop_start, me.polygons[f].loop_start + me.polygons[f].loop_total) for f in fs])
        ext = uvt[ls].max(0) - uvt[ls].min(0); return float(ext[0] * ext[1]), float(ext.max())
    isl.sort(key=lambda fs: -bbox_area(fs)[0])
    final = uvt.copy(); squares = []; remaining = list(isl); scaled = []
    while remaining:
        tp = os.path.join(TMP, 'occ.npy'); np.save(tp, np.array(occ, np.float32))
        sq = json.loads(post('freesquare', tp, 1024, 3).strip().splitlines()[-1])
        cap = sq['size'] ** 2 * 0.5; batch = []; used = 0.0
        for fs in remaining:
            ar, ex = bbox_area(fs)
            if ex > sq['size'] * 0.95: continue
            if used + ar <= cap or not batch: batch.append(fs); used += ar
        if not batch and allow_scale:
            # no island fits this (largest remaining) square: scale the longest one down to fit it - long single triangles
            # (n-gon fans of the receiver floor / underside) cannot be split by chunking
            fs = max(remaining, key=lambda q: bbox_area(q)[1]); ex = bbox_area(fs)[1]; f = 0.9 * sq['size'] / ex
            if f < 0.3:
                L.kill(t); raise RuntimeError('%s: island %.3f UV would need scale %.2f' % (atlas, ex, f))
            ls = np.concatenate([np.arange(me.polygons[q].loop_start, me.polygons[q].loop_start + me.polygons[q].loop_total) for q in fs])
            mn = uvt[ls].min(0); uvt[ls] = mn + (uvt[ls] - mn) * f; scaled.append(round(f, 3)); batch = [fs]
        if not batch:
            L.kill(t); raise RuntimeError('%s: no free square large enough for the biggest island' % atlas)
        while True:
            faces = sorted(f for fs in batch for f in fs)
            sub = me.copy(); b2 = bmesh.new(); b2.from_mesh(sub); fi = b2.faces.layers.int.new('_fi')
            for f in b2.faces: f[fi] = f.index
            keep = set(faces); b2.faces.ensure_lookup_table()
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if f.index not in keep], context='FACES'); b2.to_mesh(sub); b2.free()
            so = bpy.data.objects.new('_new_sub', sub); bpy.context.scene.collection.objects.link(so)
            su = uv_arr(sub); fmap = np.empty(len(sub.polygons), np.int64); sub.attributes['_fi'].data.foreach_get('value', fmap)
            for j, p in enumerate(sub.polygons):
                q = me.polygons[fmap[j]]; su[p.loop_start:p.loop_start + p.loop_total] = uvt[q.loop_start:q.loop_start + q.loop_total] / sq['size']
            sub.uv_layers.active.data.foreach_set('uv', su.ravel())
            A.select_only([so], so)
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.pack_islands(rotate=True, scale=False, margin_method='FRACTION', margin=0.0012 / sq['size'], shape_method='CONCAVE')
            bpy.ops.object.mode_set(mode='OBJECT')
            su = uv_arr(sub); lo, hi = su.min(0), su.max(0)
            if float((hi - lo).max()) <= 1.0 or len(batch) == 1: break
            L.kill(so); batch = batch[:-1]
        su = (su - lo) / max(1.0, float((hi - lo).max())); su = np.array((sq['u0'], sq['v0'])) + su * sq['size']
        for j, p in enumerate(sub.polygons):
            q = me.polygons[fmap[j]]; final[q.loop_start:q.loop_start + q.loop_total] = su[p.loop_start:p.loop_start + p.loop_total]
            ls = list(p.loop_indices)
            for kk in range(1, len(ls) - 1): occ.append([su[ls[0]], su[ls[kk]], su[ls[kk + 1]]])
        L.kill(so)
        done = set(id(fs) for fs in batch); remaining = [fs for fs in remaining if id(fs) not in done]
        squares.append(dict(sq, islands=len(batch)))
    j0 = 0; a3 = 0.0; ua = 0.0
    for (n, fs), cnt in zip(items, counts):
        mo = L.PARTS[n].obj.data; pu = uv_arr(mo); fs = sorted(fs); assert len(fs) == cnt
        for j, f in enumerate(fs):
            p = mo.polygons[f]; q = me.polygons[j0 + j]; pu[p.loop_start:p.loop_start + p.loop_total] = final[q.loop_start:q.loop_start + q.loop_total]
        mo.uv_layers.active.data.foreach_set('uv', pu.ravel()); j0 += cnt
        a3 += sum(mo.polygons[f].area for f in fs) * 1e4; ua += A.tri_uv_area(mo, uv_arr(mo), np.array(fs)).sum()
    dens = size * math.sqrt(ua / a3) if a3 else 0.0
    L.kill(t)
    log('PACK %-12s %-8s %5d new faces (%s), %.1f cm2, %d islands in %d free squares at %.2f px/cm (kit %.2f)' %
        (atlas, slot, sum(counts), ', '.join('%s %d' % (n.replace('SM_AR15_', ''), len(f)) for n, f in items), a3, len(isl), len(squares), dens, D))
    if scaled: log('PACK %s: %d long islands scaled to fit the free space (factors %s, i.e. down to %.1f px/cm)' % (atlas, len(scaled), scaled, D * min(scaled)))
    return dict(atlas=atlas, slot=slot, faces=sum(counts), parts={n: len(f) for n, f in items}, area_cm2=round(a3, 2), islands=len(isl),
                squares=len(squares), density_px_per_cm=round(dens, 2), scaled_islands=scaled)

def pack_all(new, at):
    import ar15_assemble as A
    groups = {}
    for n, fs in new.items():
        P = L.PARTS[n]; mo = P.obj.data; names = [m.name.split('.')[0] for m in mo.materials]
        mi = np.empty(len(mo.polygons), np.int64); mo.polygons.foreach_get('material_index', mi)
        for slot in set(names):
            sf = [f for f in fs if names[mi[f]] == slot]
            if sf: groups.setdefault((slot, A.atlas_of(n, slot)), []).append((n, sf))
    out = []
    for (slot, atlas), items in sorted(groups.items()):
        for chunk, sc in ((70.0, False), (30.0, False), (30.0, True)):      # fragmented free space: smaller chunks, then scaling
            try: out.append(dict(place_new(slot, atlas, items, new, at, chunk, sc), chunk_mm=chunk)); break
            except RuntimeError as e: log('PACK %s: %s with %.0f mm chunks - retrying smaller' % (atlas, e, chunk))
        else: raise RuntimeError('%s: the new faces do not fit its free space' % atlas)
    return out

# ------------------------------------------------------------------------------------------------ 3. game re-bake (context A)
def rebake_game(at):
    import ar15_bake as B, ar15_assemble as A, ar15_game as G
    B.setup_cycles(64)
    a_parts = G.LOWER + G.UPPER + ['SM_AR15_Barrel16'] + G.BARREL_COMMON + ['SM_AR15_HandguardMLOK', 'SM_AR15_Stock', 'SM_AR15_Birdcage'] + list(SIGHTS)
    oa = SPATCH._place(a_parts, True); A.reorder_slots(oa); oa.name = '_patch_bake_A'
    atl = lambda s: 'MLOK_Handguard' if s == 'Handguard' else 'Kit_%s' % s
    sizes = {m.name: at[atl(m.name)]['texture'] for m in oa.data.materials}
    names = lambda tag: {m.name: os.path.join(TMP, 'A_%s_%s.png' % (atl(m.name), tag)) for m in oa.data.materials}
    B.bake_object(oa, 'AO', sizes, 'PA', samples=96, tag='AO', names=names('AO'))
    B.bake_object(oa, 'EMIT', sizes, 'PA', shader=B.curvature_shader, samples=24, tag='Curv', names=names('Curv'))
    if B.markings_mask():
        B.bake_object(oa, 'NORMAL', sizes, 'PA', shader=B.receiver_bump_shader, slots=['Receiver'], samples=8, tag='N', names=names('N'))
    B.bake_object(oa, 'NORMAL', sizes, 'PA', shader=B.polymer_bump_shader, slots=['Polymer'], samples=8, tag='N', names=names('N'))
    L.kill(oa)
    groups = {}
    for n in REBAKE:
        o = L.PARTS[n].obj
        for slot in set(m.name.split('.')[0] for m in o.data.materials):
            groups.setdefault(atl(slot), []).extend(tris_of(o, faces_of(o, slot)))
    for atlas, tris in sorted(groups.items()):
        tp = os.path.join(TMP, 'rebake_%s_tris.npy' % atlas); np.save(tp, np.array(tris, np.float32))
        for tag in ('AO', 'Curv', 'N'):
            src = os.path.join(TMP, 'A_%s_%s.png' % (atlas, tag)); dst = os.path.join(GBAKE, '%s_%s.png' % (atlas, tag))
            if os.path.exists(src) and os.path.exists(dst): post('composite', dst, src, tp, dst, 1)
        log('REBAKE %-16s %6d triangles of %s' % (atlas, len(tris), ', '.join(n.replace('SM_AR15_', '') for n in REBAKE
                                                                            if any(atl(s) == atlas for s in L.PARTS[n].info['slots']))))
    log('REBAKE game masks: %s' % post('packmasks', GBAKE).strip())
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

# ------------------------------------------------------------------------------------------------ 4. legacy assembled guns, skeletal, parts
def legacy(at):
    """the pass-1/2/3 deliverables built from the same parts: SM_AR15_MLOK / SM_AR15_M4Quad (+LODs, UCX, sockets), their
    per-gun bakes, SK_AR15_MLOK (+rig json), every part FBX; the manifest keeps its game entries"""
    import ar15_assemble as A, ar15_bake as B
    A.REPORT.clear(); A.REPORT.update(json.load(open(os.path.join(L.OUT, 'assembly_report.json'))))
    guns = A.build_guns(); A.write_sockets(guns)
    lods = {}
    for cfg, g in guns.items():
        for ratio, lab in ((0.5, 'LOD1'), (0.2, 'LOD2')):
            o, info = A.make_lod(g, ratio, lab); o.hide_render = True; lods[o.name] = (o, info)
    sk = A.build_skeletal()
    B.setup_cycles(64); have = B.markings_mask(); res = {}
    for g in guns.values():                                         # per-gun bakes (the magazine's own bake is unchanged)
        o = g['obj']; name = o.name
        sizes = {m.name: at[('MLOK_Handguard' if name == 'SM_AR15_MLOK' else 'M4Quad_Handguard') if m.name == 'Handguard' else 'Kit_%s' % m.name]['texture']
                 for m in o.data.materials}
        r = dict(AO=B.bake_object(o, 'AO', sizes, name, samples=96, tag='AO'),
                 Curv=B.bake_object(o, 'EMIT', sizes, name, shader=B.curvature_shader, samples=24, tag='Curv'))
        if have: r['N_Receiver'] = B.bake_object(o, 'NORMAL', sizes, name, shader=B.receiver_bump_shader, slots=['Receiver'], samples=8, tag='N')
        r['N_Polymer'] = B.bake_object(o, 'NORMAL', sizes, name, shader=B.polymer_bump_shader, slots=['Polymer'], samples=8, tag='N')
        res[name] = r
    log('LEGACY per-gun masks: %s' % post('packmasks', B.BAKE).strip())
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    mp = os.path.join(L.OUT, '_export_manifest.json'); keep = json.load(open(mp))
    exp = A.export_all(guns, lods, sk)                              # rewrites the manifest: parts, guns, lods, skeletal
    for k in ('game', 'game_lods'): exp[k] = keep.get(k, {})
    json.dump(exp, open(mp, 'w'), indent=1)
    rep = A.REPORT
    rep['guns'] = {g['obj'].name: dict(tris=g['tris'], shells=g['shells'], slots=g['slots'], hulls=[h.name for h in g['hulls']],
                                       lod1=lods[g['obj'].name + '_LOD1'][1], lod2=lods[g['obj'].name + '_LOD2'][1]) for g in guns.values()}
    rep['parts'] = {n: dict(tris=P.info['tris'], slots=P.info['slots'], configs=sorted(P.configs), bone=P.bone, static=P.static,
                            errs=P.info['errs']) for n, P in L.PARTS.items()}
    json.dump(rep, open(os.path.join(L.OUT, 'assembly_report.json'), 'w'), indent=1, default=str)
    log('LEGACY exported: %s' % ', '.join(sorted(exp['guns']) + sorted(exp['lods']) + ['SK_AR15_MLOK', '%d parts' % len(exp['parts'])]))
    return guns

# ------------------------------------------------------------------------------------------------ 5. game exports
def export_game(at, packed):
    import ar15_assemble as A, ar15_game as G
    game = G.build_meshes(); socks = G.sockets(game); G.lower_hulls(game)
    G.write_sockets(game, socks)                                     # every game socket file (the Lower's Trigger moved)
    mp = os.path.join(L.OUT, '_export_manifest.json'); M = json.load(open(mp))
    jp = os.path.join(L.OUT, 'game_parts.json'); J = json.load(open(jp))
    rel = lambda p: os.path.relpath(p, L.OUT).replace('\\', '/')
    fi = SPATCH.fold_info()
    notes = {'SM_AR15_Lower': 'pass 4b: fire-control group fixed from refs 05/06 - trigger blade under the trigger pin in the rear half of the '
                              'guard opening (concave finger face, tip curling forward), disconnector, guard opening rear wall at the rear pin, '
                              'floor slot under the pin, selector tail cut-away; Trigger socket moved onto the new finger face'}
    sight_note = ('pass 4: polymer flip-up sights in the MBUS-3 style (no logo / lettering); Polymer faces in free space of Kit_Polymer, '
                  'Steel faces in free space of Kit_Steel; Kit_Receiver is no longer used by the sights')
    for n in GAME_EXPORT:
        D = game[n]; o = D['obj']; clash, old = G._named(n, o)
        path = os.path.join(G.GDIR, n + '.fbx'); A.export_fbx([o] + D['hulls'], path); co = A.coords(o)
        M['game'][n] = dict(fbx=path, tris=D['tris'], slots=D['slots'], hulls=[h.name for h in D['hulls']], lo=co.min(0).tolist(),
                            hi=co.max(0).tolist(), frame=D['frame'])
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
                     attach=dict(parent=D['attach'][0], socket=D['attach'][1]) if D['attach'] else None,
                     collision=[h.name for h in D['hulls']] or None, textures=G.textures(D, at), socket_names=[s['name'] for s in socks[n]],
                     note=notes.get(n, sight_note))
        if 'Sights' in n: entry['fold'] = {k: v for k, v in fi.items() if k == 'rear' or 'SM_AR15_FrontBUIS' in D['parts']}
        if n.endswith('_Stowed'): entry['stowed'] = True
        log('EXPORT %-30s tris %5d  LOD %s  slots %s' % (n, D['tris'], lt, ','.join(D['slots'])))
    for k in ('default', 'm4quad'):
        J['assembled_tris'][k] = sum(game[n]['tris'] for n in (J['default_build'] if k == 'default' else J['m4quad_build']))
    J['note'] = J['note'].split(' Pass 4')[0] + (' Pass 4/4b (ar15_kit_patch.py): MBUS-style sights + stowed set, fire-control group fixed; '
                                                 'see Docs/AR15_BUILD.md sections 23-24 for the re-import list.')
    json.dump(M, open(mp, 'w'), indent=1); json.dump(J, open(jp, 'w'), indent=1)
    rp = os.path.join(L.OUT, 'assembly_report.json'); R = json.load(open(rp))
    R.setdefault('game', {})['meshes'] = {n: dict(tris=D['tris'], slots=D['slots'], frame=D['frame']) for n, D in game.items()}
    R['game']['assembled_tris'] = J['assembled_tris']; json.dump(R, open(rp, 'w'), indent=1, default=str)
    return game, {n: socks[n] for n in game}, J

# ------------------------------------------------------------------------------------------------ main
def main():
    t0 = time.time()
    L.reset_scene()
    import parts_lower, parts_upper, parts_barrel, parts_handguard, parts_rear
    for m in (parts_lower, parts_upper, parts_barrel, parts_handguard, parts_rear): m.build()
    bad = [n for n, P in L.PARTS.items() if P.info['errs']]
    if bad: log('PARTS WITH ERRORS: %s' % ', '.join('%s %s' % (n, L.PARTS[n].info['errs']) for n in bad))
    at = json.load(open(os.path.join(L.OUT, 'assembly_report.json')))['atlases']
    h0 = md5s(GBAKE)
    old_trig = {s['name']: s for s in json.load(open(os.path.join(L.OUT, 'game', 'sockets', 'sockets_SM_AR15_Lower.json')))['sockets']}['Trigger']
    new, stats = transfer_uvs()
    unexpected = sorted(set(new) - set(SIGHTS) - set(FCG))
    if unexpected: log('WARNING: new triangles in parts outside the patch: %s' % ', '.join(unexpected))
    packed = pack_all(new, at)
    rebake_game(at)
    h1 = md5s(GBAKE); changed = sorted(f for f in h1 if h0.get(f) != h1[f])
    log('game textures changed by this run: %s' % ', '.join(changed))
    guns = legacy(at)
    game, gsocks, GJ = export_game(at, packed)
    import ar15_assemble as A, ar15_game as G
    trig = {s['name']: s for s in json.load(open(os.path.join(G.GSOCK, 'sockets_SM_AR15_Lower.json')))['sockets']}['Trigger']
    if '--norender' not in ARGS:
        import ar15_final as F
        rd = os.path.join(L.OUT, 'renders')
        SPATCH.beauty(True, rd, 64); SPATCH.sight_picture()
        F.run(guns, which=['assembled']); F.game_renders(GJ)
    import build_ar15 as BA
    shutil.copyfile(MASTER, os.path.join(L.OUT, 'AR15_master_pass3.blend')) if not os.path.exists(os.path.join(L.OUT, 'AR15_master_pass3.blend')) else None
    BA.master(guns)
    import ar15_verify as VF
    socks = {g['obj'].name: g['sockets'] for g in guns.values()}; socks.update(gsocks)
    rep = dict(uv=dict(new_triangles={n: len(f) for n, f in new.items()}, packed=packed), game_textures_changed_this_run=changed,
               trigger_socket=dict(old_loc_cm=old_trig['loc'], new_loc_cm=trig['loc'], rot=trig.get('rot'),
                                   bone_head_cm=json.load(open(os.path.join(L.OUT, 'rig_SK_AR15.json')))['bones']['trigger']['head_cm']),
               sights=dict(tris={n: L.PARTS[n].info['tris'] for n in SIGHTS}, fold=SPATCH.fold_info()),
               fcg_tris={n: L.PARTS[n].info['tris'] for n in FCG}, meshes={n: game[n]['tris'] for n in GAME_EXPORT})
    json.dump(rep, open(os.path.join(L.OUT, 'kit_patch_report.json'), 'w'), indent=1)
    VF.verify(os.path.join(L.OUT, '_export_manifest.json'), socks)
    log('KIT PATCH (pass 4 + 4b) done in %.1fs' % (time.time() - t0))

if __name__ == '__main__':
    main()
