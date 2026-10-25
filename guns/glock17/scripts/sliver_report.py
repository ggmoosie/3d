"""sliver_report.py - classify mesh_qc's long sliver triangles (< 1 deg, longest edge > 2 mm) on the game meshes:
how many lie on flat ground (all neighbours within 3 deg: no shading effect), how many run ALONG a straight rounded
edge (the needle's long axis parallel to the crease: the normal varies across, not along, it), and how many are neither
(the 'spike' kind that needs fixing).  usage: blender -b <blend> --python sliver_report.py"""
import bpy, bmesh, math, json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); out = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.name.startswith('SM_G17_') or '_LOD' in o.name: continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.normal_update(); bm.faces.ensure_lookup_table()
    flat = along = spike = 0; spikes = []; SH = []
    for f in bm.faces:
        if len(f.verts) != 3: continue
        vs = [v.co for v in f.verts]; ang = []
        for i in range(3):
            u, w = vs[(i + 1) % 3] - vs[i], vs[(i + 2) % 3] - vs[i]
            if u.length > 0 and w.length > 0: ang.append(u.angle(w))
        L = [(vs[1] - vs[0]), (vs[2] - vs[1]), (vs[0] - vs[2])]; lmax = max(e.length for e in L) * 1000
        if not ang or min(ang) >= math.radians(1.0) or lmax <= 2.0: continue
        dih = [f.normal.angle(g.normal, 0.0) for e in f.edges for g in e.link_faces if g is not f]
        if max(dih) < math.radians(3.0): flat += 1; continue
        axis = max(L, key=lambda e: e.length).normalized()
        # neighbour normals change perpendicular to the needle -> it follows a straight rounded edge
        nvar = [abs((g.normal - f.normal).dot(axis)) for e in f.edges for g in e.link_faces if g is not f]
        short = min(e.length for e in L) * 1000; SH.append(short)
        if nvar and max(nvar) < 0.035: along += 1
        else: spike += 1; spikes.append([round(c * 1000, 1) for c in f.calc_center_median()])
    out[o.name] = dict(flat=flat, along_edge=along, other=spike, other_where_mm=spikes[:12])
    print('SLIVERS %-18s flat %4d  along-edge %4d  other %4d   short-edge mm p50 %.3f p90 %.3f max %.3f' % (o.name, flat, along, spike, *(np.percentile(SH, [50, 90, 100]) if SH else (0, 0, 0)))); bm.free()
json.dump(out, open(os.path.join(HERE, 'work', 'sliver_report.json'), 'w'), indent=1)
