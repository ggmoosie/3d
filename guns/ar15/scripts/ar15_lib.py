"""ar15_lib.py - shared library of the modular AR-15 kit (LootNShoot).  Blender 4.0, headless, no external assets.

Same conventions as Tools/bpy/station_props/make_station_props.py (metres in Blender -> cm in the FBX through
apply_unit_scale + FBX_SCALE_NONE, axis_forward '-Y', axis_up 'Z', UE Y mirror baked into the data, closed shells,
UCX_ hulls checked convex), plus what a hand-held weapon needs: true-arc fillets, EXACT booleans, bevel + weighted
normals (custom normals exported to UE), per-slot UV atlases, Cycles mask bakes, LODs and a rigid skeletal variant.

Modelling happens in the G frame (ar15_spec.py: mm, UE axes, origin = bore at the upper's front face).  Part.finalize()
moves every piece to the game frame (G2F), bakes the UE Y mirror, converts mm -> m and only THEN bevels, so custom
normals are never mirrored.  Scene objects are therefore true-handed (muzzle toward Blender -Y)."""
import bpy, bmesh, math, os, sys, json, time
import numpy as np
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
from ar15_spec import *            # noqa: F401,F403  (dimensions)
import ar15_spec as SP

OUT = os.path.join(HERE, 'out')
for d in ('', 'parts', 'renders', 'bake', 'lod', 'progress'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
MM = 0.001

def log(*a):
    print('[ar15]', *a); sys.stdout.flush()

# ================================================================================================ scene basics
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
    return sc

def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name); (parent or bpy.context.scene.collection).children.link(c)
    return c

def kill(o):
    if o is None: return
    me = o.data if o.type == 'MESH' else None
    bpy.data.objects.remove(o, do_unlink=True)
    if me is not None and me.users == 0: bpy.data.meshes.remove(me)

def bm_obj(bm, name='_s', collection=None, free=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me)
    if free: bm.free()
    o = bpy.data.objects.new(name, me); (collection or bpy.context.scene.collection).objects.link(o); return o

def obj_bm(o, kill_obj=True):
    bm = bmesh.new(); bm.from_mesh(o.data)
    if kill_obj: kill(o)
    return bm

def bm_copy(bm):
    me = bpy.data.meshes.new('_c'); bm.to_mesh(me); b2 = bmesh.new(); b2.from_mesh(me); bpy.data.meshes.remove(me); return b2

def bm_join(*bms):
    """merge bmeshes into one (no boolean: disjoint shells only).  Frees the inputs."""
    out = bmesh.new(); me = bpy.data.meshes.new('_j')
    for b in bms:
        if b is None: continue
        b.to_mesh(me); out.from_mesh(me); b.free()
    bpy.data.meshes.remove(me); return out

def xf(bm, M):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts); return bm

def T(x=0.0, y=0.0, z=0.0): return Matrix.Translation(V((x, y, z)))
def Rx(d): return Matrix.Rotation(math.radians(d), 4, 'X')
def Ry(d): return Matrix.Rotation(math.radians(d), 4, 'Y')
def Rz(d): return Matrix.Rotation(math.radians(d), 4, 'Z')
def S(x, y=None, z=None): return Matrix.Diagonal((x, x if y is None else y, x if z is None else z, 1.0))
def about(M, p):
    """matrix M applied about point p"""
    return T(*p) @ M @ T(-p[0], -p[1], -p[2])
def mirror_x(bm):
    """mirror across X = 0 (keeps the shell closed and outward)"""
    xf(bm, S(-1, 1, 1)); bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); return bm

# ================================================================================================ 2-D profiles
def clean2d(pts, eps=1e-6):
    out = []
    for p in pts:
        p = (float(p[0]), float(p[1]))
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > eps: out.append(p)
    while len(out) > 2 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) <= eps: out.pop()
    return out

def area2d(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % len(pts)]; a += x0 * y1 - x1 * y0
    return a * 0.5

def ccw(pts):
    pts = clean2d(pts); return pts if area2d(pts) > 0 else pts[::-1]

def fillet(pts, r, seg=4, closed=True):
    """round polygon corners with true circular arcs tangent to both edges.
    r: scalar or per-vertex list (0 = sharp corner); seg = segments per 90 degrees of turn."""
    P = [np.array(p, float) for p in clean2d(pts)]; n = len(P)
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * n
    out = []
    for i in range(n):
        b = P[i]
        if (not closed and (i == 0 or i == n - 1)) or rs[i] <= 0:
            out.append((b[0], b[1])); continue
        a, c = P[i - 1], P[(i + 1) % n]
        u = a - b; w = c - b; lu = np.linalg.norm(u); lw = np.linalg.norm(w)
        if lu < 1e-9 or lw < 1e-9: out.append((b[0], b[1])); continue
        u = u / lu; w = w / lw
        ang = math.acos(max(-1.0, min(1.0, float(np.dot(u, w)))))
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3: out.append((b[0], b[1])); continue
        t = min(rs[i] / math.tan(ang / 2), lu * 0.499, lw * 0.499)
        rr = t * math.tan(ang / 2)
        bis = u + w; bis = bis / np.linalg.norm(bis)
        cen = b + bis * (rr / math.sin(ang / 2))
        p0 = b + u * t; p1 = b + w * t
        a0 = math.atan2(p0[1] - cen[1], p0[0] - cen[0]); a1 = math.atan2(p1[1] - cen[1], p1[0] - cen[0])
        d = a1 - a0
        while d > math.pi: d -= 2 * math.pi
        while d < -math.pi: d += 2 * math.pi
        k = max(1, int(math.ceil(abs(d) / (math.pi / 2) * seg - 1e-6)))
        for j in range(k + 1):
            aa = a0 + d * j / k; out.append((cen[0] + rr * math.cos(aa), cen[1] + rr * math.sin(aa)))
    return clean2d(out)

def circle(r, n=24, c=(0.0, 0.0), phase=0.0):
    return [(c[0] + r * math.cos(phase + 2 * math.pi * k / n), c[1] + r * math.sin(phase + 2 * math.pi * k / n)) for k in range(n)]

def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

def rrect(u0, v0, u1, v1, r, seg=4):
    return fillet(rect(u0, v0, u1, v1), r, seg)

def stadium(c, length, width, seg=6, angle=0.0):
    """rounded slot centred on c, `length` along the angle direction"""
    r = width / 2.0; h = max(0.0, length / 2.0 - r); pts = []
    for k in range(seg + 1):
        a = -math.pi / 2 + math.pi * k / seg; pts.append((h + r * math.cos(a), r * math.sin(a)))
    for k in range(seg + 1):
        a = math.pi / 2 + math.pi * k / seg; pts.append((-h + r * math.cos(a), r * math.sin(a)))
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in pts]

def offset2d(pts, d):
    """naive polygon offset (miter) by d (positive = outward for CCW polygons); fine for convex-ish profiles"""
    P = [np.array(p, float) for p in ccw(pts)]; n = len(P); out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        e0 = b - a; e1 = c - b
        n0 = np.array([e0[1], -e0[0]]) / max(1e-12, np.linalg.norm(e0))
        n1 = np.array([e1[1], -e1[0]]) / max(1e-12, np.linalg.norm(e1))
        m = n0 + n1; lm = np.linalg.norm(m)
        if lm < 1e-9: m = n0; lm = 1.0
        m = m / lm; s = d / max(0.2, float(np.dot(m, n0)))
        out.append(tuple(b + m * s))
    return out

# ================================================================================================ solids (bmesh, mm)
_PLANES = {
    'YZ': lambda u, v, w: (w, u, v),     # profile (Y, Z), extruded along X
    'XZ': lambda u, v, w: (u, w, v),     # profile (X, Z), extruded along Y
    'XY': lambda u, v, w: (u, v, w),     # profile (X, Y), extruded along Z
}

def prism(prof, plane, w0, w1):
    """closed prism of a 2-D profile in `plane`, extruded from w0 to w1 along the third axis"""
    f = _PLANES[plane]; prof = clean2d(prof); bm = bmesh.new(); n = len(prof)
    a = [bm.verts.new(f(u, v, w0)) for u, v in prof]; b = [bm.verts.new(f(u, v, w1)) for u, v in prof]
    for k in range(n): bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(a[::-1]); bm.faces.new(b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def loft(rings, caps=True, closed=False):
    """closed solid through rings of 3-D points (same count, consistent orientation)"""
    bm = bmesh.new(); R = [[bm.verts.new(tuple(p)) for p in ring] for ring in rings]; m = len(rings[0])
    nr = len(R)
    for i in range(nr if closed else nr - 1):
        a, b = R[i], R[(i + 1) % nr]
        for k in range(m): bm.faces.new((a[k], a[(k + 1) % m], b[(k + 1) % m], b[k]))
    if caps and not closed:
        bm.faces.new(R[0][::-1]); bm.faces.new(R[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def lathe(prof, segs=32, axis='Y', c=(0.0, 0.0), phase=0.0, loop=False):
    """revolve [(r, a)] around an axis ('Y': ring in X/Z around c=(x, z); 'X': ring in Y/Z around c=(y, z);
    'Z': ring in X/Y around c=(x, y)).  r == 0 makes a pole; loop=True closes the profile (rings, tubes)."""
    bm = bmesh.new(); rings = []
    def P(r, a, t):
        cu, cv = c[0] + r * math.cos(t), c[1] + r * math.sin(t)
        if axis == 'Y': return (cu, a, cv)
        if axis == 'X': return (a, cu, cv)
        return (cu, cv, a)
    for (r, a) in prof:
        if r < 1e-9: rings.append([bm.verts.new(P(0.0, a, 0.0))])
        else: rings.append([bm.verts.new(P(r, a, phase + 2 * math.pi * k / segs)) for k in range(segs)])
    pairs = list(range(len(rings) - 1)) + ([len(rings) - 1] if loop else [])
    for i in pairs:
        A, B = rings[i], rings[(i + 1) % len(rings)]
        for k in range(segs):
            k1 = (k + 1) % segs
            if len(A) == 1 and len(B) == 1: continue
            if len(A) == 1: bm.faces.new((A[0], B[k1], B[k]))
            elif len(B) == 1: bm.faces.new((A[k], A[k1], B[0]))
            else: bm.faces.new((A[k], A[k1], B[k1], B[k]))
    if not loop:
        if len(rings[0]) > 1: bm.faces.new(rings[0][::-1])
        if len(rings[-1]) > 1: bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return bm

def cyl(axis, c, r, a0, a1, segs=24, phase=None):
    """cylinder along an axis ('X', 'Y', 'Z') through c (the two other coordinates), from a0 to a1"""
    if phase is None: phase = math.pi / segs
    return lathe([(r, a0), (r, a1)], segs, axis, c, phase)

def tube(axis, c, ro, ri, a0, a1, segs=24, phase=None):
    if phase is None: phase = math.pi / segs
    return lathe([(ri, a0), (ro, a0), (ro, a1), (ri, a1)], segs, axis, c, phase, loop=True)

def box(lo, hi):
    lo, hi = V(lo), V(hi); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    return xf(bm, T(*((lo + hi) * 0.5)) @ S(*(hi - lo)))

def rod(p0, p1, r, segs=12):
    """cylinder between two 3-D points"""
    p0, p1 = V(p0), V(p1); d = p1 - p0; L = d.length
    bm = lathe([(r, 0.0), (r, L)], segs, 'Z', (0.0, 0.0), math.pi / segs)
    q = V((0, 0, 1)).rotation_difference(d.normalized())
    return xf(bm, T(*p0) @ q.to_matrix().to_4x4())

def sphere(c, r, segs=16, rings=8):
    prof = [(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings)) for i in range(rings + 1)]
    return xf(lathe(prof, segs, 'Z'), T(*c))

def lathe_on(prof, segs, origin, direction, phase=None, loop=False):
    """lathe [(r, along)] around an arbitrary axis through `origin` along `direction`"""
    if phase is None: phase = math.pi / segs
    bm = lathe(prof, segs, 'Z', (0.0, 0.0), phase, loop)
    q = V((0, 0, 1)).rotation_difference(V(direction).normalized())
    return xf(bm, T(*origin) @ q.to_matrix().to_4x4())

def helix(origin, direction, r, wire_r, turns, length, seg_turn=16, wire_segs=6):
    """coil spring: a circle swept along a helix (closed tube with caps)"""
    n = int(turns * seg_turn); rings = []
    for i in range(n + 1):
        t = i / n; a = 2 * math.pi * turns * t
        c = V((r * math.cos(a), r * math.sin(a), length * t))
        tan = V((-r * math.sin(a) * 2 * math.pi * turns, r * math.cos(a) * 2 * math.pi * turns, length)).normalized()
        nrm = V((math.cos(a), math.sin(a), 0.0)); bin_ = tan.cross(nrm).normalized(); nrm = bin_.cross(tan).normalized()
        rings.append([c + (nrm * math.cos(2 * math.pi * k / wire_segs) + bin_ * math.sin(2 * math.pi * k / wire_segs)) * wire_r
                      for k in range(wire_segs)])
    bm = loft(rings)
    q = V((0, 0, 1)).rotation_difference(V(direction).normalized())
    return xf(bm, T(*origin) @ q.to_matrix().to_4x4())

# ================================================================================================ booleans (EXACT)
def boolean(base, others, op='DIFFERENCE', self_inter=False, hole_tolerant=False):
    """EXACT boolean of bmesh `base` with a list of bmeshes (all freed); returns a new bmesh"""
    others = [b for b in (others if isinstance(others, (list, tuple)) else [others]) if b is not None]
    if not others: return base
    o = bm_obj(base, '_bool_base')
    c = bpy.data.collections.new('_bool_ops'); bpy.context.scene.collection.children.link(c)
    objs = []
    for i, b in enumerate(others):
        me = bpy.data.meshes.new('_op'); b.to_mesh(me); b.free()
        oo = bpy.data.objects.new('_op%d' % i, me); c.objects.link(oo); objs.append(oo)
    m = o.modifiers.new('bool', 'BOOLEAN'); m.operation = op; m.solver = 'EXACT'
    m.operand_type = 'COLLECTION'; m.collection = c; m.use_self = self_inter; m.use_hole_tolerant = hole_tolerant
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bm = bmesh.new(); bm.from_mesh(me2); bpy.data.meshes.remove(me2)
    for oo in objs: kill(oo)
    bpy.data.collections.remove(c); kill(o)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return bm

def union(*bms, self_inter=False):
    bms = [b for b in bms if b is not None]
    if len(bms) == 1: return bms[0]
    return boolean(bms[0], list(bms[1:]), 'UNION', self_inter=self_inter)

def cut(base, *cutters): return boolean(base, list(cutters), 'DIFFERENCE')
def inter(base, other): return boolean(base, [other], 'INTERSECT')

# ================================================================================================ material slots
SLOT_PREVIEW = {  # linear base colours used by the preview / render materials (the UE side only reads the names)
    'Receiver': (0.030, 0.031, 0.034), 'Steel': (0.040, 0.040, 0.036), 'BCG': (0.060, 0.060, 0.058),
    'Polymer': (0.024, 0.024, 0.024), 'Handguard': (0.030, 0.031, 0.034), 'Brass': (0.62, 0.42, 0.15)}

def slot_mat(name):
    if name not in SP.ALL_SLOTS: raise ValueError('material slot not allowed: ' + name)
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        c = SLOT_PREVIEW[name]; m.diffuse_color = (*c, 1.0)
        b = m.node_tree.nodes.get('Principled BSDF')
        if b: b.inputs['Base Color'].default_value = (*c, 1.0)
    return m

# ================================================================================================ topology checks
def topo_check(me):
    """(non-manifold edges, inside-out shells, degenerate faces, shells) - every part must be closed shells"""
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    nm = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    comp = [-1] * len(bm.faces); nc = 0
    for f0 in bm.faces:
        if comp[f0.index] >= 0: continue
        stack = [f0]; comp[f0.index] = nc
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if comp[g.index] < 0: comp[g.index] = nc; stack.append(g)
        nc += 1
    vol = np.zeros(nc)
    for f in bm.faces:
        cidx = comp[f.index]; pts = [np.array(v.co[:], dtype=np.float64) for v in f.verts]
        for i in range(1, len(pts) - 1): vol[cidx] += np.dot(pts[0], np.cross(pts[i], pts[i + 1]))
    degen = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    bm.free()
    return nm, int((vol <= 0).sum()), degen, nc

def tri_count(me):
    lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt); return int((lt - 2).sum())

# ================================================================================================ parts
PARTS = {}          # name -> Part (registry, insertion order = build order)

class Part:
    """one kit part.  pieces: (bmesh in G mm, slot, finish kwargs).  finalize() -> one Blender object (metres, true-handed)."""
    def __init__(self, name, label, group, configs=('MLOK', 'QUAD'), bone='root', pivot=None, motion=None,
                 explode=(0.0, 0.0, 0.0), budget=None, static=True):
        self.name, self.label, self.group = name, label, group
        self.static = static          # False: hidden internal part, left out of the merged SM_ meshes (kept in parts + skeletal)
        self.configs = set(configs); self.bone = bone
        self.pivot = pivot            # G mm (moving parts: hinge / travel origin)
        self.motion = motion          # dict: type rotate|translate, axis (UE), limits ...
        self.explode = explode        # G mm offset for the exploded view
        self.budget = budget
        self.pieces = []; self.obj = None; self.info = {}
        self.atlas = 'kit' if configs else 'own'   # 'kit': kit-wide atlases per slot; 'own': the part's own atlases (accessories)
    def add(self, bm, slot, bevel=0.4, segs=2, angle=35.0, profile=0.5, sharp=35.0, wn=True, clamp=True):
        self.pieces.append((bm, slot, dict(bevel=bevel, segs=segs, angle=angle, profile=profile, sharp=sharp, wn=wn, clamp=clamp)))
        return bm

def g_to_scene_matrix():
    """G mm (UE axes) -> Blender scene metres (true-handed): (x, y, z) -> ((x+ox), -(y+oy), (z+oz)) * 0.001"""
    ox, oy, oz = SP.G2F
    return S(MM, -MM, MM) @ T(ox, oy, oz)

def g2b(p):
    """G point (mm) -> Blender scene point (m)"""
    return V(((p[0] + SP.G2F[0]) * MM, -(p[1] + SP.G2F[1]) * MM, (p[2] + SP.G2F[2]) * MM))

def b2f_cm(v):
    """Blender scene point (m) -> F / UE (cm)"""
    return (v[0] * 100.0, -v[1] * 100.0, v[2] * 100.0)

def apply_mods(o):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = o.data; o.modifiers.clear(); o.data = me; me.name = old.name
    if old.users == 0: bpy.data.meshes.remove(old)

def _dissolve_collinear(bm, ang=0.05):
    vs = []
    for v in bm.verts:
        if len(v.link_edges) != 2: continue
        a, b = [e.other_vert(v).co - v.co for e in v.link_edges]
        if a.length > 0 and b.length > 0 and a.angle(b) > math.pi - math.radians(ang): vs.append(v)
    if vs: bmesh.ops.dissolve_verts(bm, verts=vs)

def triangulate_keep_normals(o, eps=1e-11):
    """triangulate in bmesh carrying the custom split normals through per-corner float layers; zero-area triangles
    (collinear boundary vertices) are repaired by rotating their longest edge.  Returns the number left (should be 0)."""
    me = o.data; me.calc_normals_split()
    n = np.empty(len(me.loops) * 3); me.loops.foreach_get('normal', n); n = n.reshape(-1, 3)
    bm = bmesh.new(); bm.from_mesh(me)
    lay = [bm.loops.layers.float.new(k) for k in ('_nx', '_ny', '_nz')]
    bm.faces.ensure_lookup_table()
    for f, p in zip(bm.faces, me.polygons):
        for i, l in enumerate(f.loops):
            v = n[p.loop_start + i]; l[lay[0]], l[lay[1]], l[lay[2]] = v[0], v[1], v[2]
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    left = 0
    for it in range(6):
        bad = [f for f in bm.faces if f.calc_area() < eps]
        left = len(bad)
        if not bad: break
        es = set()
        for f in bad:
            e = max(f.edges, key=lambda e: e.calc_length())
            if len(e.link_faces) == 2: es.add(e)
        if es: bmesh.ops.rotate_edges(bm, edges=list(es), use_ccw=(it % 2 == 1))
    bm.to_mesh(me); bm.free()
    cn = np.zeros((len(me.loops), 3))
    for k, name in enumerate(('_nx', '_ny', '_nz')):
        a = np.empty(len(me.loops)); me.attributes[name].data.foreach_get('value', a); cn[:, k] = a
        me.attributes.remove(me.attributes[name])
    ln = np.linalg.norm(cn, axis=1, keepdims=True); cn = cn / np.maximum(ln, 1e-12)
    me.use_auto_smooth = True
    me.normals_split_custom_set([tuple(v) for v in cn])
    return left

def finish_obj(o, bevel=0.4, segs=2, angle=35.0, profile=0.5, sharp=35.0, wn=True, clamp=True, tri=True):
    """bevel (angle limited, width in mm) -> weld degenerate bevel geometry -> weighted normals (face area, keep sharp)
    -> triangulate keeping the custom normals"""
    me = o.data
    me.use_auto_smooth = True; me.auto_smooth_angle = math.radians(sharp)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if bevel > 0:
        b = o.modifiers.new('bevel', 'BEVEL'); b.width = bevel * MM; b.segments = segs
        b.limit_method = 'ANGLE'; b.angle_limit = math.radians(angle); b.profile = profile
        b.use_clamp_overlap = clamp; b.loop_slide = True; b.harden_normals = False
        b.miter_outer = 'MITER_ARC' if segs > 1 else 'MITER_SHARP'
        apply_mods(o)
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-6, edges=bm.edges[:])
    _dissolve_collinear(bm)
    bm.to_mesh(me); bm.free()
    if wn:
        w = o.modifiers.new('wnormal', 'WEIGHTED_NORMAL'); w.mode = 'FACE_AREA'; w.keep_sharp = True; w.weight = 50
        apply_mods(o)
    if tri: o['degenerate_left'] = triangulate_keep_normals(o)

def clean_bm(bm, dist=0.004, angle=0.25):
    """tidy a boolean result before bevelling (mm units): weld, drop degenerate edges, merge coplanar faces and dissolve
    collinear boundary vertices so the triangulation never needs zero-area triangles"""
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.dissolve_degenerate(bm, dist=dist, edges=bm.edges[:])
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:], delimit=set())
    vs = [v for v in bm.verts if len(v.link_edges) == 2]
    if vs: bmesh.ops.dissolve_verts(bm, verts=vs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm

def _contract_slot_order(o):
    """material slots in the contract order (Receiver, Steel, BCG, Polymer, Handguard)"""
    me = o.data; names = [m.name for m in me.materials]
    order = sorted(range(len(names)), key=lambda i: SP.ALL_SLOTS.index(names[i]))
    if order == list(range(len(names))): return
    mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    remap = np.empty(len(names), np.int64)
    for new, old in enumerate(order): remap[old] = new
    mats = [me.materials[i] for i in order]; me.materials.clear()
    for m in mats: me.materials.append(m)
    me.polygons.foreach_set('material_index', remap[mi])

def finalize(P, collection=None):
    """build the part object: each piece -> scene frame -> finish -> join; checks; registry"""
    t0 = time.time(); objs = []; M = g_to_scene_matrix()
    for i, (bm, slot, kw) in enumerate(P.pieces):
        clean_bm(bm)
        xf(bm, M); bmesh.ops.reverse_faces(bm, faces=bm.faces[:])          # Y mirror flips the winding back
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        o = bm_obj(bm, '%s_p%d' % (P.name, i), collection)
        o.data.materials.append(slot_mat(slot))
        for p in o.data.polygons: p.material_index = 0
        finish_obj(o, **kw)
        o.data.attributes.new('_piece', 'INT', 'POINT').data.foreach_set('value', [i] * len(o.data.vertices))   # for folds (sights)
        objs.append(o)
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]):
            bpy.ops.object.join()
    o = objs[0]; o.name = P.name; o.data.name = P.name
    _contract_slot_order(o)
    nm, inv, degen, shells = topo_check(o.data)
    P.obj = o
    P.info = dict(tris=tri_count(o.data), nm=nm, inv=inv, degen=degen, shells=shells,
                  slots=[m.name for m in o.data.materials], secs=time.time() - t0)
    errs = []
    if nm: errs.append('%d non-manifold edges' % nm)
    if inv: errs.append('%d inside-out shells' % inv)
    if degen: errs.append('%d degenerate faces' % degen)
    if P.budget and P.info['tris'] > P.budget: errs.append('tris %d > budget %d' % (P.info['tris'], P.budget))
    P.info['errs'] = errs
    PARTS[P.name] = P
    log('PART %-28s tris %6d  shells %3d  slots %-22s %5.1fs  %s' % (P.name, P.info['tris'], shells, ','.join(P.info['slots']),
        P.info['secs'], 'OK' if not errs else 'FAIL ' + '; '.join(errs)))
    return o

# ================================================================================================ Picatinny (MIL-STD-1913)
def pic_profile(top, base, half_w=None):
    """(X, Z) cross-section of a 1913 rail head: top flat 15.67, 45 deg up chamfers to the 21.2 edge, 0.5 mm land,
    45 deg undercut to the 15.8 neck, neck down to `base` (merged into the body)"""
    hw = (half_w or SP.PIC_W / 2.0); ht = SP.PIC_TOP_W / 2.0
    zc = top - (hw - ht)                 # chamfer bottom = widest edge
    zl = zc - 0.5                        # land bottom
    hn = 7.9; zn = zl - (hw - hn)        # neck
    pts = [(-hn, base), (hn, base), (hn, zn), (hw, zl), (hw, zc), (ht, top), (-ht, top), (-hw, zc), (-hw, zl), (-hn, zn)]
    return pts

def pic_rail(y0, y1, top, base, slots_from=None, n_slots=None, chamfer=0.45):
    """straight rail along +Y (G): head prism + slot cutters.  Slots 5.23 wide every 10.01, depth 3.0 from the top,
    starting at slots_from (slot centre) and counting n_slots.  The cutters flare 45 deg over the top `chamfer` mm, so the
    lug edges come out chamfered without a bevel modifier (rails are finished unbevelled: 1913 profile + these chamfers).
    Returns (head bmesh, cutters, [slot centre Y])."""
    head = prism(pic_profile(top, base), 'XZ', y0, y1)
    cs = []
    if n_slots:
        for k in range(n_slots):
            yc = slots_from + k * SP.PIC_PITCH; cs.append(yc)
    w = SP.PIC_SLOT_W / 2; fl = top - SP.PIC_SLOT_D; c = chamfer
    cutters = [prism([(yc - w, fl), (yc + w, fl), (yc + w, top - c), (yc + w + c + 4.0, top + 4.0), (yc - w - c - 4.0, top + 4.0), (yc - w, top - c)],
                     'YZ', -SP.PIC_W, SP.PIC_W) for yc in cs]
    return head, cutters, cs

def rail_slots_fit(y0, y1, margin=3.0):
    """slot centres for a rail from y0 to y1: as many 10.01 slots as fit with >= margin of lug at each end, centred"""
    L = y1 - y0; n = int(math.floor((L - 2 * margin - SP.PIC_SLOT_W) / SP.PIC_PITCH)) + 1
    span = (n - 1) * SP.PIC_PITCH; first = y0 + (L - span) / 2.0
    return first, n

# ================================================================================================ collision hulls (station_props helpers)
def fib_dirs(n):
    ga = math.pi * (3.0 - math.sqrt(5.0)); out = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n; r = math.sqrt(max(0.0, 1.0 - z * z)); out.append((r * math.cos(ga * i), r * math.sin(ga * i), z))
    return np.array(out)

def support_pts(pts, n=40):
    A = np.array([tuple(p) for p in pts]); idx = np.unique(np.argmax(A @ fib_dirs(n).T, axis=0)); return [V(A[i]) for i in idx]

def _hull_once(pts):
    uniq = {}
    for p in pts: uniq[(round(p.x, 7), round(p.y, 7), round(p.z, 7))] = V(p)
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in uniq.values()]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    kill = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if kill: bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def _bm_convexity(bm):
    bm.normal_update(); co = np.array([v.co[:] for v in bm.verts]); worst = 0.0
    for f in bm.faces:
        n = np.array(f.normal[:]); p = np.array(f.verts[0].co[:]); worst = max(worst, float(((co - p) @ n).max()))
    return worst

def hull_bm(pts, tol=1e-6):
    """convex hull; bmesh's hull can return a non-convex shell on near-coplanar input, so it is checked and recomputed
    with a growing sub-micron jitter until every vertex is behind every face plane"""
    rng = np.random.default_rng(11); base = [V(p) for p in pts]; bm = None
    for k, jit in enumerate((0.0, 2e-7, 1e-6, 5e-6, 2e-5, 1e-4)):
        if bm is not None: bm.free()
        P = base if jit == 0 else [p + V(rng.normal(0, jit, 3)) for p in base]
        bm = _hull_once(P)
        if _bm_convexity(bm) < tol: return bm
        # second pass on the hull's own vertices often settles it
        b2 = _hull_once([v.co.copy() for v in bm.verts])
        if _bm_convexity(b2) < tol: bm.free(); return b2
        b2.free()
    return bm

def hull_check(me):
    """(closed, worst distance of a hull vertex outside any face plane) - convex hulls give ~0"""
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    closed = all(len(e.link_faces) == 2 for e in bm.edges) and len(bm.faces) >= 4
    co = np.array([v.co[:] for v in bm.verts], dtype=np.float64); worst = 0.0
    for f in bm.faces:
        n = np.array(f.normal[:]); p = np.array(f.verts[0].co[:]); worst = max(worst, float(((co - p) @ n).max()))
    bm.free(); return closed, worst

# ================================================================================================ render helpers
def look_at(cam, target, loc):
    cam.location = loc
    d = V(target) - V(loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def world_bounds(objs):
    pts = []
    for o in objs:
        if o.type != 'MESH': continue
        co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        M = np.array(o.matrix_world); pts.append(co @ M[:3, :3].T + M[:3, 3])
    A = np.concatenate(pts); return A.min(0), A.max(0)
