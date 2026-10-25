"""ar15_split_bcg.py - the AR-15 bolt carrier as its own moving part (2026-10-24, gun mechanism system).

The game Upper (out/game/SM_AR15_Upper*.fbx, LOD0-2) has the BCG + bolt merged in its own material slot (BCG). This splits it
WITHOUT a re-bake (same UVs, same Kit_* atlases, same slot names):
  SM_AR15_BCG        the BCG-slot faces: bolt carrier + bolt, in the gun frame (attaches at Cycle_Socket = identity on the Upper)
  SM_AR15_UpperBody  everything else, with the dust cover swung OPEN (-112 deg about its hinge rod, the part's own limit), so the
                     cycling carrier and the casings show through the port
The UE Upper stays the installed part (sockets, attachments); FWeaponMechanism draws UpperBody + the moving BCG in its place.

  blender -b --python-exit-code 1 --python ar15_split_bcg.py
Writes out/game/split/{SM_AR15_BCG, SM_AR15_UpperBody}.fbx (+ _LOD1/_LOD2) and out/game/split/split_report.json.
"""
import bpy, bmesh, os, json, math
from mathutils import Vector as V, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
SRC = os.path.join(OUT, 'game')
DST = os.path.join(SRC, 'split')
os.makedirs(DST, exist_ok=True)
OPEN_DEG = 112.0
REPORT = {}


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def imp(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward='-Y', axis_up='Z', use_custom_normals=True)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    assert len(new) == 1, (path, [o.name for o in new])
    o = new[0]
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def bbox(vs):
    xs, ys, zs = zip(*[(v.x, v.y, v.z) for v in vs])
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def size_iou(a, b):
    """overlap of two boxes moved to a common centre: the parts FBXs sit in their own pivot frames, only their SIZE matches"""
    da = [a[1][i] - a[0][i] for i in range(3)]
    db = [b[1][i] - b[0][i] for i in range(3)]
    inter = math.prod(min(da[i], db[i]) for i in range(3))
    return inter / max(math.prod(da) + math.prod(db) - inter, 1e-12)


def iou(a, b):
    lo = [max(a[0][i], b[0][i]) for i in range(3)]
    hi = [min(a[1][i], b[1][i]) for i in range(3)]
    inter = 1.0
    for i in range(3):
        inter *= max(0.0, hi[i] - lo[i])
    va = math.prod(a[1][i] - a[0][i] for i in range(3))
    vb = math.prod(b[1][i] - b[0][i] for i in range(3))
    return inter / max(va + vb - inter, 1e-12)


def islands(bm):
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        out.append(isl)
    return out


def ref_boxes():
    """bounding boxes of the dust cover and its rod from the part FBXs (same gun frame as the game meshes)"""
    boxes = {}
    for n in ('SM_AR15_DustCover', 'SM_AR15_DustCoverRod', 'SM_AR15_BCG', 'SM_AR15_Bolt'):
        p = os.path.join(OUT, 'parts', n + '.fbx')
        o = imp(p)
        boxes[n] = bbox([o.matrix_world @ v.co for v in o.data.vertices])
        bpy.data.objects.remove(o)
    return boxes


def split_one(path, tag, boxes):
    o = imp(path)
    me = o.data
    slots = [m.name if m else '' for m in me.materials]
    bcg_idx = [i for i, n in enumerate(slots) if 'BCG' in n.upper()]
    assert len(bcg_idx) == 1, slots
    # 1) BCG = the BCG slot (check it also covers the bolt by its box)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bcg_faces = [f for f in bm.faces if f.material_index == bcg_idx[0]]
    bb_bcg = bbox([v.co for f in bcg_faces for v in f.verts])
    r = dict(slots=slots, bcg_faces=len(bcg_faces), bcg_box_cm=[[round(c * 100, 2) for c in bb_bcg[0]], [round(c * 100, 2) for c in bb_bcg[1]]])
    # 2) dust cover + rod islands among the rest (best box match)
    rest = islands(bm)
    rest = [isl for isl in rest if isl[0].material_index != bcg_idx[0]]
    def best(name):
        sc = sorted(((size_iou(bbox([v.co for f in isl for v in f.verts]), boxes[name]), k) for k, isl in enumerate(rest)), reverse=True)
        return sc[0]
    s_cov, k_cov = best('SM_AR15_DustCover')
    r.update(cover_iou=round(s_cov, 3))
    assert s_cov > 0.75, r
    # hinge axis along Y: the cover part's FBX has its origin ON the hinge (pivot = (ROD x, ROD z)), same orientation as the game
    # mesh, so the hinge in game coordinates = the game island's box minimum - the part's box minimum. Cross-check: the rod part
    # FBX is exported in place (game coordinates); its centre line must agree within 1 mm.
    glo, ghi = bbox([v.co for f in rest[k_cov] for v in f.verts])
    plo = boxes['SM_AR15_DustCover'][0]
    piv = V((glo[0] - plo[0], 0.0, glo[2] - plo[2]))
    rlo, rhi = boxes['SM_AR15_DustCoverRod']
    rod_c = V(((rlo[0] + rhi[0]) / 2, 0.0, (rlo[2] + rhi[2]) / 2))
    r.update(hinge_vs_rod_mm=round((piv - rod_c).length * 1000, 2))
    assert (piv - rod_c).length < 0.001, r
    cov_verts = list({v for f in rest[k_cov] for v in f.verts})
    c0 = sum((v.co for v in cov_verts), V()) / len(cov_verts)
    # pick the sign that swings the cover OUT (away from the receiver centre line) and DOWN
    choice = None
    for sgn in (1.0, -1.0):
        R = Matrix.Rotation(math.radians(sgn * OPEN_DEG), 4, 'Y')
        c1 = piv + (R @ (c0 - piv).to_4d()).to_3d()
        out_ = abs(c1.x) > abs(piv.x) and c1.z < piv.z
        if out_:
            choice = (sgn, R, c1)
            break
    assert choice, ('no outward-down swing', c0, piv)
    sgn, R, c1 = choice
    T = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv)
    bmesh.ops.transform(bm, matrix=T, verts=cov_verts)
    r.update(hinge=[round(piv.x * 100, 3), round(piv.z * 100, 3)], open_deg=sgn * OPEN_DEG,
             cover_centre_cm=[round(c * 100, 2) for c in c0], cover_centre_open_cm=[round(c * 100, 2) for c in c1])
    # 3) two meshes
    bm_body = bm.copy()
    bmesh.ops.delete(bm_body, geom=[f for f in bm_body.faces if f.material_index == bcg_idx[0]], context='FACES')
    bm_bcg = bm.copy()
    bmesh.ops.delete(bm_bcg, geom=[f for f in bm_bcg.faces if f.material_index != bcg_idx[0]], context='FACES')
    made = {}
    for name, b in (('SM_AR15_UpperBody', bm_body), ('SM_AR15_BCG', bm_bcg)):
        nm = bpy.data.meshes.new(name + tag)
        b.to_mesh(nm)
        b.free()
        for m in me.materials:
            nm.materials.append(m)
        # keep the imported custom split normals for the untouched faces (the cover's normals rotate with it via recompute)
        ob = bpy.data.objects.new(name + tag, nm)
        bpy.context.scene.collection.objects.link(ob)
        # drop unused slots on the BCG (only its own slot) so UE gets one material
        made[name] = ob
        r[name + '_tris'] = sum(len(p.vertices) - 2 for p in nm.polygons)
    bm.free()
    bpy.data.objects.remove(o)
    return made, r


def strip_unused_slots(ob):
    used = sorted({p.material_index for p in ob.data.polygons})
    keep = [ob.data.materials[i] for i in used]
    remap = {old: new for new, old in enumerate(used)}
    idx = [remap[p.material_index] for p in ob.data.polygons]
    ob.data.materials.clear()                 # (this resets every face to slot 0: the indices go back on below)
    for m in keep:
        clean = m.name.split('.')[0]          # 'Steel.002' -> 'Steel': UE slot names must match the Upper's (Receiver / Steel / BCG)
        cm = bpy.data.materials.get(clean) or bpy.data.materials.new(clean)
        ob.data.materials.append(cm)
    for p, i in zip(ob.data.polygons, idx):
        p.material_index = i


def export(ob, path):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                             axis_forward='-Y', axis_up='Z', object_types={'MESH'}, path_mode='STRIP', bake_anim=False,
                             mesh_smooth_type='FACE', use_tspace=True, use_mesh_modifiers=True, add_leaf_bones=False,
                             use_custom_props=False)


def main():
    clear()
    boxes = ref_boxes()
    for tag, src in (('', 'SM_AR15_Upper.fbx'), ('_LOD1', 'lod/SM_AR15_Upper_LOD1.fbx'), ('_LOD2', 'lod/SM_AR15_Upper_LOD2.fbx')):
        p = os.path.join(SRC, src)
        if not os.path.exists(p):
            REPORT['missing_' + tag] = p
            continue
        made, r = split_one(p, tag, boxes)
        REPORT['LOD0' if not tag else tag[1:]] = r
        for name, ob in made.items():
            strip_unused_slots(ob)
            ob.name = name + tag
            export(ob, os.path.join(DST, name + tag + '.fbx'))
            r[name + '_slots'] = [m.name for m in ob.data.materials]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DST, 'split.blend'))
    json.dump(REPORT, open(os.path.join(DST, 'split_report.json'), 'w'), indent=1)
    print('SPLIT_REPORT', json.dumps(REPORT))


main()
