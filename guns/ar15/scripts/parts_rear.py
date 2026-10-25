"""parts_rear.py - rear group + accessories of the AR-15 kit: carbine buffer tube (receiver extension) with the 6-hole index
rib, castle nut, sling end plate, 6-position M4 stock (waffle sides, sling slot, adjustment latch, steel sling loop),
fold-down rear BUIS, and the 30-round STANAG magazine (a SEPARATE accessory, never merged into the gun meshes).
G-frame millimetres (ar15_spec.py)."""
import math
import numpy as np
import ar15_lib as L
import ar15_spec as SP
from ar15_lib import (prism, lathe, cyl, box, rrect, rect, fillet, union, cut, xf, T, Rx, Ry, Rz, S, bm_join, loft,
                      stadium, rod, lathe_on)
from mathutils import Vector as V

BR = SP.BUFFER_OD / 2.0
STOCK_SHIFT = -SP.STOCK_POS[SP.STOCK_ASSEMBLED]          # G Y offset of the assembled stock (position 3)
LATCH_Y0 = -262.0                                          # latch pin Y at position 0 (collapsed)

# ================================================================================================ buffer tube group
def buffer_tube():
    P = L.Part('SM_AR15_BufferTube', 'Carbine buffer tube (receiver extension)', 'rear', budget=1400)
    t = lathe([(0.0, SP.TOWER_FRONT + 0.5), (BR - 0.6, SP.TOWER_FRONT + 0.5), (BR, SP.TOWER_FRONT), (BR, SP.BUFFER_REAR + 1.2),
               (BR - 1.2, SP.BUFFER_REAR), (0.0, SP.BUFFER_REAR)], 30, 'Y')
    rib = prism(fillet([(-3.3, -BR + 1.0), (3.3, -BR + 1.0), (3.3, -BR - 2.4), (-3.3, -BR - 2.4)], [0, 0, 0.8, 0.8], 2), 'XZ',
                SP.CASTLE[1] - 1.0, SP.BUFFER_REAR + 4.0)
    t = L.union(t, rib)
    holes = [cyl('Z', (0.0, LATCH_Y0 - p), 1.75, -BR - 4.0, -BR + 0.2, 8) for p in SP.STOCK_POS]
    t = L.cut(t, *holes, cyl('Y', (0.0, 0.0), 2.5, SP.BUFFER_REAR - 1.0, SP.BUFFER_REAR + 1.0, 10))     # drain hole in the cap
    P.add(t, 'Receiver', bevel=0.4, segs=1, angle=40.0, sharp=30.0)
    return P

def castle_nut():
    y0, y1 = SP.CASTLE
    P = L.Part('SM_AR15_CastleNut', 'Castle nut + sling end plate', 'rear', budget=1600)
    n = lathe([(BR + 0.1, y0), (SP.CASTLE_OD / 2 - 0.6, y0), (SP.CASTLE_OD / 2, y0 - 0.6), (SP.CASTLE_OD / 2, y1 + 0.8),
               (SP.CASTLE_OD / 2 - 0.8, y1), (BR + 0.1, y1)], 24, 'Y', loop=True)
    notches = [xf(box((-2.6, y1 - 1.0, 12.0), (2.6, y1 + 3.6, 20.0)), Ry(a)) for a in (90.0, 210.0, 330.0)]
    n = L.cut(n, *notches)
    P.add(n, 'Steel', bevel=0.3, segs=1, angle=35.0)
    e0, e1 = SP.ENDPLATE
    plate = prism(fillet([(-18.6, 3.0), (18.6, 3.0), (18.6, -10.0), (8.5, -27.0), (-8.5, -27.0), (-18.6, -10.0)],
                         [6.0, 6.0, 8.0, 4.0, 4.0, 8.0], 4), 'XZ', e1, e0)
    top = cyl('Y', (0.0, 0.0), 18.6, e1, e0, 30)
    plate = L.union(plate, top)
    plate = L.cut(plate, cyl('Y', (0.0, 0.0), BR + 0.1, e1 - 1, e0 + 1, 30),
                  prism(rrect(-6.5, -24.0, 6.5, -18.5, 2.6, 3), 'XZ', e1 - 1, e0 + 1),               # sling slot
                  box((-1.5, e1 - 1, -BR - 4.0), (1.5, e0 + 1, -BR + 0.5)))                         # key notch for the rib
    P.add(plate, 'Steel', bevel=0.3, segs=1, angle=35.0)
    return P

# ================================================================================================ stock
# M4 6-position stock, outline traced from refs/01 (right side, 0.801 mm/px, warped into the G frame on a 10 mm grid with the
# stock collapsed): housing top 18 -> 21.5 over the length, front face Y -213, keel front at Y -246, keel / lever diagonal
# (-298, -36) -> (-328, -61) -> toe (-374, -113), butt face leaning 7.5 mm forward from the top to the toe.
# Collapsed (position 0) coordinates; the part is built there and moved to the assembled position by STOCK_SHIFT.
BUTT_TOP = (-385.0, 21.5)
BUTT_TOE = (-377.5, -113.0)
BUTT_SLOPE = (BUTT_TOP[0] - BUTT_TOE[0]) / (BUTT_TOP[1] - BUTT_TOE[1])      # dY/dZ of the butt-pad face
def butt_y(z): return BUTT_TOE[0] + BUTT_SLOPE * (z - BUTT_TOE[1])
STOCK_BUTT = (butt_y((BUTT_TOP[1] + BUTT_TOE[1]) / 2.0) + STOCK_SHIFT, (BUTT_TOP[1] + BUTT_TOE[1]) / 2.0)   # pad centre, assembled
KEEL = [(-246.6, -36.5), (-298.0, -36.5), (-328.0, -61.0), (-366.0, -104.0), (-372.0, -111.5), (-376.0, -113.0)]

def _keel_bottom(y):
    if y > KEEL[0][0]: return None
    for (y0, z0), (y1, z1) in zip(KEEL, KEEL[1:]):
        if y1 <= y <= y0: return z0 + (z1 - z0) * (y - y0) / (y1 - y0)
    return KEEL[-1][1]

def keel_w(y):
    """keel half width: 11 at its front (Y -246.6), widening into the butt (17)"""
    u = min(1.0, max(0.0, (-246.6 - y) / (-246.6 + 376.0)))
    return 11.0 + 6.0 * u ** 1.6

def stock_section(y):
    """closed (X, Z) outline of the stock at station y: rounded-spine housing (superellipse top), slight draft on the sides,
    then either a rounded housing bottom (front of the keel) or the shoulder stepping in to the narrower keel"""
    F = SP.STOCK_FRONT; t = min(1.0, max(0.0, (F - y) / (F + 378.0)))
    hw = 18.2 + 1.4 * t; ztop = 18.0 + 3.5 * t; h = 12.0; zs = ztop - h; e = 2.6
    right = []
    for k in range(9):                                   # spine: top centre -> side
        a = math.pi / 2 * (1 - k / 8.0)
        right.append((hw * abs(math.cos(a)) ** (2 / e), zs + h * abs(math.sin(a)) ** (2 / e)))
    right.append((hw - 0.3, -19.5))
    zb = _keel_bottom(y)
    if zb is None:                                       # housing only: rounded bottom corner, R 5
        c = (hw - 0.3 - 5.0, -21.0)
        for k in range(1, 7):
            a = -math.pi / 2 * k / 6.0
            right.append((c[0] + 5.0 * math.cos(a), c[1] + 5.0 * math.sin(a)))
        zb = -26.0
    else:                                                # shoulder -> keel side -> rounded keel bottom corner
        wk = min(keel_w(y), hw - 1.2)
        rb = min(3.0, max(0.6, (-27.0 - zb) / 3.0))
        right += [(hw - 0.9, -23.0), (wk + 1.4, -24.8), (wk, -27.0), (wk, zb + rb), (wk - rb * 0.29, zb + rb * 0.29), (wk - rb, zb)]
    right.append((0.0, zb))
    left = [(-x, z) for (x, z) in reversed(right[1:-1])]
    return right + left

def stock():
    sh = STOCK_SHIFT
    P = L.Part('SM_AR15_Stock', '6-position M4 stock', 'rear', bone='stock', pivot=(0.0, SP.STOCK_FRONT + sh, 0.0),
               motion=dict(type='translate', axis=(0, -1, 0), limits=(-SP.STOCK_POS[SP.STOCK_ASSEMBLED], SP.STOCK_POS[-1] - SP.STOCK_POS[SP.STOCK_ASSEMBLED]),
                           rest=0.0, stops={'pos%d' % k: p - SP.STOCK_POS[SP.STOCK_ASSEMBLED] for k, p in enumerate(SP.STOCK_POS)},
                           note='rest = position %d (half extended); collapse toward +Y, extend toward -Y in 16.3 mm clicks' % SP.STOCK_ASSEMBLED),
               budget=6000)
    F = SP.STOCK_FRONT
    ys = [F, F - 0.7, F - 1.8, F - 3.4, -222.0, -236.0, -245.9, -246.6, -262.0, -280.0, -298.0, -313.0, -328.0, -340.0,
          -352.0, -362.0, -368.0, -372.0, -375.0, -376.5]
    rings = []
    for y in ys:
        sec = stock_section(y); s = {F: 0.93, F - 0.7: 0.965, F - 1.8: 0.988}.get(y, 1.0)     # rounded front edge
        rings.append([(x * s, y, z * s + (1 - s) * -4.0) for (x, z) in sec])
    body = loft(rings)
    # butt: the last section run back to the leaning pad face; the rubber pad is the rear 4.6 mm, inset 0.8 mm all round
    # (the step reads as the pad seam) and ribbed across its face
    last = stock_section(-376.5)
    lean = -math.degrees(math.atan(BUTT_SLOPE))                     # Rx(lean) turns the local Y=0 plane into the pad face
    def face_box(y0, y1, zlo=-200.0, zhi=200.0, xh=40.0):
        return xf(box((-xh, y0, zlo), (xh, y1, zhi)), T(0.0, butt_y(0.0), 0.0) @ Rx(lean))
    butt = prism(last, 'XZ', -395.0, -376.0)
    s = L.union(body, butt)
    s = L.cut(s, face_box(-100.0, 4.5))
    zc = -45.0
    inset = [(x * (1.0 - 0.8 / 19.6), zc + (z - zc) * (1.0 - 0.8 / 67.0)) for (x, z) in last]
    pad = L.inter(prism(inset, 'XZ', -398.0, -368.0), face_box(0.0, 4.6))
    s = L.union(s, pad)
    cuts = [cyl('Y', (0.0, 0.0), BR + 0.45, F + 2.0, SP.BUFFER_REAR - 3.0, 36),                 # tube bore
            box((-3.8, F + 2.0, -BR - 3.0), (3.8, SP.BUFFER_REAR - 3.0, -BR + 1.0))]          # index-rib channel
    # side slots: 3 rows x 5 columns of round-ended recesses on each side of the housing (refs/01)
    cols = [(-374.0, -348.0), (-344.0, -317.4), (-314.0, -287.0), (-283.4, -256.0), (-253.0, -225.0)]
    for z in (-3.0, -10.2, -16.8):
        for (ya, yb) in cols:
            slot = stadium(((ya + yb) / 2.0, z), yb - ya, 3.4, 4)
            cuts.append(prism(slot, 'YZ', 16.6, 30.0)); cuts.append(prism(slot, 'YZ', -30.0, -16.6))
    cuts.append(prism(stadium((-352.5, -29.4), 37.0, 6.0, 5), 'YZ', -30.0, 30.0))                 # sling slot
    cuts.append(box((-6.0, -299.0, -40.0), (6.0, -247.4, -34.0)))                                   # lever channel
    # recessed side panels on the keel (0.8 mm), following the keel's diagonal 4.5 mm in from the edge (refs/01 crease)
    for sx in (1, -1):
        rr = []
        for y in np.linspace(-302.0, -366.0, 9):
            wk = keel_w(y); zlo = _keel_bottom(y) + 4.5; zhi = -30.5
            rr.append([(sx * (wk - 0.8), y, zlo), (sx * (wk + 3.0), y, zlo), (sx * (wk + 3.0), y, zhi), (sx * (wk - 0.8), y, zhi)])
        cuts.append(loft(rr))
    # pad ribs across the face, leaning with it
    for k in range(12):
        z = -104.0 + k * 10.4
        cuts.append(xf(box((-30.0, -2.0, -0.45), (30.0, 0.8, 0.45)), T(0.0, butt_y(z), z) @ Rx(lean)))
    s = L.cut(s, *cuts)
    # sling-loop lug under the toe
    lug = prism(fillet([(-366.0, -96.0), (-354.0, -88.0), (-357.5, -101.0), (-362.0, -105.8), (-366.5, -102.0)], [0, 0, 2.0, 3.0, 2.0], 3), 'YZ', -2.6, 2.6)
    s = L.union(s, lug)
    xf(s, T(0.0, sh, 0.0))
    P.add(s, 'Polymer', bevel=0.7, segs=1, angle=35.0, sharp=40.0)
    # adjustment latch lever (polymer) under the tube, with the steel latch pin through it
    lev = fillet([(-250.5, -35.0), (-298.0, -35.0), (-327.0, -59.5), (-334.5, -76.5), (-329.5, -78.2), (-321.0, -66.5),
                  (-300.0, -51.0), (-256.0, -51.0), (-250.5, -46.0)], [1.5, 2.0, 2.5, 2.0, 2.0, 3.0, 4.0, 2.0, 2.0], 3)
    lever = prism(lev, 'YZ', -5.6, 5.6)
    lever = L.cut(lever, *[box((-6.0, y - 0.6, -60.0), (-4.8, y + 0.6, -40.0)) for y in (-318.0, -322.5, -327.0)],
                  *[box((4.8, y - 0.6, -60.0), (6.0, y + 0.6, -40.0)) for y in (-318.0, -322.5, -327.0)])    # finger grooves
    xf(lever, T(0.0, sh, 0.0))
    P.add(lever, 'Polymer', bevel=0.5, segs=1, angle=35.0, sharp=40.0)
    pin = lathe([(0.0, -59.8), (2.3, -59.8), (2.9, -59.2), (2.9, -55.5), (2.4, -55.5), (2.4, -40.0), (0.0, -40.0)], 16, 'Z', (0.0, LATCH_Y0))
    loop = L.lathe([(4.4, -1.1), (6.0, -1.1), (6.0, 1.1), (4.4, 1.1)], 24, 'X', (-360.0, -108.4), loop=True)
    rivet = cyl('X', (-360.0, -102.9), 1.3, -3.4, 3.4, 10)
    lp = bm_join(pin, loop, rivet); xf(lp, T(0.0, sh, 0.0))
    P.add(lp, 'Steel', bevel=0.15, segs=1, angle=35.0)
    return P

# ================================================================================================ rear BUIS (pass 4)
# Polymer flip-up rear sight in the MBUS-3 style, built in parts_sights.py (refs/mbus, no branding).  The aperture drum
# sits on the Aim line; the base runs from 6.4 mm behind the leaf to 33.6 mm in front (the folded leaf lies on it).
import parts_sights as PS
BUIS_HINGE = (PS.REAR_YL, PS.REAR_ZH)  # (Y, Z) of the leaf hinge
BUIS_BASE = (PS.REAR_Y0, PS.REAR_Y1)   # base footprint on the receiver rail (Y range)
BUIS_APERTURE_Y = PS.REAR_YL           # -181.6: the large aperture's plane (Aim socket)

def buis():
    P = L.Part('SM_AR15_BUIS', 'Flip-up rear sight (polymer, MBUS-3 style)', 'rear', bone='buis', pivot=(0.0, *BUIS_HINGE),
               motion=dict(type='rotate', axis=(1, 0, 0), limits=(0.0, 90.0), rest=0.0,
                           note='rest = deployed (large aperture on the sight line); fold = the leaf tips rearward (-Y) over the rail'),
               budget=6400)
    return PS.rear(P)

# ================================================================================================ 30-round STANAG magazine
MAG_MW_C = (SP.MAG_IN_FRONT + SP.MAG_IN_REAR) / 2.0                 # magwell centre Y
MAG_SOCKET = (0.0, MAG_MW_C + SP.MAG_PIVOT_FWD, SP.MAG_TOP_Z)        # G: MagazineSocket = pivot of SM_M4_Mag / SM_AR15_Mag30
MAG_STRAIGHT = 105.0          # straight upper body (refs/01: the curve starts ~107 mm under the feed lips)
MAG_RC = 200.0                # forward curve of the lower third (front edge 13 mm forward at the floorplate, refs/01)
MAG_LEN = 178.0               # body length along the centreline, feed lips to the floorplate

def _mag_path(s):
    """centreline point + unit tangent at arc length s from the top (straight upper body, then the R 200 forward curve)"""
    y0 = MAG_MW_C; z0 = SP.MAG_TOP_Z; S0 = MAG_STRAIGHT; R = MAG_RC
    if s <= S0: return V((0.0, y0, z0 - s)), V((0.0, 0.0, -1.0))
    a = (s - S0) / R
    c = V((0.0, y0 + R, z0 - S0))
    p = c + V((0.0, -R * math.cos(a), -R * math.sin(a)))
    return p, V((0.0, math.sin(a), -math.cos(a)))

def _mag_frame(s):
    p, tng = _mag_path(s); n = V((0.0, -tng.z, tng.y)).normalized(); n = n if n.y > 0 else -n
    return p, tng, n

def magazine():
    P = L.Part('SM_AR15_Mag30', '30-round STANAG magazine (separate accessory)', 'mag', configs=(), bone='magazine',
               pivot=MAG_SOCKET, motion=dict(type='translate', axis=(0, 0, -1), limits=(0.0, 200.0), rest=0.0,
                                             note='seated at rest; drop / insert straight along -Z'), budget=4000)
    L_ = MAG_LEN; W2 = SP.MAG_W / 2.0; D2 = 31.55; MT = SP.MAG_TOP_Z
    def section(s, w2, d2, rf=3.6, rr=2.4):
        p, tng, n = _mag_frame(s)
        prof = fillet([(-d2, -w2), (d2, -w2), (d2, w2), (-d2, w2)], [rr, rf, rf, rr], 3)
        return [tuple(p + n * u + V((v, 0.0, 0.0))) for (u, v) in prof]
    # body: rounder front spine, the bottom 5 mm flared 0.7 mm into the lip that holds the floorplate
    stations = [(s, W2, D2) for s in np.linspace(0.0, L_ - 6.0, 22)] + [(L_ - 4.2, W2 + 0.7, D2 + 0.7), (L_, W2 + 0.7, D2 + 0.7)]
    body = loft([section(s, w, d) for (s, w, d) in stations])
    cuts = [box((-W2 - 1, MAG_MW_C + 4.0, MT - 6.0), (W2 + 1, MAG_MW_C + 40.0, MT + 1.0)),                 # front of the top steps down
            box((-W2 + 1.5, MAG_MW_C - 29.0, MT - 40.0), (W2 - 1.5, MAG_MW_C + 29.5, MT + 1.0)),          # open top
            box((W2 - 1.4, -57.5, MT - 26.0), (W2 + 1.0, -49.0, MT - 18.3))]                               # catch notch (left)
    # stamped panels: a shallow (0.45 mm) pressed recess on each side below the magwell, between the rear spine and the ribs
    for sx in (1, -1):
        rings = []
        for s in np.linspace(68.0, 140.0, 8):
            p, tng, n = _mag_frame(s)
            rings.append([tuple(p + n * u + V((sx * (W2 + a), 0.0, 0.0))) for (u, a) in ((-28.0, -0.5), (-18.0, -0.5), (-18.0, 2.0), (-28.0, 2.0))])
        cuts.append(loft(rings))
    g = L.cut(body, *cuts)
    # pressed reinforcement ribs: three raised strips per side along the body below the magwell, ends run out flush
    ribs = []
    for u in (-14.5, -1.5, 13.0):
        for sx in (1, -1):
            rr = []
            ss = list(np.linspace(64.0, L_ - 13.0, 16))
            for i, s in enumerate(ss):
                p, tng, n = _mag_frame(s); c = p + n * u
                h = 0.62 if 0 < i < len(ss) - 1 else 0.05
                rr.append([tuple(c + n * a + V((sx * (W2 + b), 0, 0))) for (a, b) in ((-1.7, -0.3), (1.7, -0.3), (1.2, h), (-1.2, h))])
            ribs.append(loft(rr))
    g = L.union(g, *ribs)
    P.add(g, 'Receiver', bevel=0.3, segs=1, angle=35.0)
    # feed lips: the wall tops of the rear half curl inward over the follower (cartridge exit tapers open at the front)
    lips = []
    for sx in (1, -1):
        prof = [(sx * (W2 - 0.2), MT - 2.6), (sx * (W2 - 0.2), MT - 0.25), (sx * (W2 - 1.6), MT), (sx * 6.2, MT - 0.7),
                (sx * 5.6, MT - 1.5), (sx * 6.0, MT - 2.6)]
        lip = prism(prof if sx > 0 else prof[::-1], 'XZ', MAG_MW_C - 28.8, MAG_MW_C + 5.0)
        ang = math.degrees(math.atan2(0.947, sx * 0.32))            # cut line from the inner edge (Y -12) to the outer (Y +4)
        ylo, yhi = (0.0, 30.0) if sx > 0 else (-30.0, 0.0)
        lip = L.cut(lip, xf(box((-30.0, ylo, MT - 5.0), (30.0, yhi, MT + 3.0)), T(sx * 5.6, MAG_MW_C - 12.0, 0.0) @ Rz(ang)))
        lips.append(lip)
    P.add(bm_join(*lips), 'Receiver', bevel=0.25, segs=1, angle=35.0)
    # floorplate (steel): rails into the flared lip, front tab 4.5 mm proud and bent down, a pressed oval dimple underneath
    p, tng, n = _mag_frame(L_)
    ring = fillet([(-D2 - 1.6, -W2 - 1.1), (D2 + 4.2, -W2 - 1.1), (D2 + 4.2, W2 + 1.1), (-D2 - 1.6, W2 + 1.1)], [2.0, 3.0, 3.0, 2.0], 3)
    floor = loft([[tuple(p + tng * o + n * u + V((v, 0, 0))) for (u, v) in ring] for o in (-2.2, 2.0)])
    tab = loft([[tuple(p + tng * o + n * u + V((v, 0, 0))) for (u, v) in
                 fillet([(D2 + 1.5, -W2 + 2.0), (D2 + 6.2, -W2 + 2.0), (D2 + 6.2, W2 - 2.0), (D2 + 1.5, W2 - 2.0)], [0, 1.5, 1.5, 0], 2)]
                for o in (-0.2, 3.4)])
    dimple = loft([[tuple(p + tng * o + n * u + V((v, 0, 0))) for (u, v) in stadium((-2.0, 0.0), 26.0, 9.0, 4)] for o in (1.4, 3.0)])
    fp = L.cut(L.union(floor, tab), dimple)
    P.add(fp, 'Steel', bevel=0.3, segs=1, angle=35.0)
    # follower (polymer): body + the raised anti-tilt step on the right + nose.  Pass 3: it sits one round lower, under the
    # top cartridge (SM_AR15_MagRound) that the feed lips hold; with the round hidden it reads as a loaded magazine's stack
    dz = FOLLOWER_DROP
    fol = box((-W2 + 1.8, MAG_MW_C - 28.0, MT - 9.0 - dz), (W2 - 1.8, MAG_MW_C + 28.0, MT - 4.6 - dz))
    step = box((-W2 + 1.8, MAG_MW_C - 28.0, MT - 9.0 - dz), (-1.6, MAG_MW_C + 12.0, MT - 3.2 - dz))
    nose = box((-W2 + 1.8, MAG_MW_C + 20.0, MT - 9.0 - dz), (W2 - 1.8, MAG_MW_C + 28.0, MT - 3.8 - dz))
    P.add(L.union(fol, step, nose), 'Polymer', bevel=0.3, segs=1, angle=35.0)
    return P

# ================================================================================================ top cartridge (pass 3)
FOLLOWER_DROP = 6.0
ROUND_AXIS = (2.4, SP.MAG_TOP_Z - 5.8)      # (X, Z): staggered to the left, under the left feed lip, top 1 mm under the lips
ROUND_BASE_Y = MAG_MW_C - 28.6              # case head against the magazine's rear wall

def mag_round():
    """5.56 x 45 mm cartridge on the follower, held by the feed lips: case (rim, extractor groove, tapered body, 23 deg
    shoulder, neck) and the 62 gr ogive bullet, 57.4 mm overall.  Its own `Brass` slot (the only part that uses it) and
    its own small atlas; it moves with the magazine bone"""
    P = L.Part('SM_AR15_MagRound', '5.56 x 45 mm cartridge (top round in the magazine)', 'mag', configs=(), bone='magazine',
               pivot=MAG_SOCKET, motion=dict(type='translate', axis=(0, 0, -1), limits=(0.0, 200.0), rest=0.0,
                                             note='rides with the magazine; toggle it to show a loaded / empty magazine'), budget=900)
    y = ROUND_BASE_Y
    prof = [(0.0, 0.25), (1.95, 0.25), (2.05, 0.0), (4.45, 0.0), (4.8, 0.35), (4.8, 1.14), (4.3, 1.3), (4.2, 1.5), (4.2, 2.3),
            (4.8, 2.9), (4.78, 4.0), (4.5, 39.6), (3.2, 41.2), (3.2, 44.7), (2.85, 44.7), (2.85, 47.4), (2.72, 50.2), (2.3, 52.8),
            (1.62, 55.1), (0.8, 56.7), (0.0, 57.4)]
    r = lathe([(rr, y + a) for (rr, a) in prof], 20, 'Y', ROUND_AXIS)
    P.add(r, 'Brass', bevel=0.0, segs=1, angle=30.0, sharp=30.0)
    return P

# ================================================================================================ front flip-up sight (pass 4)
def front_buis():
    """flip-up front sight for the M-LOK handguard's top rail (polymer, MBUS-3 style, parts_sights.py); its square post tip
    is on the sight line, so the rear aperture and the post give the Aim line"""
    hg = L.PARTS['SM_AR15_HandguardMLOK']
    # cross bolt in the top-rail slot nearest 368 whose base still ends on the rail (base front = slot + 9.5 mm)
    lug_y = min([c for c in hg.slots['top'] if PS.front_hinge_y(c) + PS.BASE_FRONT <= SP.MLOK_REAR + SP.MLOK_LEN - 0.5], key=lambda c: abs(c - 368.0))
    P = L.Part('SM_AR15_FrontBUIS', 'Flip-up front sight (polymer, MBUS-3 style, M-LOK rail)', 'rear', configs=(),
               pivot=(0.0, PS.front_hinge_y(lug_y), PS.REAR_ZH),
               motion=dict(type='rotate', axis=(1, 0, 0), limits=(0.0, 90.0), rest=0.0,
                           note='rest = deployed (post on the sight line); fold = the leaf tips rearward (-Y) over the rail'),
               budget=5000)
    P.atlas = 'kit'
    return PS.front(P, lug_y)

def build():
    return [L.finalize(f()) for f in (buffer_tube, castle_nut, stock, buis, front_buis, magazine, mag_round)]
