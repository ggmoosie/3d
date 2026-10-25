"""fix_ucx.py - rebuild UCX_SM_G17_Frame_NN as light convex hulls (extreme points along 96 Fibonacci directions, <= ~96 verts)
from the frame LOD0 regions (grip, receiver, dust cover).  usage: blender -b work/G17_V4_Game.blend --python fix_ucx.py"""
import bpy, bmesh, math
import numpy as np
fr = bpy.data.objects['SM_G17_Frame']; co = np.array([v.co[:] for v in fr.data.vertices]); G = co * np.array([1000, -1000, 1000])
regions = {'00': (G[:, 2] < 2.0) & (G[:, 1] < 22.0), '01': (G[:, 2] >= -2.0) & (G[:, 1] < 62.0), '02': (G[:, 1] >= 58.0) & (G[:, 2] > 5.0)}
n = 96; ga = math.pi * (3 - math.sqrt(5)); D = np.array([(math.sqrt(1 - (1 - 2 * (i + .5) / n) ** 2) * math.cos(ga * i), math.sqrt(1 - (1 - 2 * (i + .5) / n) ** 2) * math.sin(ga * i), 1 - 2 * (i + .5) / n) for i in range(n)])
for k, sel in regions.items():
    P = co[sel]; idx = np.unique(np.argmax(P @ D.T, axis=0)); pts = P[idx]
    bm = bmesh.new(); vs = [bm.verts.new(tuple(p)) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    bmesh.ops.delete(bm, geom=list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid}), context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = bpy.data.objects['UCX_SM_G17_Frame_' + k]; bm.to_mesh(o.data); bm.free()
    print('UCX', o.name, 'verts', len(o.data.vertices), 'tris', sum(len(p.vertices) - 2 for p in o.data.polygons))
bpy.ops.wm.save_mainfile()
