"""export.py - FBX export of the G17 v4 game meshes (contract settings) + LODs + sockets JSON, then a clean re-import
(work/G17_V4_Reimport.blend) for the QC gate.  Does NOT touch Unreal.
usage: blender -b work/G17_V4_Game.blend --python export.py"""
import bpy, os, sys, json, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, 'export'); GAME = os.path.join(EXP, 'game'); LOD = os.path.join(EXP, 'lod')
for d in (GAME, LOD): os.makedirs(d, exist_ok=True)
C = json.load(open(os.path.join(HERE, '..', 'v3', 'CONTRACT.json')))
NAMES = ['SM_G17_Frame', 'SM_G17_Slide', 'SM_G17_Barrel', 'SM_G17_Backstrap', 'SM_G17_Magazine']
KW = dict(use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Y', axis_up='Z',
          object_types={'MESH'}, path_mode='STRIP', bake_anim=False, mesh_smooth_type='FACE', use_tspace=True,
          use_mesh_modifiers=True, add_leaf_bones=False, use_custom_props=False)
def export(objs, path):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs:
        o.hide_set(False); o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, **KW); print('EXPORTED', path)
for c in bpy.data.collections: c.hide_viewport = False
for n in NAMES:
    objs = [bpy.data.objects[n]]
    if n == 'SM_G17_Frame': objs += [o for o in bpy.data.objects if o.name.startswith('UCX_SM_G17_Frame_')]
    export(objs, os.path.join(GAME, n + '.fbx'))
    for k in ('LOD1', 'LOD2'):
        export([bpy.data.objects['%s_%s' % (n, k)]], os.path.join(LOD, '%s_%s.fbx' % (n, k)))
# sockets: unchanged contract positions (UE cm, FRotator pitch/yaw/roll)
sock = {n: C['assemblies'][n]['sockets'] for n in NAMES}
json.dump(dict(note='G17 v4 sockets = contract positions, unchanged (v3/CONTRACT.json). See STATUS.md for the three that no longer '
                    'sit on the real geometry (Trigger, Aim z, TacticalSocket) and their measured real positions.', sockets=sock),
          open(os.path.join(EXP, 'G17_sockets.json'), 'w'), indent=1)
# clean re-import for QC
bpy.ops.wm.read_factory_settings(use_empty=True)
for n in NAMES:
    bpy.ops.import_scene.fbx(filepath=os.path.join(GAME, n + '.fbx'), use_custom_normals=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'work', 'G17_V4_Reimport.blend'))
print('REIMPORT', [(o.name, len(o.data.polygons), tuple(round(v, 4) for v in o.dimensions)) for o in bpy.data.objects if o.type == 'MESH'])
