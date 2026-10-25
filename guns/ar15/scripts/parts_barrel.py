"""parts_barrel.py - barrel group of the AR-15 kit: 14.5 in M4A1 (SOCOM) barrel with the M203 cut, barrel nut, low-profile gas
block (M-LOK build), A2 front sight base with post, bayonet lug, swivel and handguard cap (quad-rail build), gas tube,
A2 birdcage, delta-ring assembly (quad-rail build).  G-frame millimetres (ar15_spec.py)."""
import math
import ar15_lib as L
import ar15_spec as SP
from ar15_lib import (prism, lathe, lathe_on, cyl, box, rrect, rect, fillet, union, cut, xf, T, Rx, Ry, Rz, S, about, bm_join,
                      loft, circle, rod)
from mathutils import Vector as V

POST_TIP = SP.SIGHT_Z

# ================================================================================================ barrel
def barrel(name='SM_AR15_Barrel', label='14.5 in M4A1 barrel (M203 cut)', ext=0.0, configs=('MLOK', 'QUAD')):
    """M4 profile barrel.  ext > 0 lengthens the muzzle section (between the M203 cut and the muzzle shoulder): the 16 in
    civilian barrel is the same profile family with ext = 38.1 (pass 3); the gas port and journal stay put, so the A2 FSB
    and the low-profile block fit both"""
    P = L.Part(name, label, 'barrel', configs=configs, budget=2600)
    if not configs: P.atlas = 'kit'
    shoulder = SP.svg_y(1455.6)
    st = [(y + (ext if y >= shoulder - 1e-6 else 0.0), d) for (y, d) in SP.BARREL_PROFILE]
    prof = [(0.0, st[0][0])]
    for i, (y, d) in enumerate(st):
        r = d / 2.0
        if i > 0 and abs(y - st[i - 1][0]) < 1e-6:                      # square step: small chamfer on the larger diameter
            pr = st[i - 1][1] / 2.0; ch = min(0.4, abs(r - pr) * 0.6)
            if r > pr: prof.append((r - ch, y)); prof.append((r, y + ch))
            else: prof[-1] = (pr, y - ch); prof.append((pr - ch, y)); prof.append((r, y))
            continue
        prof.append((r, y))
    end = SP.BARREL_END + ext
    prof[-1] = (st[-1][1] / 2.0, end - 0.5); prof.append((st[-1][1] / 2.0 - 0.5, end)); prof.append((0.0, end))
    b = lathe(prof, 28, 'Y')
    b = L.cut(b, cyl('Y', (0.0, 0.0), 2.85, end - 40.0, end + 1.0, 16),             # bore at the muzzle (crown)
              cyl('Y', (0.0, 0.0), 4.6, SP.BARREL_PROFILE[0][0] - 1.0, SP.BARREL_PROFILE[0][0] + 6.0, 16))   # chamber mouth
    P.add(b, 'Steel', bevel=0.0, segs=1, angle=40.0, sharp=30.0)
    return P

def barrel16():
    return barrel('SM_AR15_Barrel16', '16 in M4-profile barrel (civilian, carbine gas)', SP.BARREL16_EXT, ())

def barrel_nut():
    P = L.Part('SM_AR15_BarrelNut', 'Barrel nut', 'barrel', budget=900)
    n = lathe([(15.9, -0.4), (16.8, -0.4), (16.8, 24.0), (16.0, 27.0), (12.6, 27.0), (12.6, 17.0), (15.9, 17.0)], 24, 'Y', loop=True)
    teeth = [xf(box((-1.6, 18.0, 15.0), (1.6, 28.0, 18.0)), Ry(360.0 / 20 * k + 9.0)) for k in range(20)]
    # (the 20 wrench teeth are hidden under the handguard / delta ring in both builds: omitted)
    P.add(n, 'Steel', bevel=0.3, segs=1, angle=40.0)
    return P

# ================================================================================================ gas block / FSB / tube
def low_profile_gas_block():
    y0, y1 = SP.LPGB
    P = L.Part('SM_AR15_GasBlockLP', 'Low-profile gas block', 'barrel', configs=('MLOK',), budget=1300)
    ring = cyl('Y', (0.0, 0.0), 12.5, y0, y1, 32)
    top = prism(fillet([(-7.0, 0.0), (7.0, 0.0), (7.0, 18.7), (-7.0, 18.7)], [0, 0, 2.2, 2.2], 3), 'XZ', y0, y1)
    g = L.union(ring, top)
    g = L.cut(g, cyl('Y', (0.0, 0.0), 9.55, y0 - 1, y1 + 1, 32),                                   # journal bore
              cyl('Y', (0.0, SP.GAS_Z), 2.45, y0 - 1.0, y0 + 14.0, 14),                           # gas tube socket
              cyl('X', (y0 + 5.0, SP.GAS_Z), 0.9, -10, 10, 8))                                    # roll-pin hole
    for y in (y0 + 11.0, y1 - 4.0):                                     # set screws underneath (clear of the FSB taper pin at y0 - 3 + 8)
        g = L.cut(g, cyl('Z', (0.0, y), 2.6, -15.0, -10.6, 6))
    P.add(g, 'Steel', bevel=0.4, segs=1, angle=35.0)
    return P

def gas_tube():
    P = L.Part('SM_AR15_GasTube', 'Gas tube (carbine)', 'barrel', budget=500)
    t = lathe([(0.0, -41.0), (1.6, -41.0), (2.38, -40.2), (2.38, SP.GAS_PORT_Y + 1.0), (1.8, SP.GAS_PORT_Y + 2.0), (0.0, SP.GAS_PORT_Y + 2.0)],
              14, 'Y', (0.0, SP.GAS_Z))
    P.add(t, 'Steel', bevel=0.0, segs=1, wn=True, sharp=40.0)
    return P

def front_sight_base():
    y0, y1 = SP.FSB
    P = L.Part('SM_AR15_FrontSightBase', 'A2 front sight base + post', 'barrel', configs=('QUAD',), budget=5200)
    # barrel ring with the gas housing on top-rear
    ring = lathe([(0.0, y0), (13.0, y0), (13.8, y0 + 0.8), (13.8, y1 - 0.8), (13.0, y1), (0.0, y1)], 24, 'Y')
    gas = prism(fillet([(-8.0, 4.0), (8.0, 4.0), (8.0, 20.0), (-8.0, 20.0)], [0, 0, 3.0, 3.0], 3), 'XZ', y0, y0 + 28.0)
    # triangular frame (side view), solid across X +-6.6, then a lightening window and the slot between the ears
    tri = prism(fillet([(y0 + 6.0, 9.0), (y1 + 1.6, 9.0), (y1 + 1.6, 15.0), (234.4, 63.6), (231.6, POST_TIP + 2.6), (227.0, POST_TIP + 2.6),
                        (y0 + 6.0, 16.0)], [0, 0, 2.5, 1.5, 1.0, 2.0, 3.0], 2), 'YZ', -6.6, 6.6)
    lug = prism(fillet([(226.0, -9.0), (y1 + 4.5, -9.0), (y1 + 4.5, -23.5), (230.0, -23.5)], [0, 2.0, 1.5, 2.0], 3), 'YZ', -3.2, 3.2)
    base = prism(fillet([(y1 - 30.0, -5.0), (y1 + 1.6, -5.0), (y1 + 1.6, -14.0), (y1 - 30.0, -14.0)], [0, 1.0, 1.0, 3.0], 3), 'YZ', -7.0, 7.0)
    cap = lathe([(17.0, y0 - 4.0), (24.6, y0 - 4.0), (24.6, y0 - 0.8), (24.0, y0 + 0.4), (13.0, y0 + 0.4), (13.0, y0 - 1.0),
                 (21.8, y0 - 1.0), (21.8, y0 - 4.0)], 20, 'Y', loop=True)                          # handguard cap (cup)
    f = L.union(ring, gas, tri, lug, base)
    f = L.cut(f, cyl('Y', (0.0, 0.0), 9.55, y0 - 1, y1 + 1, 24),                                       # journal bore
              prism(fillet([(207.0, 21.0), (229.5, 21.0), (229.5, 44.5), (221.4, 44.5)], [3.0, 2.0, 2.0, 3.5], 3), 'YZ', -10, 10),   # window
              box((-2.9, 222.0, 50.5), (2.9, 240.0, 80.0)),                                             # slot between the ears
              cyl('Y', (0.0, SP.GAS_Z), 2.45, y0 - 2.0, y0 + 14.0, 14),                                 # gas tube socket
              cyl('Z', (0.0, 231.0), 2.1, 44.0, 52.0, 12),                                              # post bore
              box((-1.3, y1 - 0.5, -26), (1.3, y1 + 6.0, -14.5)),                                       # lug relief
              cyl('X', (y1 - 3.0, -11.0), 2.3, -10, 10, 12))                                            # swivel rivet bore
    for y in (y0 + 8.0, y1 - 9.0):                                                                      # taper pins
        f = L.cut(f, cyl('X', (y, -10.4), 1.6, -10, 10, 10))
    P.add(f, 'Steel', bevel=0.45, segs=1, angle=35.0)
    P.add(cap, 'Steel', bevel=0.35, segs=1, angle=35.0)
    # front sight post (A2 square post on a threaded base) + detent, taper pins, swivel
    post = L.union(cyl('Z', (0.0, 231.0), 2.0, 44.5, 52.6, 12), box((-0.95, 230.05, 52.0), (0.95, 231.95, POST_TIP)))
    P.add(post, 'Steel', bevel=0.15, segs=1, angle=40.0)
    pins = bm_join(*[cyl('X', (y, -10.4), 1.6, -13.4, 13.4, 10) for y in (y0 + 8.0, y1 - 9.0)])
    P.add(pins, 'Steel', bevel=0.12, segs=1, angle=40.0)
    sw = L.union(cyl('X', (y1 - 3.0, -11.0), 2.3, -4.8, 4.8, 12), prism(rrect(y1 - 11.0, -28.0, y1 + 5.0, -14.0, 7.0, 4), 'YZ', -0.8, 0.8))
    sw = L.cut(sw, prism(rrect(y1 - 9.4, -26.4, y1 + 3.4, -15.6, 5.4, 4), 'YZ', -2, 2))
    P.add(sw, 'Steel', bevel=0.15, segs=1, angle=40.0)
    return P

def birdcage():
    y0 = SP.THREAD_SHOULDER; y1 = SP.MUZZLE_Y
    P = L.Part('SM_AR15_Birdcage', 'A2 birdcage flash hider', 'barrel', budget=2800)
    b = lathe([(6.4, y0 + 0.6), (10.4, y0 + 0.6), (11.0, y0 + 1.2), (11.0, y1 - 1.0), (10.3, y1), (7.6, y1), (7.0, y1 - 1.5),
               (7.0, SP.BARREL_END + 0.5), (6.4, SP.BARREL_END + 0.5)], 18, 'Y', loop=True)
    cuts = []
    for yc in (y0 + 4.0, y0 + 7.0):                                                   # two rings near the rear
        cuts.append(lathe([(10.6, yc - 0.6), (11.5, yc - 0.6), (11.5, yc + 0.6), (10.6, yc + 0.6)], 18, 'Y', loop=True))
    for a in (0.0, 60.0, -60.0, 120.0, -120.0):                                       # five slots, closed bottom (A2)
        s = prism(rrect(-1.25, y0 + 13.0, 1.25, y1 - 5.5, 1.25, 2), 'XY', 4.0, 14.0)
        xf(s, Ry(a)); cuts.append(s)
    b = L.cut(b, *cuts)
    washer = lathe([(6.5, y0 - 0.2), (9.6, y0 - 0.2), (9.6, y0 + 0.6), (6.5, y0 + 0.6)], 18, 'Y', loop=True)
    P.add(b, 'Steel', bevel=0.3, segs=1, angle=35.0)
    P.add(washer, 'Steel', bevel=0.0, segs=1)
    return P

def delta_ring():
    y0, y1 = SP.DELTA
    P = L.Part('SM_AR15_DeltaRing', 'Delta ring + slip ring (M4 handguard retainer)', 'barrel', configs=('QUAD',), budget=2600)
    d = lathe([(17.2, y0), (21.4, y0), (22.2, y0 + 0.8), (22.2, y0 + 8.0), (24.6, y0 + 10.0), (25.2, y0 + 10.8), (25.2, y1 - 0.8),
               (24.6, y1), (23.2, y1), (23.2, y1 - 6.5), (17.2, y1 - 6.5)], 28, 'Y', loop=True)
    flutes = [xf(box((-1.0, y0 + 11.6, 24.6), (1.0, y1 - 1.6, 26.0)), Ry(360.0 / 14 * k + 6.43)) for k in range(14)]
    d = L.cut(d, *flutes)
    P.add(d, 'Steel', bevel=0.3, segs=1, angle=35.0)
    return P

def build():
    return [L.finalize(f()) for f in (barrel, barrel16, barrel_nut, low_profile_gas_block, gas_tube, front_sight_base, birdcage, delta_ring)]
