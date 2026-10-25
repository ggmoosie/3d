"""parts_handguard.py - the two handguards of the AR-15 kit (Handguard slot):
  (A) SM_AR15_HandguardMLOK: 15 in free-float, rounded-octagon tube, integral full-length 1913 top rail, M-LOK slots
      (32 x 7 mm, r 2.4, 40 mm pitch) at 3, 6 and 9 o'clock, bottom-rear clamp with two cross screws.
  (B) SM_AR15_HandguardQuad: M4 quad rail (RAS style) between the delta ring and the FSB cap: four 1913 rails, oval vent
      holes on the diagonals, a ribbed aluminium heat shield inside, split line between the halves.
Slot centres are stored on the Part (P.slots) for the Rail_Top_NN / Mlok_<3|6|9>_NN sockets.  G-frame millimetres."""
import math
import ar15_lib as L
import ar15_spec as SP
from mathutils import Vector as V
from ar15_lib import (prism, lathe, cyl, box, rrect, rect, fillet, union, cut, xf, T, Rx, Ry, Rz, S, bm_join, loft,
                      stadium, offset2d)

def octagon(half_w, top, bot, top_half, bot_half, side_top, side_bot, r):
    pts = [(top_half, top), (half_w, side_top), (half_w, side_bot), (bot_half, bot),
           (-bot_half, bot), (-half_w, side_bot), (-half_w, side_top), (-top_half, top)]
    return fillet(pts, r, 3)

def mlok_slot_cutter(face, yc, depth_from, depth_to):
    """M-LOK slot cutter (32 x 7, r 2.4) through a face: face '3' (-X side), '9' (+X side), '6' (bottom)"""
    l, w, r = SP.MLOK_SLOT
    prof = rrect(yc - l / 2, -w / 2, yc + l / 2, w / 2, r, 2)
    if face == '6':
        return prism([(v, u) for (u, v) in prof], 'XY', depth_to, depth_from)          # (X, Y) profile along Z
    zc = SP_MLOK_SIDE_Z
    prof_yz = [(u, v + zc) for (u, v) in prof]
    a, b = (depth_from, depth_to) if face == '9' else (-depth_to, -depth_from)
    return prism(prof_yz, 'YZ', min(a, b), max(a, b))

SP_MLOK_SIDE_Z = 1.0

def mlok():
    y0 = SP.MLOK_REAR; y1 = SP.MLOK_REAR + SP.MLOK_LEN
    P = L.Part('SM_AR15_HandguardMLOK', '15 in free-float M-LOK handguard', 'handguard', configs=('MLOK',), budget=11000)
    hw, top, bot = SP.MLOK_HALF_W, SP.MLOK_TOP, SP.MLOK_BOT
    outer = octagon(hw, top, bot, 11.0, 9.5, 12.0, -10.0, 3.2)
    tube = prism(outer, 'XZ', y0, y1)
    first, n = L.rail_slots_fit(y0, y1, 2.6)
    head, rail_cuts, rail_c = L.pic_rail(y0, y1, SP.RAIL_TOP, top - 0.6, first, n)
    clamp = prism(fillet([(-7.5, bot + 1.0), (7.5, bot + 1.0), (7.5, bot - 4.6), (-7.5, bot - 4.6)], [0, 0, 1.6, 1.6], 3), 'XZ', y0 + 3.0, y0 + 30.0)
    rail = L.cut(head, *rail_cuts)
    # receiver interface: anti-rotation tabs reaching back over the upper's front, flanking its 1913 rail
    tabs = [box((10.9, y0 - 8.5, 23.0), (13.4, y0 + 2.0, 27.6)), box((-13.4, y0 - 8.5, 23.0), (-10.9, y0 + 2.0, 27.6))]
    # QD sling-swivel cups (bosses) front and rear on both sides
    QD_Y = (y0 + 34.5, y1 - 11.5)
    cups = [cyl('X', (yq, SP_MLOK_SIDE_Z), 6.4, s * (hw - 2.5), s * (hw + 1.6), 24) if s > 0 else
            cyl('X', (yq, SP_MLOK_SIDE_Z), 6.4, -(hw + 1.6), -(hw - 2.5), 24) for yq in QD_Y for s in (1, -1)]
    g = L.union(tube, clamp, *tabs, *cups)
    inner = offset2d(outer, -SP.MLOK_WALL)
    cuts = [prism(inner, 'XZ', y0 - 1.0, y1 + 1.0)]
    # M-LOK slots: 8 per face, 40 mm pitch, centred in the free length behind the clamp
    span_lo, span_hi = y0 + 32.0, y1 - 9.0
    ns = int((span_hi - span_lo - SP.MLOK_SLOT[0]) // SP.MLOK_PITCH) + 1
    first_s = span_lo + (span_hi - span_lo - ((ns - 1) * SP.MLOK_PITCH + SP.MLOK_SLOT[0])) / 2 + SP.MLOK_SLOT[0] / 2
    centres = [first_s + k * SP.MLOK_PITCH for k in range(ns)]
    for yc in centres:
        cuts.append(mlok_slot_cutter('9', yc, hw - 6.0, hw + 2.0))
        cuts.append(mlok_slot_cutter('3', yc, hw - 6.0, hw + 2.0))
        cuts.append(mlok_slot_cutter('6', yc, bot + 6.0, bot - 2.0))
    # clamp: split along the bottom + two cross screws (counterbored heads on the left, nuts on the right)
    cuts.append(box((-0.6, y0 - 1.0, bot - 6.0), (0.6, y0 + 31.0, bot + 3.5)))
    for ys in (y0 + 10.0, y0 + 23.0):
        cuts.append(cyl('X', (ys, bot - 1.8), 1.7, -9.0, 9.0, 12))
    # QD cup bores (9.5 mm) and the barrel-nut screw counterbores on the sides behind the slots
    for yq in QD_Y:
        cuts.append(cyl('X', (yq, SP_MLOK_SIDE_Z), 4.75, hw - 1.3, hw + 3.0, 20))
        cuts.append(cyl('X', (yq, SP_MLOK_SIDE_Z), 4.75, -(hw + 3.0), -(hw - 1.3), 20))
    SCREW_Y = (y0 + 9.0, y0 + 21.0)
    for ys in SCREW_Y:
        cuts.append(cyl('X', (ys, 2.0), 2.95, hw - 1.5, hw + 2.0, 16))
        cuts.append(cyl('X', (ys, 2.0), 2.95, -(hw + 2.0), -(hw - 1.5), 16))
    # lightening pockets (pass 3): real machined pockets on the two upper diagonal faces, one per M-LOK slot station:
    # 1.4 mm deep, 45 deg chamfered walls, a 0.6 mm radius into a flat floor (a ball-nose cutter's section).  The pass-2
    # pockets were 0.8 mm deep with square walls and read as painted outlines.
    dn = V((12.4, 0.0, 9.5)).normalized(); fc = (15.75, 18.2)
    phi = -math.degrees(math.atan2(dn.z, dn.x))
    POCKET = [(-1.40, 1.25, 11.6), (-1.32, 1.52, 11.87), (-1.12, 1.82, 12.17), (2.0, 4.94, 15.29)]   # depth, half w, half l
    for yc in centres:
        rings = [[(d, yc + u, v) for (u, v) in stadium((0.0, 0.0), 2 * hl, 2 * hw, 5)] for (d, hw, hl) in POCKET]
        f = loft(rings)
        xf(f, T(fc[0], 0.0, fc[1]) @ Ry(phi))
        cuts.append(f); cuts.append(L.mirror_x(L.bm_copy(f)))
    g = L.cut(g, *cuts)
    # 45 deg x 2.2 mm chamfer round the front end (intersection with a frustum that only bites the last 2.2 mm)
    fr = [(y0 - 10.0, 8.0), (y1 - 10.2, 8.0), (y1 + 1.0, -3.2)]
    g = L.inter(g, loft([[(x, y, z) for (x, z) in offset2d(outer, d)] for (y, d) in fr]))
    P.add(g, 'Handguard', bevel=0.45, segs=1, angle=35.0)
    P.add(rail, 'Handguard', bevel=0.0, segs=1, angle=35.0, sharp=35.0)
    screws = []
    for ys in (y0 + 10.0, y0 + 23.0):
        screws.append(L.cut(lathe([(0.0, 7.5), (2.6, 7.5), (2.6, 9.9), (2.2, 10.3), (0.0, 10.3)], 14, 'X', (ys, bot - 1.8)),
                            cyl('X', (ys, bot - 1.8), 1.1, 9.4, 11.0, 6)))                  # socket head + hex socket
        nut = lathe([(0.0, -10.3), (2.9, -10.3), (2.9, -7.5), (0.0, -7.5)], 6, 'X', (ys, bot - 1.8)); screws.append(nut)
    for ys in SCREW_Y:                                                               # barrel-nut screws, socket heads
        for sgn in (1, -1):
            a0, a1 = (hw - 1.5, hw - 0.25) if sgn > 0 else (-(hw - 0.25), -(hw - 1.5))
            hd = L.cut(cyl('X', (ys, 2.0), 2.55, a0, a1, 14), cyl('X', (ys, 2.0), 1.05, a0 - 1.0 if sgn < 0 else a0 + 0.5,
                                                                  a1 + 1.0 if sgn > 0 else a1 - 0.5, 6))
            screws.append(hd)
    P.add(bm_join(*screws), 'Steel', bevel=0.15, segs=1, angle=40.0)
    P.slots = dict(top=rail_c, rail_top_z=SP.RAIL_TOP, mlok=centres, mlok_side_z=SP_MLOK_SIDE_Z, mlok_side_x=hw, mlok_bot_z=bot)
    return P

# ================================================================================================ quad rail
QR_FACE = 24.4          # rail base distance from the bore axis (all four rails)
QR_INNER = 21.4

def quad():
    y0, y1 = SP.QUAD
    P = L.Part('SM_AR15_HandguardQuad', 'M4 quad rail (RAS)', 'handguard', configs=('QUAD',), budget=12000)
    oct_ = octagon(QR_FACE, QR_FACE, -QR_FACE, 11.2, 11.2, 11.2, -11.2, 2.4)
    body = prism(oct_, 'XZ', y0, y1)
    first, n = L.rail_slots_fit(y0, y1, 2.6)
    heads, cuts = [], []
    for k, ang in enumerate((0.0, 90.0, 180.0, 270.0)):
        h, rc, cs = L.pic_rail(y0, y1, SP.QUAD_R, QR_FACE - 0.6, first, n)
        h = L.cut(h, *rc); xf(h, Ry(ang)); heads.append(h)
    spigot = cyl('Y', (0.0, 0.0), 23.0, y0 - 4.0, y0 + 1.0, 32)
    g = L.union(body, spigot)
    cuts.append(cyl('Y', (0.0, 0.0), QR_INNER, y0 - 6.0, y1 + 1.0, 32))
    # oval vent holes on the four diagonal faces
    nv = 5; pitch = (y1 - y0 - 40.0) / (nv - 1)
    for a in (45.0, 135.0, 225.0, 315.0):
        for k in range(nv):
            yc = y0 + 20.0 + k * pitch
            v = prism(stadium((0.0, yc), 12.5, 6.8, 3, angle=90.0), 'XY', 15.0, 32.0)
            xf(v, Ry(a)); cuts.append(v)
    g = L.cut(g, *cuts)
    P.add(g, 'Handguard', bevel=0.4, segs=1, angle=35.0)
    P.add(bm_join(*heads), 'Handguard', bevel=0.0, segs=1, angle=35.0, sharp=35.0)
    # heat shield: thin liner with circumferential ribs, seen through the vents
    shield = lathe([(19.0, y0 + 3.0), (20.2, y0 + 3.0), (20.2, y1 - 3.0), (19.0, y1 - 3.0)], 18, 'Y', loop=True)
    ribs = []
    nr = 6; rp = (y1 - y0 - 16.0) / (nr - 1)
    for k in range(nr):
        yc = y0 + 8.0 + k * rp
        ribs.append(lathe([(19.6, yc - 1.4), (21.2, yc - 0.6), (21.2, yc + 0.6), (19.6, yc + 1.4)], 18, 'Y', loop=True))
    P.add(L.union(shield, *ribs), 'Handguard', bevel=0.0, segs=1, angle=40.0, sharp=40.0)
    P.slots = dict(top=cs, rail_top_z=SP.QUAD_R)
    return P

def build():
    return [L.finalize(f()) for f in (mlok, quad)]
