"""ar15_verify.py - re-import every exported FBX into a fresh factory scene and check it (run LAST: it wipes the scene).
Checks: one render mesh with the expected name, UCX_ hulls parented + convex + closed, identity transforms (scale 1), FBX unit =
cm, closed shells, no inside-out shells, no degenerate faces, slot names from the contract in the contract order, UVs inside
0-1 and non-overlapping per slot, bounds and triangle count as exported, custom normals present; skeletal: bones, rigid
single-bone weights; sockets: each socket against the geometry it belongs to (rail tops, slot centres, magwell clearance,
surfaces, muzzle tip, aperture).  A failing FBX is deleted, as in Tools/bpy/station_props."""
import bpy, bmesh, os, json, math
import numpy as np
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
import ar15_lib as L
import ar15_spec as SP
import ar15_sockets as SK
from ar15_assemble import overlap_pct, uv_array

def fbx_unit(path):
    from io_scene_fbx import parse_fbx
    root, _ = parse_fbx.parse(path)
    def find(e, n): return [c for c in e.elems if c.id == n]
    for p in find(find(find(root, b'GlobalSettings')[0], b'Properties70')[0], b'P'):
        if p.props[0] == b'UnitScaleFactor': return p.props[4]
    return None

def fbx_model_scales(path):
    from io_scene_fbx import parse_fbx
    root, _ = parse_fbx.parse(path)
    def find(e, n): return [c for c in e.elems if c.id == n]
    out = {}
    for m in find(find(root, b'Objects')[0], b'Model'):
        for p in find(find(m, b'Properties70')[0], b'P'):
            if p.props[0] == b'Lcl Scaling': out[m.props[1].split(b'\x00')[0].decode()] = tuple(p.props[4:7])
    return out

def import_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    return list(bpy.data.objects)

def mesh_checks(o, E, errs, notes, uv_check=True):
    me = o.data
    for a in (o.scale, ):
        if any(abs(s - 1.0) > 1e-5 for s in a): errs.append('%s scale %s' % (o.name, tuple(a)))
    if o.location.length > 1e-6 or any(abs(r) > 1e-6 for r in o.rotation_euler): errs.append('%s transform not identity' % o.name)
    nm, inv, degen, shells = L.topo_check(me)
    if nm: errs.append('%d non-manifold edges' % nm)
    if inv: errs.append('%d inside-out shells' % inv)
    if degen: errs.append('%d degenerate faces' % degen)
    slots = [s.material.name for s in o.material_slots if s.material]
    brass_ok = any(o.name.startswith(b) for b in SP.BRASS_MESHES)          # the sixth slot only on the cartridge meshes
    allowed = SP.ALL_SLOTS if brass_ok else SP.SLOTS
    if any(s not in allowed for s in slots): errs.append('slot names %s' % slots)
    if slots != sorted(slots, key=SP.ALL_SLOTS.index): errs.append('slot order %s' % slots)
    if E.get('slots') and slots != E['slots']: errs.append('slots %s vs %s' % (slots, E['slots']))
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    if E.get('tris') is not None and tris != E['tris']: errs.append('tris %d vs %d' % (tris, E['tris']))
    co = np.array([(o.matrix_world @ v.co)[:] for v in me.vertices])
    if E.get('lo') is not None:
        err = max(np.abs(co.min(0) - np.array(E['lo'])).max(), np.abs(co.max(0) - np.array(E['hi'])).max())
        if err > 1e-4: errs.append('bounds error %.3f mm' % (err * 1000))
    if not me.has_custom_normals: errs.append('no custom normals')
    ov_all = {}
    if uv_check:
        if not me.uv_layers: errs.append('no UVs')
        else:
            uv = uv_array(me)
            if not ((uv >= -1e-5).all() and (uv <= 1 + 1e-5).all()): errs.append('UVs outside 0-1')
            mi = np.array([p.material_index for p in me.polygons]); ls = np.array([p.loop_start for p in me.polygons])
            for k, s in enumerate(slots):
                sel = ls[mi == k]
                if len(sel) == 0: continue
                ov, cov = overlap_pct(uv[sel.reshape(-1, 1) + np.arange(3)].reshape(-1, 3, 2), 512)
                ov_all[s] = round(ov, 3)
                if ov > 0.5: errs.append('UV overlap %s %.2f %%' % (s, ov))
    notes.append('shells %d, tris %d, slots %s, uv overlap %s' % (shells, tris, ','.join(slots), ov_all))
    return co, ov_all

def socket_checks(gun_obj, sockets, errs):
    """sockets (from ar15_sockets.layout) against the re-imported gun; geometry converted to F cm"""
    me = gun_obj.data
    vs = [V((v.co.x * 100, -v.co.y * 100, v.co.z * 100)) for v in me.vertices]
    bvh = BVHTree.FromPolygons(vs, [list(p.vertices)[::-1] for p in me.polygons])
    co = np.array([tuple(v) for v in vs]); res = {}
    bore_z = SP.G2F[2] / 10
    def hit(o, d, dist=10.0):
        loc, n, i, t = bvh.ray_cast(V(o), V(d).normalized(), dist); return t
    for s in sockets:
        c = s.get('check'); p = V(s['loc']); X = V((0, 1, 0)); Z = V(s.get('nrm') or s['z_axis']); ok = True; msg = ''
        if c is None: continue
        if c == 'muzzle':
            sel = co[(np.abs(co[:, 0]) < 1.2) & (np.abs(co[:, 2] - bore_z) < 1.2)]
            d = abs(sel[:, 1].max() - p.y); ok = d < 0.05 and abs(p.x) < 1e-3 and abs(p.z - bore_z) < 1e-3; msg = 'tip dy %.3f cm' % d
        elif c == 'axis':
            ok = abs(p.x) < 1e-3 and abs(p.z - bore_z) < 1e-3; msg = 'on the bore axis'
        elif c == 'aperture':
            # peep (pass 1-3, r 1.0 mm) or ghost ring (pass 3b, r 2.5 mm): the nearest wall is the aperture's own rim
            d = (bvh.find_nearest(p)[0] - p).length; ok = 0.07 < d < 0.32; msg = 'aperture wall %.3f cm' % d
        elif c in ('rail', 'rail_down', 'rail_right', 'rail_left'):
            t0 = hit(p + Z * 0.5, -Z); off = [hit(p + Z * 0.5 + X * k * 0.37, -Z) for k in (-1, 1)]
            ok = t0 is not None and abs(t0 - 0.8) < 0.04 and all(t is not None and abs(t - 0.5) < 0.03 for t in off)
            msg = 'slot floor %.3f, lug tops %s cm' % (t0 or -1, ['%.3f' % (t or -1) for t in off])
        elif c == 'mlok':
            t0 = hit(p + Z * 0.5, -Z, 0.5 + 0.4); Y = Z.cross(X).normalized()
            off = [hit(p + Z * 0.5 + Y * k * 0.45, -Z, 1.0) for k in (-1, 1)]
            ok = t0 is None and all(t is not None and abs(t - 0.5) < 0.04 for t in off)
            msg = 'open slot %s, surface either side %s' % (t0 is None, ['%.3f' % (t or -1) for t in off])
        elif c == 'magwell':
            # the magazine envelope (22.4 x 64.5 mm) drops straight out of the well: rays down from the socket height
            ys = [p.y - 0.58 + dy for dy in (-3.0, 0.0, 3.0)]; xs = (-1.0, 0.0, 1.0); blocked = 0
            for x in xs:
                for y in ys:
                    t = hit(V((x, y, p.z - 0.05)), (0, 0, -1), 10.0)
                    if t is not None and t < 6.0: blocked += 1
            ok = blocked == 0; msg = '%d of 9 drop rays blocked within 6 cm' % blocked
        elif c == 'tip_x':                                   # muzzle device in its own frame: tip on the +X axis
            sel = co[(np.abs(co[:, 1]) < 1.2) & (np.abs(co[:, 2]) < 1.2)]
            d = abs(sel[:, 0].max() - p.x); ok = d < 0.05 and abs(p.y) < 1e-3 and abs(p.z) < 1e-3; msg = 'tip dx %.3f cm' % d
        elif c == 'surface':
            d = (bvh.find_nearest(p)[0] - p).length; ok = d < 0.15; msg = 'surface %.3f cm' % d
        elif c == 'port':
            d = (bvh.find_nearest(p)[0] - p).length; t = hit(p, X, 3.0); ok = d < 1.3 and t is None; msg = 'port edge %.2f cm, exit clear %s' % (d, t is None)
        elif c == 'inside_diag':
            n_in = sum(1 for d in ((1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1)) if hit(p, d, 10.0) is not None)
            ok = n_in == 4; msg = 'enclosed (diagonals) %d/4' % n_in
        elif c == 'inside':
            n_in = sum(1 for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)) if hit(p, d, 10.0) is not None)
            ok = n_in == 4; msg = 'enclosed %d/4' % n_in
        res[s['name']] = (ok, msg)
        if not ok: errs.append('socket %s: %s' % (s['name'], msg))
    return res

def verify(manifest, gun_sockets):
    M = json.load(open(manifest)); out = {}; all_ok = True
    for kind in ('guns', 'parts', 'lods', 'game', 'game_lods'):
        for name, E in M.get(kind, {}).items():
            objs = import_fbx(E['fbx']); errs = []; notes = []
            meshes = [o for o in objs if o.type == 'MESH' and not o.name.startswith('UCX_')]
            ucx = sorted([o for o in objs if o.name.startswith('UCX_')], key=lambda o: o.name)
            exp_name = name
            if len(meshes) != 1 or meshes[0].name != exp_name: errs.append('render meshes %s' % [o.name for o in meshes])
            if fbx_unit(E['fbx']) != 1.0: errs.append('UnitScaleFactor %s' % fbx_unit(E['fbx']))
            if meshes:
                m = meshes[0]
                mesh_checks(m, E, errs, notes)
                if kind in ('guns', 'game'):
                    if [o.name for o in ucx] != E.get('hulls', []): errs.append('hulls %s' % [o.name for o in ucx])
                    for h in ucx:
                        if h.parent is not m: errs.append('%s not parented' % h.name)
                        closed, worst = L.hull_check(h.data)
                        if not closed or worst > 1e-5: errs.append('%s convex %.6f closed %s' % (h.name, worst, closed))
                    sk = gun_sockets.get(name)
                    if sk:
                        r = socket_checks(m, sk, errs); notes.append('sockets %d checked, %d ok' % (len(r), sum(1 for v in r.values() if v[0])))
                        out.setdefault('socket_checks', {})[name] = {k: v[1] for k, v in r.items()}
            ok = not errs; all_ok &= ok
            out[name] = dict(ok=ok, errs=errs, notes=notes)
            L.log('VERIFY %-30s %s  %s' % (name, 'OK  ' if ok else 'FAIL', '; '.join(notes)))
            for e in errs: L.log('       ! %s' % e)
            if not ok and os.path.exists(E['fbx']):
                os.remove(E['fbx']); L.log('       removed %s' % os.path.basename(E['fbx']))
    # skeletal
    E = M['skeletal']; errs = []
    objs = import_fbx(E['fbx'])
    arms = [o for o in objs if o.type == 'ARMATURE']; meshes = [o for o in objs if o.type == 'MESH']
    if len(arms) != 1 or len(meshes) != 1: errs.append('objects %s' % [o.name for o in objs])
    else:
        a, m = arms[0], meshes[0]
        names = [b.name for b in a.data.bones]
        if sorted(names) != sorted(E['bones']): errs.append('bones %s' % names)
        if fbx_unit(E['fbx']) != 1.0: errs.append('UnitScaleFactor %s' % fbx_unit(E['fbx']))
        bad = sum(1 for v in m.data.vertices if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1e-4)
        if bad: errs.append('%d vertices without one rigid weight' % bad)
        sc = max(abs(s) for s in a.scale)
        raw = fbx_model_scales(E['fbx'])
        for nm_, s_ in raw.items():
            if any(abs(c - 1.0) > 1e-6 for c in s_): errs.append('FBX node %s has scale %s' % (nm_, s_))
        nm, inv, degen, shells = L.topo_check(m.data)
        if nm or inv or degen: errs.append('topology nm %d inv %d degen %d' % (nm, inv, degen))
        notes = 'bones %d, tris %d, armature scale %.3f' % (len(names), sum(len(p.vertices) - 2 for p in m.data.polygons), sc)
        out['SK_AR15_MLOK'] = dict(ok=not errs, errs=errs, notes=[notes])
        L.log('VERIFY %-30s %s  %s' % ('SK_AR15_MLOK', 'OK  ' if not errs else 'FAIL', notes))
        for e in errs: L.log('       ! %s' % e)
    all_ok &= not errs
    out['ALL_OK'] = all_ok
    json.dump(out, open(os.path.join(L.OUT, 'verify_report.json'), 'w'), indent=1)
    L.log('VERIFY %s' % ('ALL OK' if all_ok else 'FAILURES - see verify_report.json'))
    return out
