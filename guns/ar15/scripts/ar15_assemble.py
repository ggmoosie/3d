"""ar15_assemble.py - milestone 7: UV atlases (uniform texel density), assembled game meshes SM_AR15_MLOK / SM_AR15_M4Quad,
UCX_ hulls, socket JSON, LODs, the rigid skeletal variant SK_AR15_MLOK + rig JSON, per-part / assembled / LOD / skeletal FBX,
the master .blend, then a re-import verify pass of every FBX.  Called from build_ar15.py --assemble."""
import bpy, bmesh, os, json, math, time
import numpy as np
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree
import ar15_lib as L
import ar15_spec as SP
import ar15_sockets as SK

GUNS = {'MLOK': 'SM_AR15_MLOK', 'QUAD': 'SM_AR15_M4Quad'}
OUTP = os.path.join(L.OUT, 'parts')
REPORT = {}

def log(*a): L.log(*a)

def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)

def coords(o):
    co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); return co.reshape(-1, 3)

def poly_areas(me):
    a = np.empty(len(me.polygons)); me.polygons.foreach_get('area', a); return a

# ================================================================================================ UVs
def _dirs26():
    d = []
    for x in (-1, 0, 1):
        for y in (-1, 0, 1):
            for z in (-1, 0, 1):
                if (x, y, z) != (0, 0, 0): d.append(np.array((x, y, z), float) / math.sqrt(x * x + y * y + z * z))
    return np.array(d)
DIRS26 = _dirs26()

INTERIOR_SCALE = 0.4        # pass 3: UV scale of enclosed islands (bores, magwell / FCG pocket walls, handguard liner)
INTERIOR_ENCLOSED = 0.8     # an island is interior when >= 80 % of hemisphere rays from its faces hit the part within 8 cm

def _hemi(n=12):
    """n unit directions spread over the +Z hemisphere (Fibonacci)"""
    out = []
    for k in range(n):
        z = 1.0 - (k + 0.5) / n; r = math.sqrt(max(0.0, 1.0 - z * z)); a = k * 2.399963
        out.append((r * math.cos(a), r * math.sin(a), z))
    return np.array(out)
HEMI = _hemi(12)

def enclosure(bvh, centre, normal):
    """share of hemisphere rays around `normal` that hit the part within 8 cm"""
    n = V(normal).normalized(); t = n.orthogonal().normalized(); b = n.cross(t)
    o = V(centre) + n * 2e-5; hits = 0
    for (x, y, z) in HEMI:
        d = t * x + b * y + n * z
        if bvh.ray_cast(o, d, 0.08)[0] is not None: hits += 1
    return hits / len(HEMI)

def unwrap_part(o, chunk_mm=70.0, hard_deg=35.0):
    """chunked box projection (our own unwrapper, replaces smart_project which made 38 cm strips that capped the density):
    every face picks the closest of 26 projection directions; islands are connected faces that share the direction and the
    70 mm chunk along the gun axis and are not separated by a hard edge (custom-normal split), so hard edges always sit on
    UV seams.  Each island is projected flat in millimetres (1:1 scale, so no averaging is needed), u along the gun axis."""
    me = o.data; me.calc_normals_split()
    nP = len(me.polygons)
    fn = np.empty(nP * 3); me.polygons.foreach_get('normal', fn); fn = fn.reshape(-1, 3)
    fc = np.empty(nP * 3); me.polygons.foreach_get('center', fc); fc = fc.reshape(-1, 3)
    cls = np.argmax(fn @ DIRS26.T, axis=1)
    chunk = np.floor((-fc[:, 1] * 1000.0) / chunk_mm).astype(int)          # Blender -Y = UE +Y (gun axis), mm
    ln = np.empty(len(me.loops) * 3); me.loops.foreach_get('normal', ln); ln = ln.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    ls = np.empty(nP, np.int64); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(nP, np.int64); me.polygons.foreach_get('loop_total', lt)
    # edge -> faces, with the loop normals of both faces at the edge's vertices
    from collections import defaultdict
    ef = defaultdict(list)
    for f in range(nP):
        s, t = ls[f], lt[f]
        for k in range(t):
            a, b = lv[s + k], lv[s + (k + 1) % t]
            ef[(a, b) if a < b else (b, a)].append((f, s + k, s + (k + 1) % t))
    parent = np.arange(nP)
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    cos_h = math.cos(math.radians(hard_deg))
    for e, lst in ef.items():
        if len(lst) != 2: continue
        (f0, a0, b0), (f1, a1, b1) = lst
        if cls[f0] != cls[f1] or chunk[f0] != chunk[f1]: continue
        # hard edge = the faces' loop normals disagree at the shared vertices (custom normals split)
        va = {lv[a0]: a0, lv[b0]: b0}; vb = {lv[a1]: a1, lv[b1]: b1}
        if any(np.dot(ln[va[v]], ln[vb[v]]) < 0.999 for v in va): continue
        if np.dot(fn[f0], fn[f1]) < cos_h: continue
        r0, r1 = find(f0), find(f1)
        if r0 != r1: parent[r1] = r0
    roots = np.array([find(i) for i in range(nP)])
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3) * 1000.0
    uv = np.zeros((len(me.loops), 2))
    gun_axis = np.array((0.0, -1.0, 0.0))
    # enclosed islands (pass 3): sampled hemisphere rays against the part itself; those islands get INTERIOR_SCALE so
    # the visible surfaces keep the texel density
    bvh = BVHTree.FromPolygons([V(p) for p in co / 1000.0], [list(p.vertices) for p in me.polygons])
    area = poly_areas(me); interior = np.zeros(nP, np.int32); rng = np.random.default_rng(3)
    for r in np.unique(roots):
        faces = np.where(roots == r)[0]
        pick = faces if len(faces) <= 8 else rng.choice(faces, 8, replace=False, p=area[faces] / area[faces].sum())
        e = np.average([enclosure(bvh, fc[f], fn[f]) for f in pick], weights=area[pick] + 1e-12)
        if e >= INTERIOR_ENCLOSED: interior[faces] = 1
    if '_int' in me.attributes: me.attributes.remove(me.attributes['_int'])
    me.attributes.new('_int', 'INT', 'FACE').data.foreach_set('value', interior.tolist())
    for r in np.unique(roots):
        faces = np.where(roots == r)[0]
        d = DIRS26[cls[faces[0]]]
        u = gun_axis - d * np.dot(gun_axis, d)
        if np.linalg.norm(u) < 1e-3: u = np.array((1.0, 0.0, 0.0)) - d * d[0]
        u /= np.linalg.norm(u); v = np.cross(d, u)
        loops = np.concatenate([np.arange(ls[f], ls[f] + lt[f]) for f in faces])
        p = co[lv[loops]]
        k = INTERIOR_SCALE if interior[faces[0]] else 1.0
        uv[loops, 0] = (p @ u) * k; uv[loops, 1] = (p @ v) * k
    if not me.uv_layers: me.uv_layers.new(name='UVMap')
    me.uv_layers.active.data.foreach_set('uv', (uv * 0.001).ravel())       # metres; packing rescales anyway
    return len(np.unique(roots))

def uv_array(me):
    uv = np.empty(len(me.loops) * 2); me.uv_layers.active.data.foreach_get('uv', uv); return uv.reshape(-1, 2)

def tri_uv_area(me, uv, polys=None):
    """sum of UV areas of the given polygons (all if None); meshes are triangulated"""
    ls = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', ls)
    idx = ls if polys is None else ls[polys]
    a, b, c = uv[idx], uv[idx + 1], uv[idx + 2]
    return 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))

def build_atlas_object(members, slot):
    """temporary object holding only `slot` faces of the member parts, tagged with (part, face) for the way back"""
    copies = []
    for pi, o in enumerate(members):
        me = o.data.copy(); me.name = '_uv_%s' % o.name
        nf = len(me.polygons)
        me.attributes.new('_pidx', 'INT', 'FACE').data.foreach_set('value', [pi] * nf)
        me.attributes.new('_fidx', 'INT', 'FACE').data.foreach_set('value', list(range(nf)))
        mi = [i for i, m in enumerate(me.materials) if m and m.name == slot]
        bm = bmesh.new(); bm.from_mesh(me)
        kill = [f for f in bm.faces if f.material_index not in mi]
        if kill: bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(me); bm.free()
        if len(me.polygons) == 0: bpy.data.meshes.remove(me); continue
        t = bpy.data.objects.new('_uvtmp', me); bpy.context.scene.collection.objects.link(t); copies.append(t)
    if not copies: return None
    select_only(copies, copies[0])
    if len(copies) > 1:
        with bpy.context.temp_override(active_object=copies[0], selected_editable_objects=copies, object=copies[0]):
            bpy.ops.object.join()
    return copies[0]

def pack_atlas(J):
    select_only([J], J)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='FRACTION', margin=0.0012, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')

def overlap_pct(uv_tris, res=1024):
    """rasterise UV triangles (shrunk 0.35 px toward their centroid so shared edges never double count) -> % overlap"""
    cnt = np.zeros((res, res), np.uint16)
    T = uv_tris * res
    for tri in T:
        c = tri.mean(0); tri = c + (tri - c) * np.maximum(0.0, 1.0 - 0.35 / max(1e-6, np.linalg.norm(tri - c, axis=1).max()))
        x0, y0 = np.floor(tri.min(0)).astype(int); x1, y1 = np.ceil(tri.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, res), min(y1, res)
        if x1 <= x0 or y1 <= y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = tri
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12: continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        cnt[y0:y1, x0:x1] += inside.astype(np.uint16)
    cov = (cnt >= 1).sum(); ov = (cnt >= 2).sum()
    return 100.0 * ov / max(1, cov), 100.0 * cov / (res * res)

HERO_SLOTS = ('Receiver', 'Handguard')     # 4096 maps (pass 2): the surfaces the first-person camera sees most
HERO_SIZE = 4096

OWN_ATLAS = {'SM_AR15_Mag30': 'Mag30', 'SM_AR15_MagRound': 'MagRound'}

def atlases():
    """atlas groups: kit-wide Receiver / Steel / BCG / Polymer (every 'kit' part of both guns and of the game parts, e.g.
    the 16 in barrel and the front sight: one skin fits all), one Handguard atlas per handguard, and the accessories' own
    (magazine: Mag30_*, cartridge: MagRound_Brass)"""
    kit = [P for P in L.PARTS.values() if P.atlas == 'kit']
    own = [P for P in L.PARTS.values() if P.atlas == 'own']
    out = []
    for slot in ('Receiver', 'Steel', 'BCG', 'Polymer'):
        out.append(dict(name='Kit_%s' % slot, slot=slot, parts=[P for P in kit if slot in P.info['slots']], size=2048, own=False))
    for hn in ('SM_AR15_HandguardMLOK', 'SM_AR15_HandguardQuad'):
        P = L.PARTS[hn]; out.append(dict(name='%s_Handguard' % ('MLOK' if 'MLOK' in hn else 'M4Quad'), slot='Handguard', parts=[P], size=2048,
                                         own=False))
    for P in own:
        for slot in P.info['slots']:
            out.append(dict(name='%s_%s' % (OWN_ATLAS.get(P.name, P.name.replace('SM_AR15_', '')), slot), slot=slot, parts=[P], size=1024,
                            own=True))
    return [a for a in out if a['parts']]

def atlas_of(part_name, slot):
    """the atlas name that holds `part_name`'s faces of `slot`"""
    P = L.PARTS[part_name]
    if P.atlas == 'own': return '%s_%s' % (OWN_ATLAS.get(P.name, P.name.replace('SM_AR15_', '')), slot)
    if slot == 'Handguard': return 'MLOK_Handguard' if 'MLOK' in part_name else 'M4Quad_Handguard'
    return 'Kit_%s' % slot

def build_uvs():
    t0 = time.time()
    for P in L.PARTS.values(): unwrap_part(P.obj)
    A = atlases(); res = {}
    for a in A:
        objs = [P.obj for P in a['parts']]
        J = build_atlas_object(objs, a['slot'])
        pack_atlas(J)
        me = J.data; uv = uv_array(me)
        pidx = np.empty(len(me.polygons), np.int64); me.attributes['_pidx'].data.foreach_get('value', pidx)
        fidx = np.empty(len(me.polygons), np.int64); me.attributes['_fidx'].data.foreach_get('value', fidx)
        ext = np.ones(len(me.polygons), bool)
        if '_int' in me.attributes:
            iv = np.empty(len(me.polygons), np.int64); me.attributes['_int'].data.foreach_get('value', iv); ext = iv == 0
        area3 = poly_areas(me)[ext].sum() * 1e4                              # cm^2, visible faces
        uva = tri_uv_area(me, uv, np.where(ext)[0]).sum()
        a.update(J=J, uv=uv, pidx=pidx, fidx=fidx, area_cm2=area3, uv_area=uva,
                 D2048=2048.0 * math.sqrt(uva / max(1e-9, area3)))
        log('  packed %-22s %5d faces  D@2048 %.2f px/cm' % (a['name'], len(me.polygons), a['D2048']))
    # two texel-density tiers (pass 2): the hero slots the camera lives on (Receiver, Handguard) at 4096 / ~80 px/cm, the
    # rest at the pass-1 density (~40 px/cm).  In each tier the tightest atlas sets the density, the others shrink to match
    # and drop to a smaller texture when they fit.  The magazine keeps its own atlases at the standard density.
    gun = [a for a in A if not a['own']]
    hero = lambda a: a['slot'] in HERO_SLOTS and not a['own']
    D = min(a['D2048'] for a in gun)
    DH = min(a['D2048'] * HERO_SIZE / 2048.0 for a in gun if hero(a))
    for a in A:
        top = HERO_SIZE if hero(a) else 2048
        f = (DH if hero(a) else D) / (a['D2048'] * top / 2048.0); size = top
        # halve while the texture is at most half used; the magazine (a loose accessory) may drop one size for up to
        # 10 % less density rather than sit in a 2048 map at 15 % coverage
        lim = 0.56 if a['own'] else 0.5
        while f <= lim and size > 512: size //= 2; f *= 2.0
        if a['own']:
            while f > lim * 2.0 + 1e-9: size *= 2; f /= 2.0
        a['size'] = size; a['scale'] = min(1.0, f)
        a['D'] = size * math.sqrt(a['uv_area'] * a['scale'] ** 2 / max(1e-9, a['area_cm2']))
        uvs = a['uv'] * a['scale']
        # write back to the parts
        me = a['J'].data; ls = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', ls)
        lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt)
        objs = [P.obj for P in a['parts']]
        for pi, o in enumerate(objs):
            ouv = uv_array(o.data); ols = np.empty(len(o.data.polygons), np.int64); o.data.polygons.foreach_get('loop_start', ols)
            sel = np.where(a['pidx'] == pi)[0]
            for j in sel:
                src = ls[j]; dst = ols[a['fidx'][j]]
                ouv[dst:dst + lt[j]] = uvs[src:src + lt[j]]
            o.data.uv_layers.active.data.foreach_set('uv', ouv.ravel())
        ov, cov = overlap_pct(uvs[ls.reshape(-1, 1) + np.arange(3)].reshape(-1, 3, 2))
        a['overlap_pct'] = ov; a['coverage_pct'] = cov
        inside = bool((uvs >= -1e-6).all() and (uvs <= 1 + 1e-6).all()); a['inside01'] = inside
        res[a['name']] = dict(slot=a['slot'], parts=[P.name for P in a['parts']], texture=a['size'], texel_px_per_cm=round(a['D'], 2),
                              area_cm2=round(a['area_cm2'], 1), uv_coverage_pct=round(cov, 1), overlap_pct=round(ov, 3), inside_0_1=inside)
        L.kill(a['J'])
        log('ATLAS %-22s %-9s %4d px  %6.2f px/cm  area %7.1f cm2  coverage %5.1f %%  overlap %.3f %%  in0-1 %s' %
            (a['name'], a['slot'], a['size'], a['D'], a['area_cm2'], cov, ov, inside))
    REPORT['atlases'] = res; REPORT['texel_px_per_cm'] = round(D, 2); REPORT['texel_px_per_cm_hero'] = round(DH, 2)
    # hard edges on UV seams
    REPORT['hard_edges_on_seams'] = {P.name: hard_edge_seam_pct(P.obj) for P in L.PARTS.values()}
    log('UVs done in %.1fs, texel density %.2f px/cm (hero slots %s: %.2f px/cm at %d)' % (time.time() - t0, D, '/'.join(HERO_SLOTS), DH, HERO_SIZE))
    return A

def hard_edge_seam_pct(o):
    """share of hard edges (custom normals split across the edge) that are also UV seams"""
    me = o.data; me.calc_normals_split()
    ln = np.empty(len(me.loops) * 3); me.loops.foreach_get('normal', ln); ln = ln.reshape(-1, 3)
    uv = uv_array(me); lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    corner = {}
    for p in me.polygons:
        for li in p.loop_indices:
            corner.setdefault(lv[li], []).append((p.index, li))
    hard = seam = 0
    ek = me.edge_keys
    face_loops = {}
    for p in me.polygons:
        for li in p.loop_indices: face_loops[(p.index, lv[li])] = li
    from collections import defaultdict
    edge_faces = defaultdict(list)
    for p in me.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)): edge_faces[tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))].append(p.index)
    for e, fs in edge_faces.items():
        if len(fs) != 2: continue
        f0, f1 = fs; is_hard = False; is_seam = False
        for v in e:
            l0, l1 = face_loops[(f0, v)], face_loops[(f1, v)]
            if np.dot(ln[l0], ln[l1]) < 0.999: is_hard = True
            if np.abs(uv[l0] - uv[l1]).max() > 1e-5: is_seam = True
        if is_hard:
            hard += 1; seam += is_seam
    return round(100.0 * seam / max(1, hard), 1)

# ================================================================================================ assembled meshes
def join_copies(objs, name, collection=None):
    cs = []
    for o in objs:
        c = o.copy(); c.data = o.data.copy(); (collection or bpy.context.scene.collection).objects.link(c); cs.append(c)
    select_only(cs, cs[0])
    if len(cs) > 1:
        with bpy.context.temp_override(active_object=cs[0], selected_editable_objects=cs, object=cs[0]):
            bpy.ops.object.join()
    j = cs[0]; j.name = name; j.data.name = name
    reorder_slots(j)
    return j

def reorder_slots(o):
    """material slots in the contract order (Receiver, Steel, BCG, Polymer, Handguard), unused slots dropped"""
    me = o.data; names = [m.name if m else None for m in me.materials]
    mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    used = sorted(set(names[i] for i in set(mi.tolist())), key=lambda n: SP.ALL_SLOTS.index(n))
    remap = np.array([used.index(names[i]) if names[i] in used else 0 for i in range(len(names))])
    me.materials.clear()
    for n in used: me.materials.append(L.slot_mat(n))
    me.polygons.foreach_set('material_index', remap[mi])

def hulls_for(config, gun_obj):
    """UCX_ convex hulls: receiver block, handguard, barrel + muzzle, stock + buffer tube, pistol grip"""
    groups = [
        ('receiver', ['SM_AR15_LowerReceiver', 'SM_AR15_UpperReceiver', 'SM_AR15_ChargingHandle', 'SM_AR15_BUIS']),
        ('handguard', ['SM_AR15_HandguardMLOK'] if config == 'MLOK' else ['SM_AR15_HandguardQuad', 'SM_AR15_DeltaRing', 'SM_AR15_FrontSightBase']),
        ('barrel', ['SM_AR15_Birdcage']),
        ('stock', ['SM_AR15_Stock', 'SM_AR15_BufferTube', 'SM_AR15_CastleNut']),
        ('grip', ['SM_AR15_Grip']),
    ]
    hulls = []
    for i, (lab, names) in enumerate(groups):
        pts = np.concatenate([coords(L.PARTS[n].obj) for n in names if n in L.PARTS and config in L.PARTS[n].configs])
        if lab == 'barrel':      # birdcage + the exposed barrel in front of the handguard / FSB
            b = coords(L.PARTS['SM_AR15_Barrel'].obj); yb = -b[:, 1] * 1000 - SP.G2F[1]
            front = SP.MLOK_REAR + SP.MLOK_LEN - 10 if config == 'MLOK' else SP.FSB[1] - 5
            pts = np.concatenate([pts, b[yb > front]])
        if lab == 'receiver':    # leave the BUIS leaf top out of the block (keeps the hull low)
            pts = pts[pts[:, 2] < (SP.RAIL_TOP + 8.0 + SP.G2F[2]) * L.MM]
        hb = None
        for nd in (56, 40, 26):                      # fewer support directions if the hull will not come out convex
            if hb is not None: hb.free()
            hb = L.hull_bm(L.support_pts([V(p) for p in pts], nd))
            if L._bm_convexity(hb) < 1e-6: break
        log('HULL %s %-9s %3d verts  convexity %.2e m' % (gun_obj.name, lab, len(hb.verts), L._bm_convexity(hb)))
        hn = 'UCX_%s_%02d' % (gun_obj.name, i)
        ho = L.bm_obj(hb, hn); ho.parent = gun_obj; ho.hide_render = True; ho['hull'] = lab
        hulls.append(ho)
    return hulls

def build_guns():
    guns = {}
    col = L.coll('AR15_Assembled')
    for cfg, name in GUNS.items():
        objs = [P.obj for P in L.PARTS.values() if cfg in P.configs and P.static]
        g = join_copies(objs, name, col)
        hulls = hulls_for(cfg, g)
        for h in hulls:
            bpy.context.scene.collection.objects.unlink(h); col.objects.link(h)
        nm, inv, degen, shells = L.topo_check(g.data)
        guns[cfg] = dict(obj=g, hulls=hulls, tris=L.tri_count(g.data), shells=shells, nm=nm, inv=inv, degen=degen,
                         slots=[m.name for m in g.data.materials])
        log('GUN %-16s tris %6d  shells %4d  nm %d inv %d degen %d  slots %s  hulls %d' % (name, guns[cfg]['tris'], shells, nm, inv, degen,
                                                                                    ','.join(guns[cfg]['slots']), len(hulls)))
    return guns

# ================================================================================================ sockets
def write_sockets(guns):
    SK.selftest()
    out = {}
    for cfg, name in GUNS.items():
        socks = SK.layout(cfg, L.PARTS)
        J = dict(mesh=name, units='cm', frame='UE: +X = gun left, +Y = muzzle, +Z = up; origin per INTEGRATION.md (bore at z 12.14)',
                 rotator='FRotator (pitch, yaw, roll) degrees; x/y/z_axis = the resulting socket axes in mesh space',
                 import_hint='unreal.StaticMeshSocket: relative_location = loc, relative_rotation = Rotator(pitch=, yaw=, roll=), tag = tag',
                 sockets=[{k: v for k, v in s.items() if k not in ('check', 'part')} for s in socks])
        p = os.path.join(L.OUT, 'sockets_%s.json' % name); json.dump(J, open(p, 'w'), indent=1)
        guns[cfg]['sockets'] = socks; out[name] = p
        log('SOCKETS %s: %d (written %s)' % (name, len(socks), os.path.basename(p)))
    return out

# ================================================================================================ LODs
def make_lod(gun, ratio, label):
    o = gun['obj']; c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c); c.name = '%s_%s' % (o.name, label)
    m = c.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = ratio; m.use_collapse_triangulate = True
    L.apply_mods(c)
    try:
        select_only([c], c); bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except RuntimeError: pass
    c.data.use_auto_smooth = True; c.data.auto_smooth_angle = math.radians(35)
    w = c.modifiers.new('wn', 'WEIGHTED_NORMAL'); w.mode = 'FACE_AREA'; w.keep_sharp = True; L.apply_mods(c)
    me = c.data
    # sanity: triangle ratio, bounds, slots, deviation from LOD0, UVs in 0-1
    t0, t1 = gun['tris'], L.tri_count(me)
    a, b = coords(o), coords(c)
    dev_b = float(np.abs(np.r_[a.min(0) - b.min(0), a.max(0) - b.max(0)]).max()) * 1000
    bvh = BVHTree.FromPolygons([V(p) for p in b], [list(p.vertices) for p in me.polygons])
    samp = a[np.random.default_rng(7).choice(len(a), min(4000, len(a)), replace=False)]
    d = np.array([(bvh.find_nearest(V(p))[0] - V(p)).length if bvh.find_nearest(V(p))[0] else 0 for p in samp]) * 1000
    uv = uv_array(me); in01 = bool((uv >= -1e-4).all() and (uv <= 1 + 1e-4).all())
    errs = []
    if not (0.85 * ratio <= t1 / t0 <= 1.15 * ratio): errs.append('ratio %.3f' % (t1 / t0))
    if dev_b > 1.0: errs.append('bounds moved %.2f mm' % dev_b)
    if [m.name for m in me.materials] != gun['slots']: errs.append('slots')
    lim = 2.5 if ratio >= 0.5 else 6.0
    if np.percentile(d, 99) > lim: errs.append('p99 deviation %.2f mm > %.1f' % (np.percentile(d, 99), lim))
    if not in01: errs.append('uv outside 0-1')
    info = dict(tris=t1, ratio=round(t1 / t0, 3), bounds_dev_mm=round(dev_b, 3), dev_mean_mm=round(float(d.mean()), 3),
                dev_p99_mm=round(float(np.percentile(d, 99)), 3), dev_max_mm=round(float(d.max()), 3), errs=errs)
    log('LOD %-22s tris %6d (%.2f)  dev mean %.2f p99 %.2f max %.2f mm  %s' % (c.name, t1, t1 / t0, d.mean(), np.percentile(d, 99), d.max(),
                                                                          'OK' if not errs else 'FAIL ' + '; '.join(errs)))
    return c, info

# ================================================================================================ skeletal variant
BONES = ['root', 'bcg', 'bolt', 'charging_handle', 'trigger', 'hammer', 'selector', 'mag_catch', 'bolt_catch', 'dust_cover',
         'forward_assist', 'stock', 'buis', 'magazine']
POSES = {
    'rest': {},
    'safety_safe': {'selector': 0.0}, 'safety_semi': {'selector': 90.0}, 'safety_auto': {'selector': 180.0},
    'trigger_pull': {'selector': 90.0, 'trigger': -9.0},             # pass 4b: SAFE blocks the trigger tail, so pulls are on SEMI
    'fire_hammer_fall': {'selector': 90.0, 'trigger': -9.0, 'hammer': -74.0},
    'fire_bolt_back': {'selector': 90.0, 'trigger': -9.0, 'hammer': 0.0, 'bcg': 82.0, 'bolt': 22.5, 'dust_cover': -112.0},
    'charge_pulled': {'charging_handle': 80.0, 'bcg': 80.0, 'bolt': 22.5, 'dust_cover': -112.0},
    'bolt_locked_back': {'bcg': 76.0, 'bolt': 22.5, 'bolt_catch': 9.0, 'dust_cover': -112.0},
    'mag_release': {'mag_catch': 3.2},
    'mag_out': {'mag_catch': 3.2, 'magazine': 200.0},
    'stock_collapsed': {'stock': -48.9}, 'stock_extended': {'stock': 32.6},
    'forward_assist_press': {'forward_assist': 6.0},
    'buis_folded': {'buis': 90.0},                                   # pass 4: the MBUS-style rear leaf folds rearward
}

def build_skeletal():
    """SK_AR15_MLOK: the MLOK build with every moving part (hammer and bolt included, no magazine geometry), rigidly skinned:
    one bone per moving part, heads at the hinge / travel origin.  Built in centimetres (1 BU = 1 cm) for a clean UE skeleton."""
    col = L.coll('AR15_Skeletal')
    parts = [P for P in L.PARTS.values() if 'MLOK' in P.configs]
    cs = []
    for P in parts:                                   # rigid skin: every vertex of a part -> its bone, weight 1
        c = P.obj.copy(); c.data = P.obj.data.copy(); col.objects.link(c)
        g = c.vertex_groups.new(name=P.bone if P.bone in BONES else 'root'); g.add(list(range(len(c.data.vertices))), 1.0, 'REPLACE')
        cs.append(c)
    select_only(cs, cs[0])
    with bpy.context.temp_override(active_object=cs[0], selected_editable_objects=cs, object=cs[0]):
        bpy.ops.object.join()
    mesh = cs[0]; mesh.name = 'SK_AR15_MLOK'; mesh.data.name = 'SK_AR15_MLOK'; reorder_slots(mesh)
    for b in BONES:
        if b not in mesh.vertex_groups: mesh.vertex_groups.new(name=b)
    # armature (Blender scene metres here; scaled to cm at export)
    arm = bpy.data.armatures.new('SK_AR15_Skeleton'); ao = bpy.data.objects.new('Armature', arm); col.objects.link(ao)
    select_only([ao], ao); bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones; rig = {}
    root = eb.new('root'); root.head = (0, 0, 0); root.tail = (0, -0.05, 0)
    by_bone = {P.bone: P for P in L.PARTS.values() if P.bone != 'root'}
    for b in BONES[1:]:
        P = by_bone.get(b)
        if P is None: continue
        head = L.g2b(P.pivot); mo = P.motion or {}
        ax_ue = V(mo.get('axis', (0, 1, 0))); ax_b = V((ax_ue.x, -ax_ue.y, ax_ue.z)).normalized()
        e = eb.new(b); e.head = head; e.tail = head + ax_b * 0.02
        e.parent = eb[mo.get('parent', 'root')] if mo.get('parent', 'root') in eb else root
        rig[b] = dict(part=P.name, head_cm=L.b2f_cm(head), type=mo.get('type'), axis_ue=list(ax_ue), limits=list(mo.get('limits', (0, 0))),
                      units='deg' if mo.get('type') == 'rotate' else 'mm', rest=mo.get('rest', 0.0), stops=mo.get('stops', {}),
                      parent=mo.get('parent', 'root'), note=mo.get('note', ''))
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh.parent = ao; mod = mesh.modifiers.new('Armature', 'ARMATURE'); mod.object = ao
    J = dict(skeletal_mesh='SK_AR15_MLOK', units='head_cm in UE cm; limits in deg (rotate) or mm (translate)',
             convention='axis_ue = motion axis in mesh space (UE axes); positive value = rotation by the right-hand rule about axis_ue in '
                        'UE numbers / translation along axis_ue.  Bone local +Y (Blender) points along axis_ue; bone heads sit on the hinge / '
                        'travel origin.  The magazine bone holds no geometry: attach SM_AR15_Mag30 / SM_M4_Mag to it (it sits on MagazineSocket).',
             bones={'root': dict(head_cm=[0, 0, 0], type=None, note='gun origin (INTEGRATION frame)'), **rig}, poses=POSES)
    p = os.path.join(L.OUT, 'rig_SK_AR15.json'); json.dump(J, open(p, 'w'), indent=1)
    log('SKELETAL SK_AR15_MLOK: %d bones, %d tris, rig -> %s' % (len(arm.bones), L.tri_count(mesh.data), os.path.basename(p)))
    return mesh, ao, J

# ================================================================================================ export
def export_fbx(objs, path, armature=False):
    select_only(objs, objs[0])
    kw = dict(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y',
              axis_up='Z', mesh_smooth_type='FACE', use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False, path_mode='STRIP',
              use_custom_props=False)
    kw['object_types'] = {'MESH', 'ARMATURE'} if armature else {'MESH'}
    if armature:
        kw.update(primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL', use_armature_deform_only=False)
    bpy.ops.export_scene.fbx(**kw)

def export_part(P):
    """per-part FBX in the gun frame; moving parts are re-centred on their pivot (place them at the pivot to assemble)"""
    o = P.obj; c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c)
    o.name = P.name + '__keep'; c.name = P.name          # the FBX object must carry the exact part name
    if P.pivot is not None and P.bone != 'root':
        off = L.g2b(P.pivot); c.data.transform(Matrix.Translation(-off))
    path = os.path.join(OUTP, P.name + '.fbx'); export_fbx([c], path)
    info = dict(fbx=path, tris=L.tri_count(c.data), slots=[m.name for m in c.data.materials], pivot_cm=L.b2f_cm(L.g2b(P.pivot)) if P.pivot else [0, 0, 0],
                recentred=bool(P.pivot is not None and P.bone != 'root'), lo=coords(c).min(0).tolist(), hi=coords(c).max(0).tolist())
    L.kill(c); o.name = P.name
    return info

def export_all(guns, lods, sk):
    exp = {'parts': {}, 'guns': {}, 'lods': {}, 'skeletal': None}
    for P in L.PARTS.values():
        if P.info['errs'] and any('non-manifold' in e or 'inside-out' in e or 'degenerate' in e for e in P.info['errs']):
            log('NOT EXPORTED (topology):', P.name); continue
        exp['parts'][P.name] = export_part(P)
    for cfg, g in guns.items():
        path = os.path.join(L.OUT, g['obj'].name + '.fbx'); export_fbx([g['obj']] + g['hulls'], path)
        exp['guns'][g['obj'].name] = dict(fbx=path, tris=g['tris'], slots=g['slots'], hulls=[h.name for h in g['hulls']],
                                          lo=coords(g['obj']).min(0).tolist(), hi=coords(g['obj']).max(0).tolist())
    for name, (o, info) in lods.items():
        path = os.path.join(L.OUT, 'lod', o.name + '.fbx'); export_fbx([o], path); exp['lods'][o.name] = dict(fbx=path, **info)
    mesh, arm, J = sk
    # centimetre scene for a clean skeleton: scale the data x100 and set the unit scale to 0.01 during the export
    sc = bpy.context.scene; old = sc.unit_settings.scale_length
    m2 = mesh.copy(); m2.data = mesh.data.copy(); a2 = arm.copy(); a2.data = arm.data.copy()
    for o in (m2, a2): bpy.context.scene.collection.objects.link(o)
    m2.parent = a2; m2.modifiers['Armature'].object = a2
    m2.data.transform(Matrix.Scale(100.0, 4))
    select_only([a2], a2); bpy.ops.object.mode_set(mode='EDIT')
    for e in a2.data.edit_bones: e.head *= 100.0; e.tail *= 100.0
    bpy.ops.object.mode_set(mode='OBJECT')
    arm_name, mesh_name = arm.name, mesh.name
    arm.name = '_SK_arm_keep'; mesh.name = '_SK_mesh_keep'; a2.name = 'Armature'; m2.name = 'SK_AR15_MLOK'
    sc.unit_settings.scale_length = 0.01
    path = os.path.join(L.OUT, 'SK_AR15_MLOK.fbx'); export_fbx([a2, m2], path, armature=True)
    sc.unit_settings.scale_length = old
    exp['skeletal'] = dict(fbx=path, tris=L.tri_count(m2.data), bones=[b.name for b in a2.data.bones], lo=coords(m2).min(0).tolist(),
                           hi=coords(m2).max(0).tolist())
    L.kill(m2); bpy.data.objects.remove(a2, do_unlink=True); arm.name = arm_name; mesh.name = mesh_name
    json.dump(exp, open(os.path.join(L.OUT, '_export_manifest.json'), 'w'), indent=1)
    return exp

# ================================================================================================ run
def run(bake=True):
    t0 = time.time()
    build_uvs()
    guns = build_guns()
    write_sockets(guns)
    lods = {}
    for cfg, g in guns.items():
        for ratio, lab in ((0.5, 'LOD1'), (0.2, 'LOD2')):
            o, info = make_lod(g, ratio, lab); o.hide_render = True; lods[o.name] = (o, info)
    sk = build_skeletal()
    if bake:
        import ar15_bake as B; REPORT['bakes'] = B.run(guns)
    exp = export_all(guns, lods, sk)
    REPORT['guns'] = {g['obj'].name: dict(tris=g['tris'], shells=g['shells'], slots=g['slots'], hulls=[h.name for h in g['hulls']],
                                          lod1=lods[g['obj'].name + '_LOD1'][1], lod2=lods[g['obj'].name + '_LOD2'][1]) for g in guns.values()}
    REPORT['parts'] = {n: dict(tris=P.info['tris'], slots=P.info['slots'], configs=sorted(P.configs), bone=P.bone, static=P.static,
                               errs=P.info['errs']) for n, P in L.PARTS.items()}
    json.dump(REPORT, open(os.path.join(L.OUT, 'assembly_report.json'), 'w'), indent=1, default=str)
    log('ASSEMBLY done in %.1fs' % (time.time() - t0))
    return guns, lods, sk, exp
