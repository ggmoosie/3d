"""parts_upper.py - upper group of the AR-15 kit: M4 flat-top upper receiver (1913 rail, forward-assist housing, brass
deflector, ejection port + recess, hinge lugs), dust cover, dust-cover rod + spring, forward-assist plunger, charging handle,
bolt carrier group (carrier with gas key + cam pin, bolt).  G-frame millimetres (ar15_spec.py)."""
import math
import ar15_lib as L
import ar15_spec as SP
from ar15_lib import (prism, lathe, lathe_on, cyl, box, rrect, rect, fillet, union, cut, xf, T, Rx, Ry, Rz, S, about, bm_join,
                      mirror_x, loft, circle, rod, helix)
from mathutils import Vector as V, Matrix

RT = SP.RAIL_TOP
BODY_TOP = 23.5
HW = 14.6               # upper half width at the bore level
PORT = (-100.0, -20.0, -5.5, 14.0)          # Y0, Y1, Z0, Z1 (right side, -X)
ROD = (-15.0, -7.0)                         # dust cover hinge rod (X, Z), along Y
FA_REAR = V((-16.5, -192.0, 5.5)); FA_FRONT = V((-11.8, -140.0, 5.5))
FA_DIR = (FA_FRONT - FA_REAR).normalized()
CH_CHAN = (6.2, 12.4, 22.0)                 # half width, Z bottom, Z top of the charging-handle channel
BORE_R = 12.85
CARRIER_R = 12.45
CARRIER = (-183.0, -12.0)
KEY = (-84.0, -38.0)          # gas key base rear / nose front (the carbine tube reaches 38 mm into the upper)
CAM_Y = -31.0

def body_section():
    """(X, Z) section of the upper body (full width), without the rail head.  Pass 3 (refs/07, 08): the side wall steps in
    1.3 mm at Z 18-19.4, then a 45 deg chamfer band runs up to the rail-base flat, instead of one long bevel"""
    half = [(0.0, BODY_TOP), (11.4, BODY_TOP), (13.3, 21.6), (13.3, 19.4), (HW, 18.1), (HW, -3.0), (HW - 0.6, -4.5),
            (HW - 0.6, SP.PARTING)]
    hrad = [0.0, 0.9, 0.6, 0.5, 0.8, 0.6, 0.6, 0.0]
    full = half + [(-x, z) for (x, z) in reversed(half)]
    rad = hrad + list(reversed(hrad))
    keep = [i for i in range(len(full)) if i == 0 or full[i] != full[i - 1]]
    full = [full[i] for i in keep][1:]; rad = [rad[i] for i in keep][1:]      # drop the duplicated (0, BODY_TOP)
    return fillet(full, rad, 3)

def shark_fin(sgn):
    """rear transition (pass 3): a fin-shaped boss 0.9 mm proud on each side of the upper's rear, rising from the side wall
    toward the rail at the rear face, with a concave leading edge"""
    import numpy as np
    A, B, C = np.array((SP.UPPER_REAR, 20.6)), np.array((-168.0, 6.0)), np.array((-186.0, 9.0))
    edge = [tuple((1 - t) ** 2 * A + 2 * t * (1 - t) * C + t * t * B) for t in np.linspace(0.0, 1.0, 8)]
    prof = fillet([(SP.UPPER_REAR, 6.0)] + edge, [0.0] + [0.0] * 7 + [0.0], 3)
    a, b = sorted((sgn * (HW - 1.8), sgn * (HW + 0.9)))
    return prism(prof, 'YZ', a, b)

FA_R = 7.8              # forward-assist housing radius (round A2 plunger cap r 6.3 inside it)
FA_KNOB_A = -6.6        # plunger-cap face, mm along FA_DIR from FA_REAR (the ForwardAssist socket)
FA_HOUSING_A = 1.7      # housing rear face (y -190.3, just in front of the lower's tower ring)

def fa_housing():
    """forward-assist housing: a true cylinder (r 7.8) on the FA axis, which converges into the receiver (5 deg), joined to
    the flank by flat tangent facets above and below (refs/07 right upper, refs/01).  Its front end turns into the body over
    the last 9 mm, under the brass-deflector bump.  Sections = convex hull of the housing circle and the body side, resampled
    by rays from a fixed centre so ring vertices correspond station to station."""
    from mathutils.geometry import convex_hull_2d
    rings = []; M = 44
    y0 = FA_REAR.y + FA_DIR.y * FA_HOUSING_A
    ys = [y0, y0 + 0.75, -186.0, -178.0, -168.0, -158.0, -148.0, -141.0, -137.0, -134.0, -131.0, -128.5]
    for y in ys:
        u = (y - FA_REAR.y) / FA_DIR.y                                            # distance along the axis
        c = FA_REAR + FA_DIR * u
        r = FA_R - (0.75 if y < y0 + 0.1 else 0.0)                                # rear-face chamfer
        cx = c.x + max(0.0, (y + 137.0) / 8.5) ** 1.4 * 7.0                       # front end sweeps into the body
        pts = [(cx + r * math.cos(2 * math.pi * j / 48), c.z + r * math.sin(2 * math.pi * j / 48)) for j in range(48)]
        pts += [(-11.5, 17.5), (-12.0, -8.4)]                                     # lower facet runs down as a web
        hull = [pts[i] for i in convex_hull_2d(pts)]
        import parts_lower as PL
        rings.append(PL.ray_ring(hull, V((-10.0, 6.0)), M, y))
    return loft(rings)

def deflector():
    """brass deflector: the forged bump behind the ejection port - intersection of its side outline (scooped, concave
    front face leaning back toward the rail), its plan outline (rising out of the flank, deepest just behind the port)
    and its end-view outline (rounded outer corners)"""
    import numpy as np
    A, B, C = np.array((-118.0, 21.8)), np.array((-103.2, 3.2)), np.array((-113.5, 9.0))
    face = [tuple((1 - t) ** 2 * A + 2 * t * (1 - t) * C + t * t * B) for t in np.linspace(0.0, 1.0, 9)]
    side = fillet([(-134.0, 21.8)] + face + [(-104.5, 0.6), (-134.0, 0.6)], [0] + [0] * 9 + [1.5, 0], 3)
    sideP = prism(side, 'YZ', -24.0, -10.0)
    plan = fillet([(-11.0, -134.0), (-15.5, -130.5), (-19.2, -122.0), (-20.7, -112.0), (-20.6, -105.5), (-19.0, -101.5),
                   (-11.0, -101.5)], [0, 4.0, 8.0, 6.0, 3.0, 1.0, 0], 3)
    planP = prism(plan, 'XY', -2.0, 25.0)
    endv = fillet([(-11.0, 0.0), (-21.5, 0.0), (-21.5, 23.0), (-11.0, 23.0)], [0, 4.5, 7.5, 0], 4)
    endP = prism(endv, 'XZ', -140.0, -95.0)
    return L.inter(L.inter(sideP, planP), endP)

# ================================================================================================ upper receiver
def upper_receiver():
    P = L.Part('SM_AR15_UpperReceiver', 'Flat-top upper receiver', 'upper', budget=11000)
    body = prism(body_section(), 'XZ', SP.UPPER_REAR, SP.UPPER_FRONT)
    ring = cyl('Y', (0.0, 0.0), SP.RING_OD / 2, -1.0, SP.RING_LEN, 40)
    # 1913 rail: head prism + slot cutters
    first, n = L.rail_slots_fit(-188.0, -1.0, 2.6)
    head, slot_cuts, centres = L.pic_rail(-188.0, -1.0, RT, BODY_TOP - 0.6, first, n)
    P.rail_slots = centres
    # pivot + takedown lugs hanging below the parting line
    lugs = []
    for (y0, y1, yp) in ((-10.2, 0.4, SP.PIVOT_Y), (-175.6, -164.0, SP.TAKEDOWN_Y)):
        prof = fillet([(y1, SP.PARTING + 1.0), (y1, SP.PIN_Z - 2.0), (yp, SP.PIN_Z - 6.4), (y0, SP.PIN_Z - 2.0), (y0, SP.PARTING + 1.0)],
                      [0, 4.0, 6.0, 4.0, 0], 4)
        lugs.append(prism(prof, 'YZ', -6.15, 6.15))
    # forward-assist housing (cylinder + tangent facets) and the brass-deflector bump in front of it
    fa = fa_housing()
    defl = deflector()
    # dust-cover hinge lugs (rear, front)
    hinge = [cyl('Y', ROD, 2.3, -105.0, -102.4, 16), cyl('Y', ROD, 2.3, -17.6, -14.6, 16)]
    hinge_web = [box((-15.0, -105.0, -9.3), (-13.0, -102.4, -4.0)), box((-15.0, -17.6, -9.3), (-13.0, -14.6, -4.0))]
    rail = L.cut(head, *slot_cuts)
    # pass 3: raised ejection-port surround (0.7 mm, open along the hinge), the rear shark-fin transitions
    y0, y1, z0, z1 = PORT
    surround = prism(rrect(y0 - 5.2, -4.0, y1 + 5.2, z1 + 3.6, 6.0, 3), 'YZ', -HW - 0.7, -HW + 0.4)
    fins = [shark_fin(1.0), shark_fin(-1.0)]
    solid = L.union(body, ring, fa, defl, surround, *fins, *lugs, *hinge, *hinge_web)
    cuts = []
    cuts.append(cyl('Y', (0.0, 0.0), BORE_R, SP.UPPER_REAR - 5.0, SP.RING_LEN + 2.0, 40))                     # BCG bore
    cuts.append(box((-CH_CHAN[0], SP.UPPER_REAR - 5.0, CH_CHAN[1]), (CH_CHAN[0], -9.0, CH_CHAN[2])))           # charging handle channel
    cuts.append(cyl('Y', (0.0, SP.GAS_Z), 2.75, -12.0, 2.0, 16))                                             # gas tube hole
    y0, y1, z0, z1 = PORT
    cuts.append(prism(rrect(y0, z0, y1, z1, 4.0, 3), 'YZ', -30.0, -5.0))                                     # ejection port
    cuts.append(prism(rrect(y0 - 2.4, ROD[1] + 0.2, y1 + 2.4, z1 + 2.4, 5.0, 3), 'YZ', -30.0, -HW + 1.0))      # cover recess
    cuts.append(lathe_on([(4.7, -5.0), (4.7, 40.0)], 24, tuple(FA_REAR), FA_DIR))                             # FA bore
    cuts.append(lathe_on([(6.65, -2.0), (6.65, FA_HOUSING_A + 5.0)], 32, tuple(FA_REAR), FA_DIR))           # cap counterbore
    for yp in (SP.PIVOT_Y, SP.TAKEDOWN_Y):
        cuts.append(cyl('X', (yp, SP.PIN_Z), SP.PIN_D / 2 + 0.1, -8.0, 8.0, 20))
    cuts.append(cyl('Y', ROD, 1.05, -108.0, -11.0, 10))                                                      # rod bore
    cuts.append(box((6.0, SP.UPPER_REAR - 2.0, 18.5), (12.5, SP.UPPER_REAR + 4.0, 22.0)))                     # CH latch catch (left)
    solid = L.cut(solid, *cuts)
    P.add(solid, 'Receiver', bevel=0.5, segs=1, angle=35.0)
    P.add(rail, 'Receiver', bevel=0.0, segs=1, angle=35.0, sharp=35.0)
    return P

# ================================================================================================ dust cover + rod
def dust_cover():
    P = L.Part('SM_AR15_DustCover', 'Ejection port cover', 'upper', bone='dust_cover', pivot=(ROD[0], -60.0, ROD[1]),
               motion=dict(type='rotate', axis=(0, 1, 0), limits=(-112.0, 0.0), rest=0.0,
                           note='open: the cover swings down and out about the hinge rod (+Y axis); spring-loaded open'), budget=1300)
    y0, y1, z0, z1 = PORT
    plate = prism(rrect(y0 - 2.1, ROD[1] + 1.2, y1 + 2.1, z1 + 2.0, 4.6, 3), 'YZ', -HW - 0.25, -HW + 0.95)
    rib = prism(rrect(-92.0, 1.0, -28.0, 8.5, 1.5, 2), 'YZ', -HW - 0.85, -HW)
    latch = prism(rrect(-63.5, z1 - 4.0, -56.5, z1 - 1.0, 0.8, 2), 'YZ', -HW + 0.5, -HW + 3.0)                 # lock lug inside
    knuckles = [cyl('Y', ROD, 1.9, -101.8, -88.0, 14), cyl('Y', ROD, 1.9, -66.0, -54.0, 14), cyl('Y', ROD, 1.9, -32.0, -18.2, 14)]
    straps = [box((ROD[0] - 0.6, a, ROD[1]), (-HW + 0.95, b, ROD[1] + 2.4)) for (a, b) in ((-101.8, -88.0), (-66.0, -54.0), (-32.0, -18.2))]
    d = L.union(plate, rib, latch, *knuckles, *straps)
    d = L.cut(d, cyl('Y', ROD, 1.1, -110, -10, 10))
    P.add(d, 'Steel', bevel=0.25, segs=1, angle=35.0)
    return P

def dust_cover_rod():
    P = L.Part('SM_AR15_DustCoverRod', 'Dust-cover rod + spring', 'upper', budget=1500)
    r = rod((ROD[0], -104.6, ROD[1]), (ROD[0], -14.8, ROD[1]), 1.0, 8)
    clip = cyl('Y', ROD, 1.35, -14.8, -14.0, 10)
    spring = helix((ROD[0], -87.5, ROD[1]), (0, 1, 0), 1.55, 0.36, 8.0, 21.0, 7, 4)
    P.add(bm_join(r, clip), 'Steel', bevel=0.1, segs=1, angle=40.0)
    P.add(spring, 'Steel', bevel=0.0, wn=False)
    return P

# ================================================================================================ forward assist
def forward_assist():
    P = L.Part('SM_AR15_ForwardAssist', 'Forward-assist plunger', 'upper', bone='forward_assist', pivot=tuple(FA_REAR),
               motion=dict(type='translate', axis=tuple(round(c, 4) for c in FA_DIR), limits=(0.0, 5.0), rest=0.0,
                           note='press: the cap moves forward along the housing axis into the housing counterbore'), budget=1300)
    # round A2 plunger cap: domed face, serrated rim (12 flutes), on the plunger shaft
    k = lathe([(0.0, FA_KNOB_A), (2.5, FA_KNOB_A + 0.15), (4.6, FA_KNOB_A + 0.55), (5.7, FA_KNOB_A + 1.1), (6.3, FA_KNOB_A + 1.9),
               (6.3, 0.2), (5.6, 0.9), (4.55, 0.9), (4.55, 22.0), (0.0, 22.0)], 24, 'Z')
    flutes = [xf(box((5.6, -0.6, FA_KNOB_A + 2.3), (7.5, 0.6, 0.0)), Rz(360.0 / 12 * j + 360.0 / 48)) for j in range(12)]
    k = L.cut(k, *flutes)
    q = V((0, 0, 1)).rotation_difference(FA_DIR).to_matrix().to_4x4()
    xf(k, T(*FA_REAR) @ q)
    P.add(k, 'Steel', bevel=0.2, segs=1, angle=35.0)
    return P

# ================================================================================================ charging handle
def charging_handle():
    P = L.Part('SM_AR15_ChargingHandle', 'Charging handle', 'upper', bone='charging_handle', pivot=(0.0, SP.UPPER_REAR - 6.3, 20.0),
               motion=dict(type='translate', axis=(0, -1, 0), limits=(0.0, 80.0), rest=0.0, note='pull: rearward along -Y'),
               budget=1600)
    R0 = SP.UPPER_REAR - 0.3
    tee = prism(fillet([(-22.5, R0), (22.5, R0), (22.5, R0 - 6.6), (16.5, R0 - 12.6), (-16.5, R0 - 12.6), (-22.5, R0 - 6.6)],
                       [1.0, 1.0, 3.0, 4.0, 4.0, 3.0], 3), 'XY', 13.6, 26.4)
    tee = L.cut(tee, prism(fillet([(-30, R0 - 3.0), (-6.5, R0 - 3.0), (-6.5, R0 - 20.0), (-30, R0 - 20.0)], [0, 2.0, 0, 0], 3), 'XY', 13.0, 18.2),
                prism(fillet([(30, R0 - 3.0), (6.5, R0 - 3.0), (6.5, R0 - 20.0), (30, R0 - 20.0)], [0, 2.0, 0, 0], 3), 'XY', 13.0, 18.2))
    latch = prism(fillet([(5.2, R0 + 1.6), (20.5, R0 - 0.4), (21.5, R0 - 5.5), (5.2, R0 - 5.5)], [0.6, 2.0, 1.5, 0.6], 3), 'XY', 26.2, 28.6)
    shaft = box((-CH_CHAN[0] + 0.3, R0 - 1.0, CH_CHAN[1] + 0.3), (CH_CHAN[0] - 0.3, -26.0, CH_CHAN[2] - 0.4))
    c = L.union(tee, latch, shaft)
    c = L.cut(c, box((-4.9, R0 + 1.0, CH_CHAN[1] - 1.0), (4.9, -30.5, CH_CHAN[2] - 2.2)),          # key channel, open below
              cyl('Y', (0.0, SP.GAS_Z), 2.7, -32.0, -24.0, 14))                                     # gas tube passes the front hook
    P.add(c, 'Receiver', bevel=0.35, segs=1, angle=35.0)
    return P

# ================================================================================================ bolt carrier group
def bcg():
    P = L.Part('SM_AR15_BCG', 'Bolt carrier group (carrier, bolt, cam pin, gas key)', 'upper', bone='bcg', pivot=(0.0, CARRIER[1], 0.0),
               motion=dict(type='translate', axis=(0, -1, 0), limits=(0.0, 82.0), rest=0.0,
                           note='cycle / charge: rearward along -Y (carbine stroke); child bone `bolt` rotates 22.5 deg about +Y to unlock'),
               budget=6000)
    r0, r1 = CARRIER
    carrier = lathe([(0.0, r0), (CARRIER_R - 1.2, r0), (CARRIER_R, r0 + 1.2), (CARRIER_R, r1 - 1.0), (CARRIER_R - 1.0, r1), (0.0, r1)], 20, 'Y')
    key = prism(fillet([(-4.6, KEY[0]), (4.6, KEY[0]), (4.6, KEY[1] - 6.0), (-4.6, KEY[1] - 6.0)], [1.0, 1.0, 0, 0], 3), 'XY', 10.5, 19.6)
    nose = cyl('Y', (0.0, SP.GAS_Z), 3.7, KEY[1] - 6.5, KEY[1], 20)
    camhead = box((-3.7, CAM_Y - 3.7, 10.8), (3.7, CAM_Y + 3.7, 14.6))
    c = L.union(carrier, key, nose, camhead)
    cuts = []
    # forward-assist serrations on the right side
    for k in range(7):
        y = -98.5 + k * 3.9
        g = box((-20.0, y - 0.9, -6.5), (-CARRIER_R + 1.6, y + 0.9, 6.5)); xf(g, about(Rz(-40.0), (-CARRIER_R, y, 0.0))); cuts.append(g)
    # ejection-side flat with two gas vent holes
    cuts.append(box((-20.0, -64.0, -7.0), (-CARRIER_R + 0.7, -46.0, 7.0)))
    for z in (2.6, -2.6):
        cuts.append(cyl('X', (-55.0, z), 1.5, -14.0, -8.0, 12))
    # cam pin track (left / top), key screws, gas nose bore, hammer relief underneath
    cuts.append(prism(rrect(CAM_Y - 9.0, -2.4, CAM_Y + 5.0, 2.4, 2.4, 3), 'YZ', 6.0, 20.0))
    for y in (KEY[0] + 9.0, KEY[0] + 24.0):
        cuts.append(cyl('Z', (0.0, y), 1.8, 18.4, 20.0, 12))
    cuts.append(cyl('Y', (0.0, SP.GAS_Z), 1.6, KEY[1] - 8.0, KEY[1] + 1.0, 12))
    cuts.append(box((-6.0, -183.5, -20.0), (6.0, -128.0, -10.2)))
    cuts.append(cyl('Y', (0.0, 0.0), 6.9, r1 - 9.0, r1 + 1.0, 20))       # bolt bore at the front
    c = L.cut(c, *cuts)
    P.add(c, 'BCG', bevel=0.35, segs=1, angle=35.0)
    pin = cyl('Z', (0.0, CAM_Y), 2.9, -2.0, 12.0, 16)
    P.add(pin, 'BCG', bevel=0.2, segs=1, angle=40.0)
    return P

def bolt():
    r0, r1 = CARRIER
    P = L.Part('SM_AR15_Bolt', 'Bolt (7 lugs + extractor)', 'upper', bone='bolt', pivot=(0.0, SP.BOLT_FACE, 0.0),
               motion=dict(type='rotate', axis=(0, 1, 0), limits=(0.0, 22.5), rest=0.0, parent='bcg',
                           note='unlock: 22.5 deg about the bore axis while the carrier moves the first 3.4 mm; then travels with bcg'),
               budget=900, static=False)
    bf = SP.BOLT_FACE
    b = lathe([(0.0, r1 - 16.0), (6.6, r1 - 16.0), (6.6, bf - 6.5), (7.0, bf - 6.0), (7.0, bf - 0.6), (6.4, bf), (0.0, bf)], 16, 'Y')
    lugs = []
    for k in range(8):
        a = 45.0 * k
        if k == 6: continue                         # 270 deg = the right side (-X): the extractor takes this place
        lug = box((-1.9, bf - 5.2, 6.0), (1.9, bf - 0.8, 9.4)); xf(lug, Ry(a)); lugs.append(lug)
    ext = box((-9.6, bf - 18.0, -2.4), (-6.0, bf - 0.4, 2.4))
    b = L.union(b, ext, *lugs)
    b = L.cut(b, cyl('Y', (0.0, 0.0), 1.0, bf - 3, bf + 1, 10), cyl('Y', (2.6, -2.6), 1.3, bf - 2, bf + 1, 10),
                 cyl('Y', (0.0, 0.0), 4.85, bf - 1.0, bf + 1.0, 24))                              # case-head recess, firing pin, ejector
    P.add(b, 'BCG', bevel=0.0, segs=1, angle=35.0)
    return P

def build():
    return [L.finalize(f()) for f in (upper_receiver, dust_cover, dust_cover_rod, forward_assist, charging_handle, bcg, bolt)]
