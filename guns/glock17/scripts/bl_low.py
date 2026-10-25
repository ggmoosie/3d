"""bl_low.py - G17 v4 game meshes from the SDF high-poly (Blender 4.0, headless).
  per shell: copy -> quadric collapse to its triangle budget -> weld / dissolve degenerate -> triangulate
  per assembly (the five contract names): join -> weighted normals (face area) -> smart UVs packed in 0-1 ->
  M_G17_<Part> slot; LOD1 (45 %) and LOD2 (18 %) copies; UCX_SM_G17_Frame_NN convex hulls.
The high-poly shells stay in the file (collection HIGH, hidden from the game export) as the bake source.
usage: blender -b work/G17_V4_HighProd.blend --python bl_low.py -- [out.blend]"""
import bpy, bmesh, sys, os, math, json, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else os.path.join(HERE, 'work', 'G17_V4_Low.blend')
ASM = {'Frame': ['frame', 'trigger', 'pin0', 'pin1', 'slidestop', 'takedown', 'magcatchL', 'magcatchR', 'lockblock', 'housing'],
       'Slide': ['slide', 'rsight', 'fsight', 'extractor', 'plate'], 'Barrel': ['barrel', 'guiderod'],
       'Backstrap': ['backstrap'], 'Magazine': ['magbody', 'follower', 'baseplate']}
BUDGET = {'frame': 24200, 'trigger': 1100, 'pin0': 140, 'pin1': 140, 'slidestop': 800, 'takedown': 560, 'magcatchL': 640,
          'magcatchR': 260, 'lockblock': 600, 'housing': 640,
          'slide': 15600, 'rsight': 520, 'fsight': 220, 'extractor': 220, 'plate': 200,
          'barrel': 3900, 'guiderod': 2800, 'backstrap': 2950, 'magbody': 3900, 'follower': 760, 'baseplate': 1350}
SYM = {}          # symmetric collapse stalls far above the target on the barrel / baseplate: off
sc = bpy.context.scene
def log(*a): print('[low]', *a, flush=True)
def tris(o): return sum(len(p.vertices) - 2 for p in o.data.polygons)
hcol = bpy.data.collections.get('HIGH') or bpy.data.collections.new('HIGH')
if hcol.name not in sc.collection.children: sc.collection.children.link(hcol)
for c in list(sc.collection.children):
    if c.name.startswith('HI_'):
        for o in list(c.objects): hcol.objects.link(o); c.objects.unlink(o)
        sc.collection.children.unlink(c); bpy.data.collections.remove(c)
gcol = bpy.data.collections.get('GAME') or bpy.data.collections.new('GAME')
if gcol.name not in sc.collection.children: sc.collection.children.link(gcol)
lcol = bpy.data.collections.get('LODS') or bpy.data.collections.new('LODS')
if lcol.name not in sc.collection.children: sc.collection.children.link(lcol)

def decimate_copy(src, target, sym):
    me = src.data.copy(); o = bpy.data.objects.new('LO_' + src.name[3:], me); gcol.objects.link(o)
    n = tris(o); r = min(1.0, target / max(1, n))
    m = o.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = r; m.use_collapse_triangulate = True
    if sym: m.use_symmetry = True; m.symmetry_axis = 'X'
    with bpy.context.temp_override(object=o, active_object=o): bpy.ops.object.modifier_apply(modifier=m.name)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-6, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    loose = [v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(o.data); bm.free()
    o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return o

def _angles(f):
    vs = [v.co for v in f.verts]; out = []
    for i in range(3):
        u, w = vs[(i + 1) % 3] - vs[i], vs[(i + 2) % 3] - vs[i]
        out.append(u.angle(w) if u.length > 0 and w.length > 0 else 0.0)
    return out
def _is_sliver(f, deg=1.2, lmin=0.0018):
    if len(f.verts) != 3 or not f.is_valid: return False
    a = _angles(f); return min(a) < math.radians(deg) and max(e.calc_length() for e in f.edges) > lmin
def fix_slivers(o, max_iter=12, max_collapse=0.0006):
    """long sliver triangles (< 1.2 deg, longest edge > 1.8 mm) from the collapse decimation:
       caps (an angle near 180 deg) -> flip the longest edge;
       needles (two long edges)     -> collapse the short edge (<= 0.6 mm, link condition checked so the surface stays
                                       2-manifold); the normal map is baked afterwards, so the < 0.3 mm shift is invisible"""
    bm = bmesh.new(); bm.from_mesh(o.data); backup = o.data.copy()
    for it in range(max_iter):
        bm.faces.ensure_lookup_table(); flips, cols = set(), set()
        for f in bm.faces:
            if not _is_sliver(f): continue
            a = _angles(f)
            if max(a) > math.radians(150):
                e = max(f.edges, key=lambda e: e.calc_length())
                if len(e.link_faces) == 2: flips.add(e)
            else:
                e = min(f.edges, key=lambda e: e.calc_length())
                lim = max_collapse * (1.7 if max(x.calc_length() for x in f.edges) > 0.012 else 1.0)
                if e.calc_length() > lim or len(e.link_faces) != 2: continue
                v0, v1 = e.verts
                n0 = {x.other_vert(v0) for x in v0.link_edges}; n1 = {x.other_vert(v1) for x in v1.link_edges}
                if len(n0 & n1) != 2: continue                                   # link condition
                if any(x in cols for x in v0.link_edges) or any(x in cols for x in v1.link_edges): continue
                cols.add(e)
        if not flips and not cols: break
        for e in flips:                                       # one by one: a refused rotation does not block the rest
            if not e.is_valid or len(e.link_faces) != 2: continue
            a = [v for v in e.link_faces[0].verts if v not in e.verts]; b = [v for v in e.link_faces[1].verts if v not in e.verts]
            if len(a) != 1 or len(b) != 1 or any(x.other_vert(a[0]) is b[0] for x in a[0].link_edges): continue   # would duplicate an edge
            try: bmesh.utils.edge_rotate(e, False)
            except Exception: pass
        cols = [e for e in cols if e.is_valid]
        if cols: bmesh.ops.collapse(bm, edges=cols, uvs=False)
        bmesh.ops.dissolve_degenerate(bm, dist=2e-6, edges=bm.edges[:])
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    # beautify: flip only near-coplanar edges (< 2 deg crease), so the surface does not move
    flat = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) < math.radians(2.0)]
    if flat: bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=flat, use_restrict_tag=False, method='ANGLE')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    left = sum(1 for f in bm.faces if _is_sliver(f, 1.0, 0.002))
    bad = sum(1 for e in bm.edges if len(e.link_faces) != 2) + sum(1 for v in bm.verts if not v.is_manifold)
    if bad:                                              # safety net: never trade slivers for holes
        bm.free(); old = o.data; o.data = backup; bpy.data.meshes.remove(old)
        b2 = bmesh.new(); b2.from_mesh(o.data); left = sum(1 for f in b2.faces if _is_sliver(f, 1.0, 0.002)); b2.free()
        log('  sliver cleanup reverted on', o.name, '(%d non-manifold elements)' % bad); return left
    bm.to_mesh(o.data); bm.free(); bpy.data.meshes.remove(backup); return left

t0 = time.time(); report = {}
for asm, shells in ASM.items():
    objs = []
    for s in shells:
        src = bpy.data.objects.get('HI_' + s)
        if src is None: log('missing', s); continue
        t = time.time(); o = decimate_copy(src, BUDGET[s], SYM.get(s, False)); left = fix_slivers(o)
        log('%-10s %8d -> %6d tris  slivers left %d  %.1fs' % (s, tris(src), tris(o), left, time.time() - t)); objs.append(o)
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]):
        bpy.ops.object.join()
    o = objs[0]; name = 'SM_G17_' + asm; o.name = name; o.data.name = name
    bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6); bm.to_mesh(o.data); bm.free()
    # weighted normals (face area) on all-smooth geometry: flat faces stay flat, the edge strips carry the bend; the bake encodes the rest
    o.data.use_auto_smooth = True; o.data.auto_smooth_angle = math.pi
    w = o.modifiers.new('wn', 'WEIGHTED_NORMAL'); w.mode = 'FACE_AREA'; w.weight = 50; w.keep_sharp = False; w.thresh = 0.01
    with bpy.context.temp_override(object=o, active_object=o): bpy.ops.object.modifier_apply(modifier=w.name)
    # UVs: smart project, islands packed into 0-1 with a margin (2048 frame/slide, 1024 others -> ~8 px)
    size = 2048 if asm in ('Frame', 'Slide') else 1024
    for x in bpy.context.view_layer.objects: x.select_set(False)
    o.select_set(True); bpy.context.view_layer.objects.active = o
    if not o.data.uv_layers: o.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(35 if asm == 'Barrel' else 60), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method='FRACTION', margin=8.0 / size, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    m = bpy.data.materials.get('M_G17_' + asm) or bpy.data.materials.new('M_G17_' + asm)
    o.data.materials.clear(); o.data.materials.append(m); o.data.polygons.foreach_set('material_index', [0] * len(o.data.polygons))
    o['tex_size'] = size
    report[name] = dict(tris=tris(o), verts=len(o.data.vertices))
    log('ASSEMBLY', name, report[name])
# LODs
for asm in ASM:
    o = bpy.data.objects['SM_G17_' + asm]
    for k, r in (('LOD1', 0.45), ('LOD2', 0.18)):
        me = o.data.copy(); l = bpy.data.objects.new(o.name + '_' + k, me); lcol.objects.link(l)
        m = l.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = r; m.use_collapse_triangulate = True
        with bpy.context.temp_override(object=l, active_object=l): bpy.ops.object.modifier_apply(modifier=m.name)
        report[l.name] = dict(tris=tris(l))
# collision: three convex hulls of the frame LOD0 (grip, receiver, dust cover)
fr = bpy.data.objects['SM_G17_Frame']; co = np.array([v.co[:] for v in fr.data.vertices]); G = co * np.array([1000, -1000, 1000])
regions = [('00', (G[:, 2] < 2.0) & (G[:, 1] < 22.0)), ('01', (G[:, 2] >= -2.0) & (G[:, 1] < 62.0)), ('02', (G[:, 1] >= 58.0) & (G[:, 2] > 5.0))]
for k, sel in regions:
    bm = bmesh.new(); vs = [bm.verts.new(tuple(p)) for p in co[sel]]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    bmesh.ops.delete(bm, geom=list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid}), context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new('UCX_SM_G17_Frame_' + k); bm.to_mesh(me); bm.free()
    u = bpy.data.objects.new('UCX_SM_G17_Frame_' + k, me); lcol.objects.link(u); u.display_type = 'WIRE'
    report[u.name] = dict(tris=tris(u))
hcol.hide_render = True
for o in hcol.objects: o.hide_set(True)
lcol.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(report, open(os.path.join(HERE, 'work', 'low_report.json'), 'w'), indent=1)
log('LOW_DONE %.0fs total LOD0 tris %d' % (time.time() - t0, sum(v['tris'] for k, v in report.items() if k.startswith('SM_') and '_LOD' not in k)))
