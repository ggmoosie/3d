"""parts_sights.py - pass 4: flip-up back-up iron sights in the style of a polymer MBUS 3 (refs/mbus, private reference only:
NO logo, no lettering, no branding is modelled; the maker's-mark spots get a generic moulded stipple in the normal map).

Shared base (refs m01, m03, m04): an M1913 clamp with a recoil lug in a rail slot; round hinge pods at the rear end with the
steel hinge pin; ahead of the hinge the spring housing block (its top slopes down to the front, two lock windows behind,
release buttons on both sides); the cross bolt (hexalobular head on the right, hex nut on the left) through a rail slot.
The leaf stands at the rear end of the base and folds REARWARD over the rail (m03 deployed, m04 stowed).

Rear (m01, m02, m03): a tall polymer U-frame leaf: tapered sides, chamfered ears, a raised rim around recessed panels, rib
grooves on the ears; between the ears the steel windage carrier rides the windage screw and holds the aperture drum (large
4.8 mm aperture on the sight line with an eye-side countersink, the 1.8 mm one bored 90 deg out of line); the big fluted
windage knob with its click-tooth collar on the right, a screw bushing on the left.
Front (m05, m06): the same base; square-topped ears with inner chamfers; the fluted elevation drum in a window under a bridge;
the A2-style 1.5 mm square post on a flared foot.

G-frame millimetres.  Both sights are built deployed; the leaf pieces carry a fold (hinge axis + angle, P.fold) so the
stowed variant is the same mesh with the leaf rotated (ar15_game.fold_copy).

Heights (report): a real MBUS 3 rear puts the aperture 36.1 mm over the rail top; this rifle's sight line (SIGHT_Z, the A2
post height calibrated from refs/01) is 62.5 - 30.4 = 32.1 mm over the rail.  The base (hinge 7.0, block 11.2, stowed
~13.7 mm) keeps the real proportions, so the LEAF is 4.0 mm shorter than the real one; Aim / AimSocket and the front post
tip stay on the old sight line."""
import math
import ar15_lib as L
import ar15_spec as SP
from ar15_lib import (prism, lathe, lathe_on, cyl, box, rrect, fillet, xf, T, bm_join, loft)

RT = SP.RAIL_TOP
AZ = SP.SIGHT_Z
POLY = dict(bevel=0.55, segs=1, angle=35.0, sharp=40.0)          # moulded edges (weighted normals soften the chamfer)
SMALL = dict(bevel=0.3, segs=1, angle=35.0, sharp=40.0)
FLUTED = dict(bevel=0.3, segs=1, angle=70.0, sharp=40.0)          # rims only: flute / tooth corners stay crisp
STEEL = dict(bevel=0.18, segs=1, angle=35.0)

HINGE_DZ = 7.0                   # hinge axis over the rail top (real MBUS 3, refs m03)
POD_R = 4.9                      # hinge pods
BLOCK_TOP = 11.2                 # spring-housing block over the rail top (stowed height ~ this / the folded knob)
BASE_BACK, BASE_FRONT = 5.4, 21.5    # base footprint behind / ahead of the hinge axis
CLAMP_BOT = RT - 5.8             # just above the handguard body top (MLOK_TOP 24.4)

def star(n, r_in, r_out, frac=0.5, flank=0.15, phase=0.0):
    """2-D gear / flute outline: n teeth with flat tops (frac of the pitch at r_out), straight flanks (flank of the
    pitch each) and flat roots"""
    pts = []; w = 2 * math.pi / n
    for k in range(n):
        a0 = phase + w * k
        for t, r in ((0.0, r_in), (flank, r_out), (flank + frac, r_out), (2 * flank + frac, r_in)):
            a = a0 + w * t; pts.append((r * math.cos(a), r * math.sin(a)))
    return pts

def hexagon(r):
    return [(r * math.cos(math.radians(60 * k + 30)), r * math.sin(math.radians(60 * k + 30))) for k in range(6)]

def _rail_env(y0, y1):
    return prism(L.offset2d(L.pic_profile(RT + 0.1, RT - 9.0), 0.15), 'XZ', y0 - 1.0, y1 + 1.0)

def base(P, yh, bolt_y):
    """the shared polymer base (hinge axis at (yh, RT + HINGE_DZ), base from yh - BASE_BACK to yh + BASE_FRONT) + its steel"""
    zh = RT + HINGE_DZ; y0, y1 = yh - BASE_BACK, yh + BASE_FRONT; yb = yh + 4.6; zb = CLAMP_BOT; bz = RT - 1.5
    clamp = prism([(-12.2, zb), (12.2, zb), (12.2, RT + 0.4), (11.6, RT + 1.0), (-11.6, RT + 1.0), (-12.2, RT + 0.4)], 'XZ', y0, y1)
    blk = prism(fillet([(yb, RT + 0.5), (y1, RT + 0.5), (y1, RT + 5.4), (y1 - 3.2, RT + 8.3), (yb + 2.4, RT + BLOCK_TOP), (yb, RT + BLOCK_TOP)],
                       [0.0, 0.0, 1.6, 2.0, 1.6, 0.5], 2), 'YZ', -11.5, 11.5)
    parts = [clamp, blk, box((-6.8, bolt_y - 2.35, RT - 2.9), (6.8, bolt_y + 2.35, RT + 0.6))]          # recoil lug in the slot
    for s in (1.0, -1.0):
        a, b = sorted((s * 7.6, s * 11.9))
        parts += [cyl('X', (yh, zh), POD_R, a, b, 16), box((a, yh - POD_R, RT + 0.5), (b, yh + POD_R, zh))]
    parts.append(cyl('X', (bolt_y, bz), 4.3, -12.85, -12.2, 18))                                     # bolt-head boss (right)
    parts.append(cyl('X', (bolt_y, bz), 4.3, 12.2, 12.85, 18))                                       # nut boss (left)
    body = L.union(*parts)
    nutp = prism(hexagon(3.6), 'YZ', 12.45, 13.5); xf(nutp, T(0.0, bolt_y, bz))
    cuts = [_rail_env(y0, y1),
            cyl('X', (yh, zh), 1.15, -13.0, 13.0, 10),                                                 # hinge-pin bore
            cyl('X', (bolt_y, bz), 1.45, -13.5, 13.5, 8),                                              # cross-bolt bore
            cyl('X', (bolt_y, bz), 3.75, -13.5, -12.45, 18),                                           # head counterbore
            nutp]                                                                                      # hex nut pocket
    for s in (1.0, -1.0):
        a, b = sorted((s * 1.6, s * 4.4))
        cuts.append(box((a, yb + 0.7, RT + BLOCK_TOP - 2.0), (b, yb + 2.5, RT + BLOCK_TOP + 1.0)))        # lock windows (m04)
        a, b = sorted((s * 10.9, s * 12.4))
        cuts.append(box((a, yh + 5.3, RT + 4.9), (b, yh + 11.3, RT + 10.1)))                             # button recess
    P.add(L.cut(body, *cuts), 'Polymer', **POLY)
    btns = []
    for s in (1.0, -1.0):
        a, b = sorted((s * 10.9, s * 12.3))
        bt = prism(fillet([(yh + 5.6, RT + 5.2), (yh + 11.0, RT + 5.2), (yh + 11.0, RT + 9.8), (yh + 5.6, RT + 9.8)], 1.4, 2), 'YZ', a, b)
        g0, g1 = sorted((s * 11.95, s * 12.6))
        btns.append(L.cut(bt, box((g0, yh + 5.0, RT + 6.4), (g1, yh + 11.6, RT + 6.9)), box((g0, yh + 5.0, RT + 8.1), (g1, yh + 11.6, RT + 8.6))))
    P.add(bm_join(*btns), 'Polymer', **SMALL)
    # steel: cross bolt (hexalobular recess, right), hex nut (left) + bolt tip, hinge pin with heads on the pods
    head = lathe([(0.0, -13.75), (3.0, -13.75), (3.55, -13.3), (3.55, -12.45), (0.0, -12.45)], 16, 'X', (bolt_y, bz))
    lobe = prism(star(6, 0.75, 1.35, 0.45), 'YZ', -14.2, -13.0); xf(lobe, T(0.0, bolt_y, bz))
    nut = prism(hexagon(3.3), 'YZ', 12.45, 13.75); xf(nut, T(0.0, bolt_y, bz))
    tip = cyl('X', (bolt_y, bz), 1.4, 13.6, 14.2, 8)
    pin = lathe([(0.0, -12.35), (1.7, -12.35), (1.7, -11.85), (1.15, -11.85), (1.15, 11.85), (1.7, 11.85), (1.7, 12.35), (0.0, 12.35)], 12, 'X', (yh, zh))
    P.add(bm_join(L.cut(head, lobe), nut, tip, pin), 'Steel', **STEEL)
    return zh

def _stipple_base(yh):
    """normal-map-only texture regions (G boxes on |X|, Y, Z + face-normal axis; read by ar15_bake.polymer_bump_shader):
    a 0.2 mm recessed panel with a moulded stipple on the maker's-mark spots - block top (logo) and both block sides ahead
    of the buttons (lettering);
    entries with seam=True are 0.5 mm mould parting lines instead (the leaf flanks, on the leaf mid-plane)"""
    return [dict(ax=(0.0, 6.6), y=(yh + 8.6, yh + 17.0), z=(RT + 7.6, RT + BLOCK_TOP + 0.3), n=2),
            dict(ax=(11.0, 11.8), y=(yh + 12.6, yh + BASE_FRONT - 2.4), z=(RT + 1.6, RT + 7.4), n=0)]

def _taper_x(p0, p1, z):
    (x0, z0), (x1, z1) = p0, p1
    return x0 + (x1 - x0) * (z - z0) / (z1 - z0)

# ================================================================================================ rear
REAR_YL = -181.6                 # leaf mid-plane = hinge axis plane = aperture plane (BUIS_APERTURE_Y)
REAR_ZH = RT + HINGE_DZ
REAR_Y0, REAR_Y1 = REAR_YL - BASE_BACK, REAR_YL + BASE_FRONT
REAR_BOLT_Y = -171.9             # cross bolt through this receiver-rail slot
REAR_T = 4.2                     # leaf half thickness (refs m03: ~8.5 mm)
DRUM_R, DRUM_HL = 3.6, 3.4       # aperture drum radius, half length (axis X)
AP_LARGE, AP_SMALL = 2.4, 0.9    # 4.8 mm and 1.8 mm apertures (0.19 / 0.07 in)
WIND_Z = AZ - 8.5                # windage screw / knob axis (refs m03: knob centre 8.5 mm under the aperture)
REAR_EAR_TOP = AZ + 5.5

def rear(P):
    yh = REAR_YL; T_ = REAR_T
    zh = base(P, yh, REAR_BOLT_Y)
    nb = len(P.pieces)
    lo, hi = (10.6, zh + 5.6), (8.9, REAR_EAR_TOP)                    # outer flank of the leaf (tapered)
    half = [(7.3, zh), (7.3, zh + 5.2), lo, hi, (6.0, REAR_EAR_TOP), (4.9, REAR_EAR_TOP - 1.1), (4.9, AZ - 10.4)]
    outline = half + [(-x, z) for x, z in reversed(half)]
    leaf = L.union(prism(outline, 'XZ', yh - T_, yh + T_), cyl('X', (yh, zh), 4.4, -7.3, 7.3, 16))      # knuckle
    cuts = [prism([(yh - T_ - 1.0, AZ + 1.6), (yh - T_ - 1.0, AZ + 8.0), (yh + 0.8, AZ + 8.0)], 'YZ', -12.0, 12.0),   # top-rear chamfer (m03)
            cyl('X', (yh, zh), 1.15, -12.0, 12.0, 10), cyl('X', (yh, WIND_Z), 1.4, -11.5, 11.5, 10)]
    pk = fillet([(-7.6, zh + 7.0), (7.6, zh + 7.0), (6.9, AZ - 12.4), (-6.9, AZ - 12.4)], 1.0, 2)     # recessed panels
    cuts += [prism(pk, 'XZ', yh - T_ - 1.0, yh - T_ + 1.0), prism(pk, 'XZ', yh + T_ - 1.0, yh + T_ + 1.0)]
    for s in (1.0, -1.0):                                                                          # rib grooves on the ears
        cuts += [box((s * 6.95 - 0.45, yh - T_ - 1.0, AZ - 7.0), (s * 6.95 + 0.45, yh - T_ + 0.7, AZ + 3.4)),
                 box((s * 6.95 - 0.45, yh + T_ - 0.7, AZ - 7.0), (s * 6.95 + 0.45, yh + T_ + 1.0, AZ + 3.4))]
    P.add(L.cut(leaf, *cuts), 'Polymer', **POLY)
    # windage knob (polymer, right side): click-tooth collar against the ear, 22-flute grip, domed cap with an index line
    xw = _taper_x(lo, hi, WIND_Z)
    collar = prism(star(16, 4.5, 5.0, 0.45, 0.2), 'YZ', -(xw + 1.9), -(xw - 0.3)); xf(collar, T(0.0, yh, WIND_Z))
    grip = prism(star(20, 5.75, 6.2, 0.5, 0.15), 'YZ', -(xw + 9.0), -(xw + 1.7)); xf(grip, T(0.0, yh, WIND_Z))
    cap = lathe([(0.0, -(xw + 10.0)), (3.6, -(xw + 10.0)), (5.2, -(xw + 9.7)), (5.9, -(xw + 9.1)), (5.9, -(xw + 8.8)), (0.0, -(xw + 8.8))], 18, 'X', (yh, WIND_Z))
    cap = L.cut(cap, xf(box((-(xw + 10.4), -0.35, -3.4), (-(xw + 9.75), 0.35, 3.4)), T(0.0, yh, WIND_Z)))
    bush = lathe([(0.0, xw - 0.3), (2.6, xw - 0.3), (2.6, xw + 0.8), (2.0, xw + 1.3), (0.0, xw + 1.3)], 12, 'X', (yh, WIND_Z))
    P.add(bm_join(grip, cap), 'Polymer', **FLUTED)
    P.add(collar, 'Polymer', bevel=0.0, sharp=40.0)
    P.add(bush, 'Polymer', **SMALL)
    # steel: windage screw, carrier (block on the screw + fork arms), stub axles, the aperture drum
    screw = cyl('X', (yh, WIND_Z), 1.25, -(xw + 0.5), xw + 0.5, 8)
    fork = prism(fillet([(-4.5, AZ - 10.2), (4.5, AZ - 10.2), (4.5, AZ + 1.4), (3.55, AZ + 1.4), (3.55, AZ - 4.4), (-3.55, AZ - 4.4),
                         (-3.55, AZ + 1.4), (-4.5, AZ + 1.4)], [0, 0, 0.6, 0, 0, 0, 0, 0.6], 2), 'XZ', yh - 2.4, yh + 2.4)
    fork = L.cut(fork, cyl('X', (yh, WIND_Z), 1.35, -6, 6, 8))
    stubs = [cyl('X', (yh, AZ), 0.95, 3.2, 4.75, 8), cyl('X', (yh, AZ), 0.95, -4.75, -3.2, 8)]
    P.add(bm_join(screw, fork, *stubs), 'Steel', **STEEL)
    drum = cyl('X', (yh, AZ), DRUM_R, -DRUM_HL, DRUM_HL, 20)
    big = lathe_on([(0.0, 7.4), (AP_LARGE, 7.4), (AP_LARGE, 1.2), (AP_LARGE + 0.7, 0.0), (AP_LARGE + 0.7, -4.6), (0.0, -4.6)],
                   20, (0.0, yh - 1.4, AZ), (0, 1, 0))                                      # large aperture + eye-side countersink
    drum = L.cut(drum, big, cyl('Z', (0.0, yh), AP_SMALL, AZ - 5, AZ + 5, 10))               # small aperture, 90 deg out of line
    P.add(drum, 'Steel', bevel=0.15, segs=1, angle=30.0)
    P.fold = dict(pieces=list(range(nb, len(P.pieces))), axis_point=(0.0, yh, zh), angle=90.0)      # G: leaf top folds rearward
    P.aim = (0.0, REAR_YL, AZ)
    P.stipple = _stipple_base(yh) + [dict(ax=(4.0, 11.0), y=(yh - 0.25, yh + 0.25), z=(zh + 5.4, REAR_EAR_TOP - 0.4), n=0, seam=True)]
    return P

# ================================================================================================ front
FRONT_T = 3.6
FRONT_EAR_TOP = AZ + 3.0

def front_hinge_y(lug_y):
    return lug_y - 12.0

def front(P, lug_y):
    yh = front_hinge_y(lug_y); T_ = FRONT_T
    zh = base(P, yh, lug_y)
    nb = len(P.pieces)
    half = [(7.3, zh), (7.3, zh + 5.2), (10.2, zh + 5.6), (8.2, FRONT_EAR_TOP), (5.4, FRONT_EAR_TOP), (4.4, FRONT_EAR_TOP - 1.0), (4.4, AZ - 7.4)]
    outline = half + [(-x, z) for x, z in reversed(half)]
    leaf = L.union(prism(outline, 'XZ', yh - T_, yh + T_), cyl('X', (yh, zh), 3.8, -7.3, 7.3, 16))       # knuckle
    cuts = [cyl('X', (yh, zh), 1.15, -12.0, 12.0, 10), cyl('Z', (0.0, yh), 1.15, AZ - 18.5, AZ - 6.0, 10),
            box((-4.6, yh - T_ - 1.0, AZ - 17.6), (4.6, yh + T_ + 1.0, AZ - 9.4))]                  # drum window
    for s in (1.0, -1.0):
        cuts += [box((s * 6.5 - 0.4, yh - T_ - 1.0, AZ - 6.4), (s * 6.5 + 0.4, yh - T_ + 0.6, AZ + 1.6)),
                 box((s * 6.5 - 0.4, yh + T_ - 0.6, AZ - 6.4), (s * 6.5 + 0.4, yh + T_ + 1.0, AZ + 1.6))]
    P.add(L.cut(leaf, *cuts), 'Polymer', **POLY)
    # elevation drum (polymer), axis vertical, 16 flutes, in the window under the bridge
    dr = prism(star(16, 4.0, 4.4, 0.55), 'XY', AZ - 17.2, AZ - 9.8); xf(dr, T(0.0, yh, 0.0))
    dr = L.cut(dr, cyl('Z', (0.0, yh), 1.15, AZ - 19, AZ - 9, 10))
    P.add(dr, 'Polymer', **FLUTED)
    # A2-style square post (1.5 mm) on a flared foot with concave flanks (refs m06), stem down through the bridge into the drum
    rings = []
    for k in range(7):
        t = k / 6.0; z = AZ - 7.4 + 3.6 * t
        hw = 0.75 + 1.35 * (1.0 - math.sin(math.pi / 2 * t)) ** 1.6
        rings.append([(-hw, yh - hw, z), (hw, yh - hw, z), (hw, yh + hw, z), (-hw, yh + hw, z)])
    rings.append([(-0.75, yh - 0.75, AZ), (0.75, yh - 0.75, AZ), (0.75, yh + 0.75, AZ), (-0.75, yh + 0.75, AZ)])
    post = bm_join(loft(rings), cyl('Z', (0.0, yh), 1.05, AZ - 17.0, AZ - 7.3, 10))
    P.add(post, 'Steel', bevel=0.1, segs=1, angle=40.0)
    P.fold = dict(pieces=list(range(nb, len(P.pieces))), axis_point=(0.0, yh, zh), angle=90.0)      # G: leaf top folds rearward
    P.post_tip = (0.0, yh, AZ)
    P.stipple = _stipple_base(yh) + [dict(ax=(4.0, 10.6), y=(yh - 0.25, yh + 0.25), z=(zh + 5.4, FRONT_EAR_TOP - 0.4), n=0, seam=True)]
    return P
