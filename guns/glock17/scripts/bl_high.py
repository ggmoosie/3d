"""bl_high.py - import the SDF high-poly shells (work/high.npz, G mm) into Blender as the five assemblies.
usage: blender -b --factory-startup --python bl_high.py -- [in.npz] [out.blend]
G (x left, y muzzle, z up, mm) -> Blender metres with UE (x,y,z) = Blender (x,-y,z): the Y mirror flips the winding, which is
restored.  Shells keep their per-vertex 'mat' id as a FLOAT point attribute (bakes) and get a preview material."""
import bpy, sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
src = argv[0] if argv else os.path.join(HERE, 'work', 'high.npz')
out = argv[1] if len(argv) > 1 else os.path.join(HERE, 'work', 'G17_V4_High.blend')
ASSEMBLY = {'frame': 'Frame', 'trigger': 'Frame', 'pin0': 'Frame', 'pin1': 'Frame', 'lockblock': 'Frame', 'housing': 'Frame',
            'slidestop': 'Frame', 'takedown': 'Frame', 'magcatch': 'Frame', 'slidestopL': 'Frame',
            'slide': 'Slide', 'rsight': 'Slide', 'fsight': 'Slide', 'plate': 'Slide', 'extractor': 'Slide',
            'barrel': 'Barrel', 'guiderod': 'Barrel', 'backstrap': 'Backstrap',
            'magbody': 'Magazine', 'follower': 'Magazine', 'baseplate': 'Magazine'}
PREVIEW = {0: ((0.03, 0.03, 0.03), 0.65, 0.0), 1: ((0.05, 0.05, 0.05), 0.35, 1.0), 2: ((0.035, 0.035, 0.037), 0.4, 1.0),
           3: ((0.045, 0.045, 0.045), 0.3, 1.0), 4: ((0.8, 0.8, 0.8), 0.5, 0.0), 5: ((0.85, 0.2, 0.02), 0.5, 0.0),
           6: ((0.03, 0.03, 0.03), 0.5, 0.3), 7: ((0.03, 0.03, 0.03), 0.6, 0.0), 8: ((0.04, 0.04, 0.04), 0.35, 1.0),
           9: ((0.025, 0.025, 0.025), 0.55, 0.0)}
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.unit_settings.system = 'METRIC'; sc.unit_settings.scale_length = 1.0
mats = {}
for k, (c, r, m) in PREVIEW.items():
    mt = bpy.data.materials.new('PV_%d' % k); mt.use_nodes = True; b = mt.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*c, 1); b.inputs['Roughness'].default_value = r; b.inputs['Metallic'].default_value = m
    mats[k] = mt
cols = {}
D = np.load(src)
names = sorted({k.split('__')[0] for k in D.files})
for n in names:
    V = D[n + '__V'].astype(np.float64); F = D[n + '__F'].astype(np.int64)
    V = V * np.array([0.001, -0.001, 0.001]); F = F[:, ::-1]                    # mirror Y, keep outward winding
    me = bpy.data.meshes.new('HI_' + n)
    me.vertices.add(len(V)); me.vertices.foreach_set('co', V.ravel())
    me.loops.add(F.size); me.loops.foreach_set('vertex_index', F.ravel())
    me.polygons.add(len(F)); me.polygons.foreach_set('loop_start', np.arange(0, F.size, 3)); me.polygons.foreach_set('loop_total', np.full(len(F), 3))
    me.update(calc_edges=True); me.validate(clean_customdata=False)
    me.polygons.foreach_set('use_smooth', np.ones(len(F), bool))
    mat = D[n + '__a_mat'] if (n + '__a_mat') in D.files else np.zeros(len(V))
    at = me.attributes.new('mat', 'FLOAT', 'POINT'); at.data.foreach_set('value', mat.astype(np.float32))
    mid = int(round(float(np.median(mat)))); me.materials.append(mats.get(mid, mats[0]))
    a = ASSEMBLY.get(n, 'Misc'); c = cols.get(a)
    if c is None:
        c = bpy.data.collections.new('HI_' + a); sc.collection.children.link(c); cols[a] = c
    o = bpy.data.objects.new('HI_' + n, me); c.objects.link(o)
    print('[high]', n, len(V), len(F), a)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('HIGH_SAVED', out)
