"""build_ar15.py - builds the modular AR-15 kit for LootNShoot.  Blender 4.0, headless, reproducible:

    "D:/Blender/blender.exe" -b --factory-startup --python build_ar15.py -- [options]
    (heavy runs go through the CPU slot tool:  bash Tools/jobslots.sh run "D:/Blender/blender.exe" -b ... )

Options
    --stage N        build the parts of milestones 2..N (2 lower, 3 upper, 4 barrel, 5 handguards, 6 rear + mag); default 6
    --preview TAG    EEVEE studio previews + reference overlays of what was built -> out/progress/<TAG>_*.png
    --assemble       milestone 7: UVs, assembled meshes, sockets, collision, bakes, LODs, skeletal, exports, verify
    --final          milestone 8: final renders (needs --assemble in the same run or a previous run's out/ files)
    --nobake         skip the Cycles bakes (faster iteration)
Writes everything under Tools/bpy/ar15/out/ (see Docs/AR15_BUILD.md)."""
import sys, os, json, time, subprocess, math
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import bpy
import numpy as np
import ar15_spec as SP
import ar15_lib as L
import ar15_render as RD
from mathutils import Vector as V

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def opt(name, default=None, cast=str):
    if name in ARGV:
        i = ARGV.index(name)
        if i + 1 < len(ARGV) and not ARGV[i + 1].startswith('--'): return cast(ARGV[i + 1])
        return True
    return default
STAGE = opt('--stage', 6, int)
PREVIEW = opt('--preview', None)
POST = os.path.join(HERE, 'ar15_post.py')

def system_python(*args):
    r = subprocess.run(['python', POST] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode: L.log('post FAILED', r.stderr[-2000:])
    else: L.log(r.stdout.strip())
    return r.returncode == 0

# ------------------------------------------------------------------------------------------------ parts
def build_parts():
    t = time.time()
    import parts_lower; parts_lower.build()
    if STAGE >= 3:
        import parts_upper; parts_upper.build()
    if STAGE >= 4:
        import parts_barrel; parts_barrel.build()
    if STAGE >= 5:
        import parts_handguard; parts_handguard.build()
    if STAGE >= 6:
        import parts_rear; parts_rear.build()
    L.log('built %d parts in %.1fs' % (len(L.PARTS), time.time() - t))
    bad = [n for n, P in L.PARTS.items() if P.info['errs']]
    if bad: L.log('PARTS WITH ERRORS:', ', '.join(bad))

def config_objs(config):
    return [P.obj for P in L.PARTS.values() if config in P.configs and P.obj is not None]

# ------------------------------------------------------------------------------------------------ previews
def preview(tag):
    """progress renders in the FINAL look (pass 2): Cycles, the look-dev slot materials and the same light rig / backdrop as
    the finals (without the baked masks, which only exist after --assemble)"""
    import ar15_final as F
    F.cycles(40, (1600, 900)); RD.look_materials()
    outs = []
    for config in ('MLOK', 'QUAD'):
        objs = config_objs(config)
        if config == 'QUAD' and STAGE < 4: break
        for o in L.PARTS.values():
            if o.obj: o.obj.hide_render = config not in o.configs
        lo, hi = L.world_bounds(objs); radius = float(np.linalg.norm(hi - lo)) / 2
        for view in ('left', 'right', 'front34', 'rear34'):
            c, d = RD.frame(objs, view, (1600, 900), margin=1.04)
            RD.light_rig(d, c, radius); RD.backdrop(RD.R['cam'].location, c, radius)
            p = os.path.join(L.OUT, 'progress', '%s_%s_%s.png' % (tag, config, view)); RD.render(p); outs.append(p)
        RD.clear_rig()
        # ortho side renders at a known scale for the photo overlays
        side, photo = ('left', '11') if config == 'MLOK' else ('right', '01')
        stk = L.PARTS.get('SM_AR15_Stock')            # both reference photos show the stock collapsed: compare like with like
        if stk: stk.obj.location.y -= SP.STOCK_POS[SP.STOCK_ASSEMBLED] * L.MM
        meta = RD.ortho_side(objs, side, 0.55, (-5.0, -40.0), (1600, 720),
                             os.path.join(L.OUT, 'progress', '_%s_%s_ortho.png' % (tag, config)))
        if stk: stk.obj.location.y += SP.STOCK_POS[SP.STOCK_ASSEMBLED] * L.MM
        RD.clear_rig()
        J = dict(overlays=[dict(render=meta['path'], photo=photo, meta=meta, alpha=0.42,
                                out=os.path.join(L.OUT, 'progress', '%s_%s_overlay.png' % (tag, config)),
                                title='%s: %s side over %s at matching scale' % (tag, side, 'refs/11' if photo == '11' else 'refs/01'),
                                ours={})])
        jp = os.path.join(L.OUT, 'progress', '_%s_%s_overlay.json' % (tag, config)); json.dump(J, open(jp, 'w'), indent=1)
        system_python('overlay', jp)
        views = [os.path.join(L.OUT, 'progress', '%s_%s_%s.png' % (tag, config, v)) for v in ('left', 'right', 'front34', 'rear34')]
        system_python('sheet', os.path.join(L.OUT, 'progress', '%s_%s_sheet.png' % (tag, config)),
                      '%s - %s (%d parts, %s tris)' % (tag, config, len(objs), format(sum(L.tri_count(o.data) for o in objs), ',')), *views)
    for o in L.PARTS.values():
        if o.obj: o.obj.hide_render = False
    return outs

def parts_table():
    rows = []
    for n, P in L.PARTS.items():
        rows.append(dict(name=n, label=P.label, group=P.group, slots=P.info['slots'], tris=P.info['tris'], shells=P.info['shells'],
                         errs=P.info['errs'], configs=sorted(P.configs), bone=P.bone))
    json.dump(rows, open(os.path.join(L.OUT, 'parts_table.json'), 'w'), indent=1)
    for cfg in ('MLOK', 'QUAD'):
        L.log('CONFIG %s static LOD0 tris: %d' % (cfg, sum(P.info['tris'] for P in L.PARTS.values() if cfg in P.configs and P.static)))

def main():
    L.reset_scene()
    build_parts()
    parts_table()
    if PREVIEW: preview(PREVIEW)
    if opt('--assemble'):
        import ar15_assemble as A
        guns, lods, sk, exp = A.run(bake=not opt('--nobake'))
        import ar15_game as G                                  # pass 3: the game part split
        game, gsocks, GJ = G.run(bake_maps=not opt('--nobake'))
        if opt('--final'):
            import ar15_final as F; F.run(guns); F.game_renders(GJ)
        master(guns)
        import ar15_verify as VF
        socks = {g['obj'].name: g['sockets'] for g in guns.values()}; socks.update(gsocks)
        VF.verify(os.path.join(L.OUT, '_export_manifest.json'), socks)
    else:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.OUT, '_last_build.blend'))
    L.log('DONE')

def master(guns):
    """AR15_master.blend: the whole kit for a human: parts by group, the two assembled guns, the skeletal variant, LODs,
    the magazine, reference-photo planes at true scale and socket empties"""
    from mathutils import Matrix
    import ar15_render as RD
    ref_planes()
    col = L.coll('AR15_Sockets')
    for g in guns.values():
        sub = L.coll('Sockets_' + g['obj'].name, col)
        for s in g['sockets']:
            e = bpy.data.objects.new('%s.%s' % (g['obj'].name, s['name']), None); e.empty_display_type = 'ARROWS'; e.empty_display_size = 0.012
            X, Y, Z = [V((a[0], -a[1], a[2])) for a in (s['x_axis'], s['y_axis'], s['z_axis'])]
            M = Matrix((X, Y, Z)).transposed().to_4x4(); M.translation = V((s['loc'][0] / 100, -s['loc'][1] / 100, s['loc'][2] / 100))
            e.matrix_world = M; sub.objects.link(e)
    pc = L.coll('AR15_Parts')
    for P in L.PARTS.values():
        if P.obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(P.obj)
        gc = L.coll('Parts_' + P.group, pc)
        if P.obj.name not in gc.objects: gc.objects.link(P.obj)
    RD.look_materials(getattr(RD, 'MASKS', None))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.OUT, 'AR15_master.blend'))
    L.log('saved AR15_master.blend')

def ref_planes():
    """the two calibrated reference photos as image planes at true scale (the left photo on the gun's right of centre, so a
    left-side view sees the model in front of it, and vice versa)"""
    import bmesh
    import ar15_post as PO
    col = L.coll('AR15_RefPlanes')
    for key, x in (('11', -0.09), ('01', 0.09)):
        p = PO.PHOTOS[key]; img = bpy.data.images.load(os.path.join(HERE, 'refs', p['file']), check_existing=True)
        w, h = img.size; a, b = PO.photo_xf(key)
        corners = []
        for (u, v) in ((0, h), (w, h), (w, 0), (0, 0)):
            s = (complex(u, v) - b) / a
            Y = -s.real if p['side'] == 'left' else s.real; Z = -s.imag
            corners.append(L.g2b((0.0, Y, Z)))
        bm = bmesh.new(); vs = [bm.verts.new((x, c.y, c.z)) for c in corners]; f = bm.faces.new(vs)
        uvl = bm.loops.layers.uv.new('UVMap')
        for l, uvc in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): l[uvl].uv = uvc
        me = bpy.data.meshes.new('REF_' + key); bm.to_mesh(me); bm.free()
        m = bpy.data.materials.new('REF_' + key); m.use_nodes = True; nt = m.node_tree
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
        nt.links.new(t.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
        me.materials.append(m)
        o = bpy.data.objects.new('REF_%s_%s' % (key, p['side']), me); col.objects.link(o); o.hide_render = True

if __name__ == '__main__':          # importable (ar15_kit_patch uses master())
    main()
