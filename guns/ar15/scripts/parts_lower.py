"""parts_lower.py - lower group of the AR-15 kit: lower receiver (+ integral trigger guard), trigger, hammer, selector,
magazine catch + button, bolt catch, lower pins, A2 pistol grip.  All numbers are G-frame millimetres (ar15_spec.py)."""
import math
import bmesh
import ar15_lib as L
import ar15_spec as SP
from ar15_lib import (prism, lathe, cyl, box, rrect, fillet, union, cut, xf, T, Rx, Ry, Rz, S, about, bm_join, mirror_x,
                      loft, circle, stadium)
from mathutils import Matrix, Vector as V

W = SP.LOWER_HALF_W
PLATEAU = W + 0.9      # pass 3: fire-control plateau surface (|X|)
TD_BOSS = W + 1.3      # takedown-pin boss face
EAR_W = W - 1.0        # recessed pivot-pin ears
SHEAR = (SP.MAGWELL_BOT_FRONT - SP.MAGWELL_BOT_REAR) / (SP.MAGWELL_FRONT - SP.MAGWELL_REAR)   # dZ/dY of the magwell bottom

def shear_mag(bm):
    """local band (bottom at Z=0, Y as is) -> magwell bottom plane (Z = MAGWELL_BOT_FRONT + SHEAR * (Y - MAGWELL_FRONT))"""
    M = Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, SHEAR, 1, SP.MAGWELL_BOT_FRONT - SHEAR * SP.MAGWELL_FRONT), (0, 0, 0, 1)))
    return xf(bm, M)

def mag_bot(y): return SP.MAGWELL_BOT_FRONT + SHEAR * (y - SP.MAGWELL_FRONT)

def arc_pts(c, r, a0, a1, n):
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]

def both_sides(make):
    """make(sign) -> bmesh for one side; returns the two joined (disjoint) shells"""
    return bm_join(make(1.0), make(-1.0))

def xprism(prof, x0, x1, sign=1.0):
    """YZ prism between |X| x0 and x1 on the side given by sign (+1 left, -1 right)"""
    a, b = sorted((x0 * sign, x1 * sign)); return prism(prof, 'YZ', a, b)

def sweep_yz(path, half_t, half_w, x0=0.0):
    """rectangular bar swept along a 2-D (Y, Z) polyline in the X = x0 plane: thickness 2*half_t in the path normal, width 2*half_w in X"""
    rings = []
    n = len(path)
    for i in range(n):
        a = V((0, *path[max(0, i - 1)])); b = V((0, *path[min(n - 1, i + 1)])); t = (b - a).normalized()
        nrm = V((0, -t.z, t.y))           # in-plane normal
        p = V((x0, *path[i]))
        rings.append([p + nrm * half_t + V((half_w, 0, 0)), p - nrm * half_t + V((half_w, 0, 0)),
                      p - nrm * half_t - V((half_w, 0, 0)), p + nrm * half_t - V((half_w, 0, 0))])
    return loft(rings)

# ================================================================================================ lower receiver
def round_edges(bm, pick, offset, segs=3):
    """bevel the bmesh edges for which pick(edge) is True (rounded edges built into the solid, before any boolean)"""
    bm.normal_update()
    es = [e for e in bm.edges if len(e.link_faces) == 2 and pick(e)]
    if es:
        bmesh.ops.bevel(bm, geom=es, offset=offset, offset_type='OFFSET', segments=segs, profile=0.5, affect='EDGES',
                        clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm

def side_bottom_edge(ymax, zmax):
    """edge between a side face (+-X) and an underside face, behind ymax and below zmax"""
    def pick(e):
        f0, f1 = e.link_faces; n0, n1 = f0.normal, f1.normal
        side = (abs(n0.x) > 0.95 and abs(n1.x) < 0.3 and n1.z < -0.25) or (abs(n1.x) > 0.95 and abs(n0.x) < 0.3 and n0.z < -0.25)
        m = (e.verts[0].co + e.verts[1].co) * 0.5
        return side and m.y < ymax and m.z < zmax
    return pick

def ray_ring(hull, c0, M, y):
    """resample a convex 2-D hull (X, Z) into M points by rays from c0 (corresponding vertices station to station)"""
    from mathutils.geometry import intersect_line_line_2d
    ring = []
    for j in range(M):
        a = 2 * math.pi * j / M; far = c0 + V((math.cos(a), math.sin(a))) * 80.0; hit = None
        for i in range(len(hull)):
            p = intersect_line_line_2d(c0, far, V(hull[i]), V(hull[(i + 1) % len(hull)]))
            if p is not None and (hit is None or (p - c0).length > (hit - c0).length): hit = p
        if hit is None: hit = c0
        ring.append((hit.x, y, hit.y))
    return ring

SHELF_Z = -46.6        # pass 3: the rear shelf behind the grip (3.2 mm step up from LOWER_BOT)

def body_bottom(y):
    """underside of the receiver body behind the grip: flat at LOWER_BOT, a 3.2 mm step up onto the rear shelf, then the
    R 12 rounded rear corner"""
    if y >= -176.0: return SP.LOWER_BOT
    if y >= -186.0: return SHELF_Z
    dy = min(12.0, -186.0 - y)
    return SHELF_Z + 12.0 - math.sqrt(max(0.0, 12.0 ** 2 - dy ** 2))

def tower_neck():
    """the solid under the buffer-tower ring, lofted from the body section into the ring with a quarter-circle fillet in
    plan: the flanks sweep out from the body sides (+-14) to the ring (+-19) over the last 22 mm (refs/06, refs/14)"""
    from mathutils.geometry import convex_hull_2d
    R = SP.TOWER_OD / 2.0; M = 36; rings = []
    y_start = -166.0; span = y_start - SP.TOWER_FRONT
    ys = [y_start - span * (1 - math.cos(math.pi / 2 * k / 9)) for k in range(10)] + [SP.TOWER_REAR]
    for y in ys:
        t = min(1.0, (y_start - y) / span); e = 1.0 - math.sqrt(max(0.0, 1.0 - t * t))      # quarter-circle fillet
        sx = (13.6 + (R - 13.6) * e) / R
        circ = [(R * math.cos(math.radians(a)) * sx, R * math.sin(math.radians(a))) for a in range(0, 360, 6)]
        circ = [p for p in circ if p[1] <= SP.PARTING]
        xp = math.sqrt(R * R - SP.PARTING ** 2) * sx
        zb = body_bottom(max(y, -198.0)) + 1.8
        pts = circ + [(xp, SP.PARTING), (-xp, SP.PARTING), (13.2, zb), (-13.2, zb), (11.0, zb - 0.6), (-11.0, zb - 0.6)]
        hull = [pts[i] for i in convex_hull_2d(pts)]
        rings.append(ray_ring(hull, V((0.0, (SP.PARTING + zb) / 2.0)), M, y))
    return loft(rings)

def magwell_shell():
    """the proud magwell walls as a loft from the flared mouth up to Z -17: the mouth flares out 2 mm all round, and the front
    face leans forward toward the bottom (forward taper, refs/01).  Ring points ride on the sloped magwell bottom."""
    F_, R_ = SP.MAGWELL_FRONT, SP.MAGWELL_REAR
    #        h above the bottom, half width, front ext, rear ext, front r, rear r
    spec = [(0.0, 17.35, 4.6, 1.4, 6.5, 3.2), (1.5, 17.35, 4.6, 1.4, 6.5, 3.2), (3.4, 16.55, 3.9, 0.9, 5.8, 2.8),
            (5.8, 15.85, 3.3, 0.45, 5.2, 2.4), (8.8, 15.45, 2.9, 0.1, 4.8, 2.1), (None, 15.4, 0.0, 0.0, 3.0, 1.6)]
    rings = []
    for h, hw, fe, re_, rf, rr in spec:
        prof = fillet([(-hw, R_ - re_), (hw, R_ - re_), (hw, F_ + fe), (-hw, F_ + fe)], [rr, rr, rf, rf], 4)
        rings.append([(x, y, (-17.0 if h is None else mag_bot(y) + h)) for (x, y) in prof])
    return loft(rings)

def fence_profile(side):
    """raised frame on the magwell side (1 mm proud of the wall): top rib along the magwell top + the rear block that
    carries the magazine-catch button (right, the 'fence', refs/01 + 06) or the bolt catch and catch arm (left, refs/14).
    Returns a (Y, Z) polygon."""
    mb = lambda y: mag_bot(y) + 1.0
    if side < 0:     # right: button fence
        pts = [(-10.2, -16.5), (-93.5, -16.5), (-93.5, -43.0), (-84.0, -56.0), (-79.5, -64.0), (-78.6, mb(-78.6)),
               (-71.0, mb(-71.0)), (-71.0, -56.0), (-63.0, -42.0), (-63.0, -22.6), (-10.2, -22.6)]
        rad = [1.2, 2.5, 4.0, 6.0, 3.0, 0, 0, 6.0, 8.0, 4.0, 1.2]
    else:            # left: bolt-catch block, the roll-mark panel stays clear in front of it (Y > -71)
        pts = [(-10.2, -16.5), (-99.0, -16.5), (-99.0, -42.0), (-86.0, -57.0), (-80.0, -65.0), (-78.6, mb(-78.6)),
               (-73.4, mb(-73.4)), (-73.4, -54.0), (-72.0, -46.0), (-72.0, -22.6), (-10.2, -22.6)]
        rad = [1.2, 2.5, 4.0, 6.0, 3.0, 0, 0, 5.0, 6.0, 4.0, 1.2]
    return fillet(pts, rad, 3)

def lower_receiver():
    P = L.Part('SM_AR15_LowerReceiver', 'Lower receiver', 'lower', budget=9800)
    # ---- main side profile (front pivot ears, magwell core, trigger-guard span, grip seat, rear shelf, R 12 rear corner)
    prof = [(2.2, SP.PARTING), (2.2, -24.4), (SP.MAGWELL_FRONT, -24.4), (SP.MAGWELL_FRONT, SP.MAGWELL_BOT_FRONT),
            (SP.MAGWELL_REAR, SP.MAGWELL_BOT_REAR), (SP.MAGWELL_REAR, SP.LOWER_BOT), (-176.0, SP.LOWER_BOT),
            (-177.6, SHELF_Z), (-198.0, SHELF_Z), (-198.0, SP.PARTING)]
    radii = [1.6, 6.5, 1.5, 2.5, 2.5, 1.5, 1.2, 1.0, 12.0, 0.0]
    body = prism(fillet(prof, radii, 5), 'YZ', -W, W)
    # rounded lower edges along the underside behind the magwell (R 2.4, built in before the booleans)
    round_edges(body, side_bottom_edge(-79.5, -30.0), 2.4, 3)
    shell = magwell_shell()
    fences = [prism(fence_profile(-1), 'YZ', -SP.MAGWELL_HALF_W - 1.0, -W + 0.4),
              prism(fence_profile(1), 'YZ', W - 0.4, SP.MAGWELL_HALF_W + 1.0)]
    # ---- trigger guard: front ears (lug pair) and the rear web (one solid web, slotted for the guard tongue)
    fy, fz = SP.GUARD_FRONT_PIN; ry, rz = SP.GUARD_REAR_PIN
    ear_f = fillet([(-75.0, -49.0), (-75.5, fz)] + arc_pts((fy, fz), 5.5, 0, -180, 10)[1:] + [(fy - 5.5, -54.0), (-83.0, -49.0)],
                   [0, 0] + [0] * 10 + [3.0, 0], 3)
    ears = [prism(ear_f, 'YZ', 5.3, 9.6), prism(ear_f, 'YZ', -9.6, -5.3)]
    # pass 4b: the opening's rear wall sits at the rear pin, bulging back a little at mid-height (refs/01, refs/05); it was
    # 7 mm further forward, which crowded the trigger blade toward the magwell
    web_pts = ([(-124.6, -47.5), (-126.6, -51.2), (-129.6, -54.6), (-131.2, -60.0), (-130.4, -65.6), (-128.0, -70.0), (ry + 5.4, rz)]
               + arc_pts((ry, rz), 5.4, 0, -180, 10)[1:] + [(ry - 5.4, -57.0), (-137.6, -47.5)])
    web = prism(fillet(web_pts, [0, 2.5, 3.0, 3.0, 3.0, 2.0, 1.5] + [0] * 10 + [2.0, 0], 3), 'YZ', -8.6, 8.6)
    # ---- buffer tower: ring + filleted neck
    R = SP.TOWER_OD / 2
    tower = lathe([(0.0, SP.TOWER_FRONT), (R - 1.2, SP.TOWER_FRONT), (R, SP.TOWER_FRONT - 1.2),
                   (R, SP.TOWER_REAR + 0.8), (R - 0.8, SP.TOWER_REAR), (0.0, SP.TOWER_REAR)], 40, 'Y')
    neck = tower_neck()
    # ---- left: bolt-catch ears (D-shaped lobes around the fore-aft roll pin)
    from mathutils.geometry import convex_hull_2d
    lobe = [(15.6 + 3.5 * math.cos(math.radians(a)), -18.0 + 3.5 * math.sin(math.radians(a))) for a in range(0, 360, 20)]
    lobe += [(12.8, -10.6), (12.8, -23.8), (14.0, -23.8), (14.0, -10.6)]
    lobe = [lobe[i] for i in convex_hull_2d(lobe)]
    bosses = [prism(lobe, 'XZ', -83.4, -78.8), prism(lobe, 'XZ', -96.6, -92.0)]
    # ---- pass 3 forging relief (refs/06, 14): fire-control plateau (+0.9 mm) with a 5.8 mm band left at body level along
    # the underside, takedown-pin boss bulges (+1.3 mm), raised magwell side panels inside the fence frame (+0.6 over the
    # wall), a 45 deg lip where the magwell's top rib meets the body
    relief = []
    for sgn, y_front in ((-1.0, -93.5), (1.0, -99.0)):
        plat = fillet([(y_front, -12.2), (-160.0, -12.2), (-160.0, -44.0), (y_front, -44.0)], [0.0, 6.0, 6.0, 0.0], 3)
        relief.append(xprism(plat, W - 0.4, PLATEAU, sgn))
        boss = lathe([(0.0, W - 0.6), (6.8, W - 0.6), (6.8, TD_BOSS - 0.55), (6.25, TD_BOSS), (0.0, TD_BOSS)], 28, 'X',
                     (SP.TAKEDOWN_Y, SP.PIN_Z))
        relief.append(boss if sgn > 0 else L.mirror_x(boss))
        arc = [(W + 2.4 - 2.4 * math.cos(math.radians(t)), -14.2 - 2.4 * math.sin(math.radians(t))) for t in range(0, 91, 15)]
        lip = prism([(sgn * x, z) for (x, z) in [(W - 0.2, -14.2)] + arc + [(W - 0.2, -16.6)]], 'XZ', y_front, -10.2)   # R 2.4 forging radius
        relief.append(lip)
    mb = lambda y: mag_bot(y) + 12.0
    for sgn, pts in ((-1.0, [(-12.6, -25.0), (-60.4, -25.0), (-60.4, -43.0), (-67.5, -56.0), (-67.5, mb(-67.5)), (-12.6, mb(-12.6))]),
                     (1.0, [(-12.6, -25.0), (-69.6, -25.0), (-69.6, -50.0), (-70.6, mb(-70.6)), (-12.6, mb(-12.6))])):
        rad = [2.5, 2.5, 5.0, 3.0, 2.5, 2.5][:len(pts)]
        relief.append(xprism(fillet(pts, rad, 3), SP.MAGWELL_HALF_W - 0.4, SP.MAGWELL_HALF_W + 0.6, sgn))
    solid = L.union(body, shell, *fences, tower, neck, web, *ears, *bosses, *relief)
    # ---- cuts
    my, mz = SP.MAGCATCH
    def ring(y0, y1, hw, r, z):
        return [(x, y, z) for (x, y) in rrect(-hw, y0, hw, y1, r, 3)]
    cuts = []
    cuts.append(box((-SP.MAG_IN_HALF_W, SP.MAG_IN_REAR, -110.0), (SP.MAG_IN_HALF_W, SP.MAG_IN_FRONT, 5.0)))      # magwell
    mouth = loft([ring(SP.MAG_IN_REAR - 2.0, SP.MAG_IN_FRONT + 2.6, SP.MAG_IN_HALF_W + 2.0, 3.5, -1.0),
                  ring(SP.MAG_IN_REAR - 2.0, SP.MAG_IN_FRONT + 2.6, SP.MAG_IN_HALF_W + 2.0, 3.5, 0.2),
                  ring(SP.MAG_IN_REAR, SP.MAG_IN_FRONT, SP.MAG_IN_HALF_W, 0.5, 7.0)])
    cuts.append(shear_mag(mouth))                                                                                 # entry flare
    cuts.append(box((-6.4, -12.0, -26.0), (6.4, 6.0, 5.0)))                       # upper's front lug slot (between the ears)
    cuts.append(box((-9.5, -158.0, -46.0), (9.5, -84.0, 5.0)))                    # fire-control pocket
    cuts.append(box((-4.2, -124.0, -56.0), (4.2, -91.0, -40.0)))                  # trigger slot: blade root under the pin + nose travel
    cuts.append(cyl('Y', (0.0, 0.0), SP.BUFFER_OD / 2, -206.0, -158.0, 40))       # tower bore + buffer channel in the deck
    import parts_upper as PU                                                       # clearance for the forward-assist cap
    cuts.append(L.lathe_on([(6.95, PU.FA_KNOB_A - 1.5), (6.95, PU.FA_HOUSING_A + 0.6)], 32, tuple(PU.FA_REAR), PU.FA_DIR))
    cuts.append(box((-6.4, -176.0, -26.0), (6.4, -163.5, 5.0)))                   # upper's takedown lug slot
    for (y, z), r in (((SP.PIVOT_Y, SP.PIN_Z), SP.PIN_D / 2 + 0.05), ((SP.TAKEDOWN_Y, SP.PIN_Z), SP.PIN_D / 2 + 0.05),
                      (SP.TRIGGER_PIN, SP.FCG_PIN_D / 2), (SP.HAMMER_PIN, SP.FCG_PIN_D / 2), (SP.SELECTOR, SP.SELECTOR_D / 2)):
        cuts.append(cyl('X', (y, z), r, -22.0, 22.0, 20 if r > 3 else 12))
    for (y, z) in (SP.GUARD_FRONT_PIN, SP.GUARD_REAR_PIN):
        cuts.append(cyl('X', (y, z), 1.25, -10.5, 10.5, 12))
    cuts.append(box((-5.35, ry - 7.0, -82.0), (5.35, ry + 7.0, -66.0)))           # guard tongue slot in the rear web
    # pivot-pin detent hole in the front face of the right ear
    cuts.append(cyl('Y', (-10.4, -21.4), 0.95, -3.0, 4.0, 10))
    # left: magazine-catch arm channel + catch window into the magwell; bolt-catch slot between the ears; roll pin
    cuts.append(prism(rrect(my - 14.5, mz - 4.6, -47.5, mz + 4.6, 2.0, 3), 'YZ', 13.4, 20.0))
    cuts.append(prism(rrect(-57.5, mz - 3.4, -48.5, mz + 3.4, 1.0, 2), 'YZ', 10.0, 20.0))
    cuts.append(box((9.0, -92.5, -13.0), (20.0, -83.0, 5.0)))                     # paddle notch in the deck edge
    cuts.append(box((14.1, -92.0, -29.2), (21.0, -83.4, -9.5)))                   # catch slot between the ears
    cuts.append(box((14.1, -92.0, -29.2), (21.0, -79.0, -23.9)))                  # plunger-tab channel under the front ear
    cuts.append(cyl('Y', (15.6, -18.0), 1.2, -100.0, -75.0, 12))
    # right: button pocket in the fence (rounded, taller than wide) + button bore
    cuts.append(prism(rrect(my - 6.9, mz - 8.1, my + 6.9, mz + 8.1, 5.6, 4), 'YZ', -18.0, -W - 0.6))
    cuts.append(cyl('X', (my, mz), 5.85, -18.0, -9.0, 24))
    cuts.append(cyl('X', (my, mz), 2.7, -20.0, 20.0, 12))
    cuts.append(prism(rrect(-68.6, -55.6, -16.0, -40.0, 3.0, 3), 'YZ', SP.MAGWELL_HALF_W + 0.1, 20.0))            # roll-mark panel
    # recessed pivot-pin ears: the front lug pair stands 1 mm inside the body sides (refs/06)
    cuts += [box((EAR_W, -9.3, -26.0), (22.0, 3.2, -8.5)), box((-22.0, -9.3, -26.0), (-EAR_W, 3.2, -8.5))]
    solid = L.cut(solid, *cuts)
    P.add(solid, 'Receiver', bevel=0.6, segs=1, angle=35.0)
    # ---- trigger guard (separate aluminium shell): hinge knuckle at the front ear, flat bar with relieved sides,
    # tongue at the rear pinned in the web
    # pass 4b: the bar runs flat to under the rear web and rises to the tongue inside it (it used to rise in front of the moved
    # web face and showed as a separate strut)
    path = fillet([(fy, fz), (fy - 2.4, -79.35), (fy - 9.0, -79.35), (ry + 3.2, -79.35), (ry + 0.6, rz - 1.6), (ry, rz)],
                  [0, 3.5, 0, 2.0, 0.8, 0], 5, closed=False)
    guard = sweep_yz(path, 1.75, 5.1)
    knuckle = cyl('X', (fy, fz), 3.95, -5.1, 5.1, 20)
    tongue = cyl('X', (ry, rz), 3.6, -5.1, 5.1, 16)
    guard = L.union(guard, knuckle, tongue)
    relief = [box((4.55, -122.0, -80.25), (6.0, -90.0, -78.45)), box((-6.0, -122.0, -80.25), (-4.55, -90.0, -78.45))]   # side relief
    guard = L.cut(guard, cyl('X', (fy, fz), 1.25, -6, 6, 12), cyl('X', (ry, rz), 1.25, -6, 6, 12), *relief)
    P.add(guard, 'Receiver', bevel=0.35, segs=1, angle=35.0)
    return P

# ================================================================================================ trigger
# pass 4b (user: "our trigger assembly is completely backwards"; refs 05 + 06): the blade hangs right under the trigger pin in
# the REAR half of the guard opening, its finger face (the FRONT face - the finger pulls from in front) concave, the tip
# curling forward.  Both faces are arcs about centres in front of the blade.
TRIG_FC, TRIG_FR = (-99.5, -61.0), 19.5        # finger (front) face arc
TRIG_BC, TRIG_BR = (-99.5, -61.5), 23.8        # back face arc

def trig_face_y(z):
    """Y of the finger face at height z (G mm)"""
    return TRIG_FC[0] - math.sqrt(TRIG_FR ** 2 - (z - TRIG_FC[1]) ** 2)

def trigger():
    py, pz = SP.TRIGGER_PIN
    P = L.Part('SM_AR15_Trigger', 'Trigger + disconnector', 'lower', bone='trigger', pivot=(0.0, py, pz),
               motion=dict(type='rotate', axis=(1, 0, 0), limits=(-9.0, 0.0), rest=0.0,
                           note="pull: the blade moves toward -Y (rotation about +X, right-hand rule in UE numbers)"), budget=1700)
    back = arc_pts(TRIG_BC, TRIG_BR, 130.0, 211.0, 13)               # down the back face (starts inside the body: no sliver
    face = arc_pts(TRIG_FC, TRIG_FR, 214.0, 130.0, 13)               # up the finger face   where the two outlines cross)
    prof = back + face
    rad = [0.0] * len(prof); rad[len(back) - 1] = 1.6; rad[len(back)] = 1.4
    blade = prism(fillet(prof, rad, 3), 'YZ', -3.4, 3.4)             # a little narrower than the body: no step slivers
    # body inside the receiver: pivot eye, sear nose forward under the hammer, tail back under the selector, the blade root
    # through the floor slot right under the pin
    bprof = fillet([(-93.5, -38.6), (-93.5, -42.4), (-98.0, -43.9), (-108.0, -44.6), (-113.5, -47.2), (-121.2, -47.2), (-122.8, -45.2),
                    (-126.0, -43.6), (-133.0, -42.0), (-146.8, -40.4), (-146.8, -37.3), (-137.5, -36.0), (-124.0, -29.5), (-112.0, -30.5),
                    (-100.0, -35.6)],
                   [0.8, 0.8, 0, 2.0, 0, 0, 1.0, 1.5, 0, 0.8, 0.8, 1.5, 3.0, 3.0, 0], 2)       # rear of the root stays in the slot when pulled
    body = prism(bprof, 'YZ', -3.6, 3.6)
    t = L.union(blade, body)
    t = L.cut(t, cyl('X', (py, pz), SP.FCG_PIN_D / 2 + 0.05, -5, 5, 16),
              box((-1.55, -122.4, -34.6), (1.55, -102.0, -24.0)))                       # disconnector slot in the top
    P.add(t, 'Steel', bevel=0.3, segs=2, angle=30.0)
    # disconnector: plate in the slot on the trigger pin, its hook end at the rear (hidden; seen with the carrier out)
    dprof = fillet([(-102.4, -35.6), (-102.4, -33.0), (-110.0, -31.2), (-118.0, -30.2), (-121.7, -30.6), (-122.2, -32.2), (-121.0, -33.4),
                    (-118.6, -32.8), (-110.0, -34.6)], [0.6, 0.6, 1.0, 0.8, 0.5, 0.5, 0.4, 0.8, 1.0], 2)
    d = L.cut(prism(dprof, 'YZ', -1.35, 1.35), cyl('X', (py, pz), SP.FCG_PIN_D / 2 + 0.05, -5, 5, 12))
    P.add(d, 'Steel', bevel=0.15, segs=1, angle=30.0)
    return P

# ================================================================================================ hammer
def hammer():
    hy, hz = SP.HAMMER_PIN
    P = L.Part('SM_AR15_Hammer', 'Hammer', 'lower', bone='hammer', pivot=(0.0, hy, hz),
               motion=dict(type='rotate', axis=(1, 0, 0), limits=(-74.0, 0.0), rest=0.0,
                           note='cocked at rest (head back, under the carrier); fall = -74 deg about +X: the head swings up and forward onto the firing pin'),
               budget=900, static=False)
    # authored upright (fired), then rotated back to the cocked rest pose
    prof = fillet([(hy + 6.5, hz + 2.0), (hy + 9.0, hz + 22.0), (hy + 7.5, hz + 25.5), (hy - 2.0, hz + 27.0), (hy - 5.5, hz + 23.0),
                   (hy - 6.0, hz + 8.0), (hy - 9.5, hz + 2.0), (hy - 9.0, hz - 4.0), (hy - 3.0, hz - 7.0), (hy + 4.0, hz - 6.5),
                   (hy + 8.5, hz - 3.5)], [1.0, 1.5, 1.0, 1.5, 1.0, 2.0, 1.5, 2.0, 2.0, 2.0, 1.0], 3)
    h = prism(prof, 'YZ', -3.9, 3.9)
    h = L.cut(h, cyl('X', (hy, hz), SP.FCG_PIN_D / 2 + 0.05, -5, 5, 16),
              box((-1.6, hy - 7.0, hz + 6.0), (1.6, hy + 3.0, hz + 20.0)))           # slot for the disconnector hook
    xf(h, about(Rx(80.0), (0.0, hy, hz)))                                            # cocked: head back, lying under the carrier path
    P.add(h, 'Steel', bevel=0.3, segs=1, angle=35.0)
    return P

# ================================================================================================ selector
def selector():
    sy, sz = SP.SELECTOR
    P = L.Part('SM_AR15_Selector', 'Selector', 'lower', bone='selector', pivot=(0.0, sy, sz),
               motion=dict(type='rotate', axis=(1, 0, 0), limits=(0.0, 180.0), rest=0.0, stops={'SAFE': 0, 'SEMI': 90, 'AUTO': 180},
                           note='lever tip: +Y (SAFE, rest) -> +Z (SEMI) -> -Y (AUTO); rotation about +X'), budget=1200)
    E = PLATEAU - W                                         # pass 3: the lever sits on the fire-control plateau
    drum = cyl('X', (sy, sz), SP.SELECTOR_D / 2 - 0.05, -PLATEAU - 0.1, PLATEAU + 0.6, 18)
    # lever on the left side, pointing forward (SAFE)
    lever = prism(fillet([(sy - 5.2, sz - 4.6), (sy + 4.0, sz - 4.0), (sy + 18.5, sz - 2.8), (sy + 21.5, sz - 1.0),
                          (sy + 21.5, sz + 1.0), (sy + 18.5, sz + 2.8), (sy + 4.0, sz + 4.0), (sy - 5.2, sz + 4.6)],
                         [2.5, 0, 3.0, 1.2, 1.2, 3.0, 0, 2.5], 3), 'YZ', W + E + 0.4, W + E + 3.4)
    rib = prism(rrect(sy + 13.0, sz - 2.2, sy + 20.0, sz + 2.2, 1.0, 2), 'YZ', W + E + 3.2, W + E + 4.1)
    hub = cyl('X', (sy, sz), 5.6, W + E + 0.4, W + E + 3.6, 20)
    s = L.union(drum, lever, hub, rib)
    s = L.cut(s, box((-PLATEAU - 2, sy - 0.6, sz + 1.2), (-PLATEAU + 0.3, sy + 0.6, sz + 5)),     # indicator notch (points at the setting)
              box((-3.9, sy - 6.0, sz - 6.0), (3.9, sy - 1.0, sz + 6.0)))         # pass 4b: trigger-tail cut-away: faces back at SAFE
                                                                                   # (the full drum blocks the tail), down at SEMI (the tail rises)
    P.add(s, 'Steel', bevel=0.3, segs=1, angle=30.0)
    return P

# ================================================================================================ magazine catch + button
def mag_catch():
    my, mz = SP.MAGCATCH
    P = L.Part('SM_AR15_MagCatch', 'Magazine catch + button', 'lower', bone='mag_catch', pivot=(-SP.LOWER_HALF_W - 2.4, my, mz),
               motion=dict(type='translate', axis=(1, 0, 0), limits=(0.0, 3.2), rest=0.0,
                           note='press: the button and catch move toward +X (the catch lug leaves the magazine notch)'), budget=1200)
    button = lathe([(0.0, -16.3), (4.6, -16.3), (5.5, -15.7), (5.5, -12.5), (4.2, -12.5), (4.2, -10.0), (0.0, -10.0)], 16, 'X', (my, mz))
    shaft = cyl('X', (my, mz), 2.45, -11.0, 13.6, 16)
    arm = prism(fillet([(my + 3.8, mz - 3.9), (-55.0, mz - 3.9), (-49.2, mz - 2.9), (-49.2, mz + 2.9), (-55.0, mz + 3.9), (my + 3.8, mz + 3.9),
                        (my - 4.6, mz + 3.0), (my - 4.6, mz - 3.0)], [0, 1.0, 0.8, 0.8, 1.0, 0, 2.5, 2.5], 3), 'YZ', 13.55, 14.95)
    boss = cyl('X', (my, mz), 4.1, 13.45, 15.1, 20)
    lug = prism(rrect(-56.8, mz - 2.7, -49.6, mz + 2.7, 0.8, 2), 'YZ', 10.6, 14.0)
    m = L.union(button, shaft, arm, boss, lug)
    m = L.cut(m, cyl('X', (my, mz), 1.1, 14.6, 16.0, 12))     # threaded shaft end seen in the boss
    P.add(m, 'Steel', bevel=0.25, segs=1, angle=30.0)
    return P

# ================================================================================================ bolt catch
def bolt_catch():
    P = L.Part('SM_AR15_BoltCatch', 'Bolt catch', 'lower', bone='bolt_catch', pivot=(15.6, -87.75, -18.0),
               motion=dict(type='rotate', axis=(0, 1, 0), limits=(0.0, 9.0), rest=0.0,
                           note='lock: rotation about the fore-aft roll pin; the paddle top tilts out (+X), the stop rises into the bolt path'),
               budget=1200)
    paddle = prism(fillet([(-82.2, 3.2), (-82.2, -10.5), (-93.3, -10.5), (-93.3, 3.2)], [4.5, 1.0, 1.0, 4.5], 4), 'YZ', 15.4, 17.6)
    stem = prism(rrect(-91.6, -27.5, -83.9, -9.0, 1.0, 2), 'YZ', 14.4, 16.8)
    tab = prism(fillet([(-79.5, -24.0), (-79.5, -28.2), (-91.6, -28.2), (-91.6, -24.0)], [1.5, 1.5, 1.0, 0.0], 3), 'YZ', 14.4, 18.2)
    hook = prism(rrect(-91.4, -12.8, -84.1, -9.4, 0.6, 2), 'YZ', 9.6, 15.6)
    pinboss = cyl('Y', (15.6, -18.0), 2.6, -91.45, -84.05, 16)
    b = L.union(paddle, stem, tab, hook, pinboss)
    grooves = [box((17.0, -93.6, z - 0.45), (18.0, -81.9, z + 0.45)) for z in (-7.8, -5.4, -3.0, -0.6, 1.8)]
    b = L.cut(b, *grooves, cyl('Y', (15.6, -18.0), 1.25, -95, -80, 12))
    P.add(b, 'Steel', bevel=0.22, segs=1, angle=30.0)
    return P

# ================================================================================================ pins
def lower_pins():
    P = L.Part('SM_AR15_LowerPins', 'Pivot + takedown pins, FCG pins, roll pins', 'lower', budget=2600)
    pins = []
    r = SP.PIN_D / 2
    for y, wb in ((SP.PIVOT_Y, EAR_W), (SP.TAKEDOWN_Y, TD_BOSS)):
        # head on the right side (-X, pulled out to break the gun open): domed face with a centre dimple; the left end
        # stands 0.3 mm proud with a chamfer and the detent-plunger dimple.  wb = the face the pin sits in (recessed
        # pivot ear / takedown boss, pass 3)
        pins.append(lathe([(0.0, wb + 0.05), (1.1, wb + 0.3), (r - 0.55, wb + 0.3), (r, wb - 0.25), (r, -wb), (4.85, -wb),
                           (4.85, -wb - 0.9), (4.25, -wb - 1.55), (2.6, -wb - 1.95), (1.0, -wb - 1.95), (0.0, -wb - 1.7)],
                          16, 'X', (y, SP.PIN_Z)))
    for (y, z) in (SP.TRIGGER_PIN, SP.HAMMER_PIN):
        pins.append(cyl('X', (y, z), SP.FCG_PIN_D / 2, -PLATEAU - 0.05, PLATEAU + 0.05, 12))
    for (y, z) in (SP.GUARD_FRONT_PIN, SP.GUARD_REAR_PIN):
        pins.append(cyl('X', (y, z), 1.25, -9.8, 9.8, 8))
    pins.append(L.tube('Y', (15.6, -18.0), 1.2, 0.55, -96.8, -78.7, 10))           # bolt-catch roll pin (hollow)
    P.add(bm_join(*pins), 'Steel', bevel=0.2, segs=1, angle=40.0)
    return P

# ================================================================================================ A2 pistol grip
# A2 outline traced from refs/01 (closed silhouette mask, 0.802 mm/px): front strap with the middle-finger groove and the
# A2 finger swell at Z -106, rear strap, base tilted ~13 deg.  The top front tucks behind the trigger guard's rear ear.
FRONT = [(-137.2, -49.8), (-138.2, -60.0), (-139.4, -72.0), (-140.8, -82.0), (-142.6, -88.0), (-145.2, -93.5), (-147.2, -98.5),
         (-146.8, -101.5), (-145.0, -104.0), (-143.9, -106.5), (-144.7, -108.6), (-148.6, -109.9), (-154.0, -110.8),
         (-157.6, -114.5), (-161.4, -121.5), (-165.2, -128.5), (-168.6, -135.0), (-171.0, -141.0), (-172.2, -146.5), (-172.4, -151.2)]
REAR = [(-173.6, -49.8), (-174.4, -56.0), (-175.6, -62.0), (-177.6, -66.5), (-180.6, -71.5), (-184.0, -76.5), (-187.4, -81.5),
        (-191.0, -86.5), (-194.6, -91.5), (-198.2, -96.5), (-201.8, -101.5), (-205.4, -106.5), (-209.0, -111.5), (-212.6, -116.5),
        (-216.2, -121.5), (-219.8, -126.5), (-223.2, -131.5), (-226.0, -136.0), (-227.2, -139.2)]
GRIP_AXIS = (-0.423, -0.906)

def _at_height(poly, t):
    """point of a top-to-bottom outline at normalised height t measured along GRIP_AXIS"""
    import numpy as np
    P_ = np.array(poly, float); a = np.array(GRIP_AXIS); s = P_ @ a; tgt = s[0] + t * (s[-1] - s[0])
    for i in range(len(s) - 1):
        if (s[i] - tgt) * (s[i + 1] - tgt) <= 0 and s[i + 1] != s[i]:
            f = (tgt - s[i]) / (s[i + 1] - s[i]); return P_[i] + (P_[i + 1] - P_[i]) * f
    return P_[-1]

def _interp(poly, t):
    """point at normalised arc length t along a polyline"""
    import numpy as np
    P_ = np.array(poly, float); d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))]; s = t * d[-1]
    i = min(len(d) - 2, int(np.searchsorted(d, s, 'right') - 1)); f = (s - d[i]) / max(1e-9, d[i + 1] - d[i])
    return P_[i] + (P_[i + 1] - P_[i]) * f

def grip():
    P = L.Part('SM_AR15_Grip', 'A2 pistol grip', 'lower', budget=4200)
    import numpy as np
    N = 34; M = 28; rings = []
    for i in range(N + 1):
        t = i / N
        F = _at_height(FRONT, t); Rr = _at_height(REAR, t)
        hw = 12.8 + 2.3 * min(1.0, t / 0.3) - 0.5 * max(0.0, (t - 0.55) / 0.35)
        lip = 0.0
        if t > 0.92: lip = (t - 0.92) / 0.08 * 1.3
        hw = min(hw, 15.1) + lip
        c = (F + Rr) / 2.0; ax = (F - Rr); depth = np.linalg.norm(ax); ax = ax / depth
        half = depth / 2.0
        ring = []
        for k in range(M):
            a = 2 * math.pi * k / M
            ca, sa = math.cos(a), math.sin(a)
            e = 2.5 if ca > 0 else 2.9          # rounder front strap, squarer back corners, flat checkered sides
            u = math.copysign(abs(ca) ** (2.0 / e), ca); w = math.copysign(abs(sa) ** (2.0 / e), sa)
            yz = c + ax * (u * half)
            ring.append((w * hw, yz[0], yz[1]))
        rings.append(ring)
    g = loft(rings)
    # storage cavity in the base (open bottom), along the grip axis
    base_c = (_at_height(FRONT, 1.0) + _at_height(REAR, 1.0)) / 2.0
    ax = np.array([-GRIP_AXIS[0], -GRIP_AXIS[1]])
    ang = math.degrees(math.atan2(ax[0], ax[1]))
    cav = prism(rrect(-10.0, -7.0, 10.0, 7.0, 4.5, 3), 'XY', -6.0, 48.0)
    xf(cav, T(0.0, base_c[0] + 2.0, base_c[1]) @ Rx(-ang))
    g = L.cut(g, cav)
    P.add(g, 'Polymer', bevel=0.6, segs=2, angle=40.0, sharp=40.0)
    return P

def build():
    return [L.finalize(f()) for f in (lower_receiver, trigger, hammer, selector, mag_catch, bolt_catch, lower_pins, grip)]
