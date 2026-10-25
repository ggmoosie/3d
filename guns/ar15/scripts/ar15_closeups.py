"""ar15_closeups.py - fixed-camera Cycles close-ups of the areas reworked in pass 2 (lower, upper, stock, magazine), used for
the before/after sheets and as work-in-progress views during part rebuilds.  The cameras are defined in G millimetres, so a
pass-1 blend and a pass-2 blend render from exactly the same viewpoints with the same light rig and look-dev materials.

    "D:/Blender/blender.exe" -b --factory-startup --python ar15_closeups.py -- --blend <file.blend> --tag <tag>
                                [--bake <dir with <gun>_<slot>_{AO,Curv,N}.png>] [--out <dir>] [--only lower,stock] [--samples N]

Without --bake the parts render with the plain look-dev materials (no AO / curvature / normal maps).  Writes
<out>/<tag>_<shot>.png (default out/progress/closeups/).  The sheet: python ar15_post.py beforeafter <dir> <tagA> <tagB>."""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import bpy
from mathutils import Vector as V

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def opt(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV and ARGV.index(name) + 1 < len(ARGV) else default

BLEND = opt('--blend'); TAG = opt('--tag', 'wip')
BAKE = os.path.abspath(opt('--bake')) if opt('--bake') else None
OUTD = os.path.abspath(opt('--out')) if opt('--out') else None
if BLEND: bpy.ops.wm.open_mainfile(filepath=os.path.abspath(BLEND))
import ar15_lib as L
import ar15_render as RD
import ar15_final as F

OUTD = OUTD or os.path.join(L.OUT, 'progress', 'closeups'); os.makedirs(OUTD, exist_ok=True)
ONLY = set(opt('--only', '').split(',')) - {''}; SAMPLES = int(opt('--samples', '64'))
RES = (1200, 900)

MLOK_PARTS = ['LowerReceiver', 'Trigger', 'Hammer', 'Selector', 'MagCatch', 'BoltCatch', 'LowerPins', 'Grip', 'UpperReceiver',
              'DustCover', 'DustCoverRod', 'ForwardAssist', 'ChargingHandle', 'BCG', 'Bolt', 'Barrel', 'BarrelNut', 'GasBlockLP',
              'GasTube', 'Birdcage', 'HandguardMLOK', 'BufferTube', 'CastleNut', 'Stock', 'BUIS']
STOCK_Y = -300.0 - 48.9          # middle of the stock at the assembled position (3)

# shot: (region, objects, target G mm, view direction (Blender, subject -> camera), visible width mm)
SHOTS = [
    ('lower_right',  'lower',    'gun', (0.0, -100.0, -45.0), (-0.93, -0.10, 0.30), 250.0),
    ('lower_left',   'lower',    'gun', (0.0, -100.0, -42.0), (0.93, -0.14, 0.26), 250.0),
    ('upper_right',  'upper',    'gun', (-14.0, -150.0, 6.0), (-0.80, 0.30, 0.42), 150.0),
    ('upper_rear34', 'upper',    'gun', (-12.0, -160.0, 6.0), (-0.72, 0.52, 0.46), 150.0),
    ('stock_left',   'stock',    'gun', (0.0, STOCK_Y, -42.0), (0.88, 0.16, 0.22), 250.0),
    ('stock_rear34', 'stock',    'gun', (0.0, STOCK_Y, -42.0), (-0.52, 0.78, 0.30), 250.0),
    ('mag_right',    'magazine', 'mag', None, (-1.0, -0.12, 0.10), 285.0),
    ('mag_top34',    'magazine', 'mag', (0.0, -44.0, -50.0), (-0.52, -0.42, 0.74), 230.0),
    ('hg_front34',   'handguard', 'gun', (0.0, 230.0, 0.0), (0.62, -0.30, 0.40), 300.0),
    ('hg_rear34',    'handguard', 'gun', (-5.0, 15.0, 8.0), (-0.70, 0.25, 0.55), 150.0),
    ('hg_pockets',   'handguard', 'gun', (0.0, 150.0, 10.0), (0.62, -0.25, 0.48), 150.0),
    ('mag_lips',     'magazine', 'mag', (0.0, -44.0, -16.0), (-0.42, -0.38, 0.82), 100.0),
    ('trig_right',   'trigger',  'gun', (0.0, -110.0, -56.0), (-0.96, -0.06, 0.16), 105.0),       # pass 4b: trigger fix
    ('trig_left',    'trigger',  'gun', (0.0, -110.0, -56.0), (0.96, -0.08, 0.14), 105.0),
    ('trig_below34', 'trigger',  'gun', (0.0, -110.0, -60.0), (-0.55, -0.35, -0.62), 120.0),
]

def objs_for(kind):
    names = ['SM_AR15_Mag30', 'SM_AR15_MagRound'] if kind == 'mag' else ['SM_AR15_' + n for n in MLOK_PARTS]
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]

def materials():
    """look-dev materials on the five slot materials; with a bake dir, per-gun copies carrying the SM_AR15_MLOK masks (the
    MLOK parts share their UVs with the assembled MLOK gun) and the magazine's own masks"""
    RD.look_materials(None)
    if not BAKE: return {}, {}
    def masks(prefix):
        out = {}
        for slot in ('Receiver', 'Steel', 'BCG', 'Polymer', 'Handguard', 'Brass'):
            d = {}
            for tag, key in (('AO', 'ao'), ('Curv', 'curv'), ('N', 'normal')):
                p = os.path.join(BAKE, '%s_%s_%s.png' % (prefix, slot, tag))
                if os.path.exists(p): d[key] = p
            if d: out[slot] = d
        return out
    sets = []
    for prefix, suffix in (('SM_AR15_MLOK', 'gun'), ('SM_AR15_Mag30', 'mag')):
        mk = masks(prefix)
        if suffix == 'mag': mk.update(masks('SM_AR15_MagRound'))
        RD.look_materials(mk); m = {}
        for slot in ('Receiver', 'Steel', 'BCG', 'Polymer', 'Handguard', 'Brass'):
            c = L.slot_mat(slot).copy(); c.name = '%s__cu_%s' % (slot, suffix); m[slot] = c
        sets.append(m)
    RD.look_materials(None)
    return sets[0], sets[1]

def frame_at(target_b, d, width_mm, lens=85.0):
    cam = RD.R['cam']; cd = cam.data; d = V(d).normalized()
    cd.type = 'PERSP'; cd.lens = lens; cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0
    dist = (width_mm * L.MM / 2.0) / (18.0 / lens)
    cam.location = target_b + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cd.clip_start = 0.005; cd.clip_end = 100.0
    return dist

def main():
    sc = F.cycles(SAMPLES, RES)
    gun_m, mag_m = materials()
    for name, region, kind, tgt, d, width in SHOTS:
        if ONLY and region not in ONLY and name not in ONLY: continue
        objs = objs_for(kind)
        if not objs: L.log('closeup %s: no objects' % name); continue
        for o in bpy.data.objects:
            if o.type == 'MESH': o.hide_render = o not in objs
        saved = F.assign(objs, mag_m if kind == 'mag' else gun_m) if gun_m else []
        if tgt is None:
            lo, hi = L.world_bounds(objs); t = V(((lo + hi) * 0.5).tolist())
        else:
            t = L.g2b(tgt)
        frame_at(t, d, width)
        RD.light_rig(V(d).normalized(), t, 0.15); RD.backdrop(RD.R['cam'].location, t, 0.25)
        p = os.path.join(OUTD, '%s_%s.png' % (TAG, name)); RD.render(p, RES); RD.clear_rig()
        F.restore(saved)
        L.log('closeup %s' % p)
    L.log('CLOSEUPS DONE')

main()
