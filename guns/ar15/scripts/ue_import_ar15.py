"""ue_import_ar15.py - UE 5.5 editor Python (NOT run by the Blender build; run it in the editor when the kit is imported).

Pass 3: imports the GAME PARTS listed in Tools/bpy/ar15/out/game_parts.json (written by build_ar15.py --assemble):
every mesh FBX with its LOD1 / LOD2, the sockets from its JSON, and the UCX hulls that SM_AR15_Lower carries.  Static-mesh
options follow INTEGRATION.md (import normals, convert scene, no forced front X, uniform scale 1).  Textures are not
imported here: game_parts.json lists, per mesh and slot, the atlas and its packed mask (out/bake/game/<atlas>_Masks.png,
R = AO, G = curvature) and normal map; MATERIALS.md has the master-material recipe.

LEGACY = True also imports the pass-1/2 assembled guns (SM_AR15_MLOK, SM_AR15_M4Quad) and the skeletal SK_AR15_MLOK.
Untested in the editor so far: review DST and run it on a scratch folder first.

    # UE editor > Output Log > Python:  exec(open(r'<repo>/Tools/bpy/ar15/ue_import_ar15.py').read())
"""
import unreal, json, os

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else
                   r'C:/Users/moosi/Documents/Unreal Projects/LootNShoot/Tools/bpy/ar15', 'out')
DST = '/Game/A_Inventory/Weapons/AR15'          # change before running
LEGACY = False

def fbx_task(fbx, dest, skeletal=False, collision=False):
    t = unreal.AssetImportTask(); t.filename = fbx; t.destination_path = dest; t.automated = True; t.save = True; t.replace_existing = True
    o = unreal.FbxImportUI(); o.import_materials = True; o.import_textures = False; o.import_as_skeletal = skeletal
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH
    if skeletal:
        sk = o.skeletal_mesh_import_data
        sk.import_mesh_lo_ds = False; sk.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        sk.convert_scene = True; sk.force_front_x_axis = False; sk.import_uniform_scale = 1.0
    else:
        sm = o.static_mesh_import_data
        sm.combine_meshes = True
        sm.auto_generate_collision = collision              # True only where the FBX carries UCX_ hulls (SM_AR15_Lower)
        sm.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        sm.convert_scene = True; sm.force_front_x_axis = False; sm.import_uniform_scale = 1.0
        sm.remove_degenerates = True; sm.generate_lightmap_u_vs = True
    t.options = o
    return t

def add_sockets(asset_path, json_path):
    sm = unreal.load_asset(asset_path); J = json.load(open(json_path))
    for s in J['sockets']:
        k = sm.find_socket(s['name'])
        if not k:
            k = unreal.StaticMeshSocket(outer=sm); k.set_editor_property('socket_name', s['name']); sm.add_socket(k)
        k.set_editor_property('relative_location', unreal.Vector(*s['loc']))
        p, y, r = s['rot_pyr']; k.set_editor_property('relative_rotation', unreal.Rotator(pitch=p, yaw=y, roll=r))
        k.set_editor_property('relative_scale', unreal.Vector(*s['scale']))
        if s.get('tag'): k.set_editor_property('tag', s['tag'])
    unreal.EditorAssetLibrary.save_loaded_asset(sm)

def import_game():
    J = json.load(open(os.path.join(SRC, 'game_parts.json')))
    dest = DST + '/Parts'
    tasks = [fbx_task(os.path.join(SRC, m['fbx']), dest, collision=bool(m.get('collision'))) for m in J['meshes']]
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for m in J['meshes']:
        path = '%s/%s' % (dest, m['name'])
        add_sockets(path, os.path.join(SRC, m['sockets']))
        sm = unreal.load_asset(path)
        for i, lod in enumerate(m['lods'], start=1):
            unreal.EditorStaticMeshLibrary.import_lod(sm, i, os.path.join(SRC, lod))
        unreal.EditorAssetLibrary.save_loaded_asset(sm)
    print('AR15 game parts imported ->', dest, '| default build:', ', '.join(J['default_build']))

def import_legacy():
    tasks = [fbx_task(os.path.join(SRC, n + '.fbx'), DST, collision=True) for n in ('SM_AR15_MLOK', 'SM_AR15_M4Quad')]
    tasks.append(fbx_task(os.path.join(SRC, 'SK_AR15_MLOK.fbx'), DST + '/Skeletal', skeletal=True))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for n in ('SM_AR15_MLOK', 'SM_AR15_M4Quad'):
        add_sockets('%s/%s' % (DST, n), os.path.join(SRC, 'sockets_%s.json' % n))
        sm = unreal.load_asset('%s/%s' % (DST, n))
        for i in (1, 2):
            unreal.EditorStaticMeshLibrary.import_lod(sm, i, os.path.join(SRC, 'lod', '%s_LOD%d.fbx' % (n, i)))
        unreal.EditorAssetLibrary.save_loaded_asset(sm)
    print('AR15 legacy assembled guns imported ->', DST)

import_game()
if LEGACY: import_legacy()
