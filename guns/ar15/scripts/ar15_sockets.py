"""ar15_sockets.py - socket layout of the assembled AR-15 meshes (INTEGRATION.md table + the rail-system extras), UE FRotator
math, and the socket-vs-geometry checks used by the verify pass.  Pure Python + mathutils; positions are built in the G frame
(mm) and written in the F frame (UE cm)."""
import math
from mathutils import Vector as V
import ar15_spec as SP

# ------------------------------------------------------------------------------------------------ UE rotator math
def rotator_axes(p, y, r):
    """FRotator (pitch, yaw, roll) degrees -> (X, Y, Z) axes in UE coordinates (FRotationMatrix)"""
    sp, cp = math.sin(math.radians(p)), math.cos(math.radians(p))
    sy, cy = math.sin(math.radians(y)), math.cos(math.radians(y))
    sr, cr = math.sin(math.radians(r)), math.cos(math.radians(r))
    X = V((cp * cy, cp * sy, sp))
    Y = V((sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp))
    Z = V((-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp))
    return X, Y, Z

def axes_rotator(X, Z):
    """axes (X forward, Z up; Y = Z x X as in UE's FRotationMatrix) -> FRotator (pitch, yaw, roll), UE's FMatrix::Rotator()"""
    X = V(X).normalized(); Z = (V(Z) - V(X).normalized() * V(Z).dot(V(X).normalized())).normalized(); Y = Z.cross(X)
    pitch = math.degrees(math.atan2(X.z, math.sqrt(X.x ** 2 + X.y ** 2)))
    yaw = math.degrees(math.atan2(X.y, X.x))
    _, SY, _ = rotator_axes(pitch, yaw, 0.0)
    roll = math.degrees(math.atan2(Z.dot(SY), Y.dot(SY)))
    return [round(pitch, 4) + 0.0, round(yaw, 4) + 0.0, round(roll, 4) + 0.0]

def selftest():
    for rot, ax in (((270, 0, 0), ((0, 0, -1), (0, 1, 0), (1, 0, 0))), ((0, 90, 0), ((0, 1, 0), (-1, 0, 0), (0, 0, 1)))):
        X, Y, Z = rotator_axes(*rot)
        for a, b in zip((X, Y, Z), ax): assert (a - V(b)).length < 1e-6, (rot, a, b)
        back = axes_rotator(X, Z); X2, Y2, Z2 = rotator_axes(*back)
        assert (X2 - X).length < 1e-6 and (Z2 - Z).length < 1e-6, (rot, back)
    return True

# ------------------------------------------------------------------------------------------------ layout
def g2f(p): return [round((p[0] + SP.G2F[0]) / 10.0, 4), round((p[1] + SP.G2F[1]) / 10.0, 4), round((p[2] + SP.G2F[2]) / 10.0, 4)]

def S(name, g, X=(0, 1, 0), Z=(0, 0, 1), rot=None, scale=(1, 1, 1), tag='', part=None, check=None, note='', nrm=None):
    """one socket; nrm = outward surface normal used by the verify checks (defaults to the socket Z axis)"""
    r = list(rot) if rot is not None else axes_rotator(X, Z)
    Xa, Ya, Za = rotator_axes(*r)
    return dict(name=name, loc=g2f(g), rot_pyr=[round(v, 4) for v in r], scale=list(scale), tag=tag,
                x_axis=[round(c, 5) for c in Xa], y_axis=[round(c, 5) for c in Ya], z_axis=[round(c, 5) for c in Za],
                g_mm=[round(c, 3) for c in g], part=part, check=check, note=note,
                nrm=list(nrm) if nrm else [round(c, 5) for c in Za])

FWD = (0, 90, 0)

def layout(config, parts):
    """config 'MLOK' | 'QUAD'; parts = ar15_lib.PARTS (for slot centres and part names).  Returns the socket list."""
    import parts_rear as PR, parts_upper as PU, parts_handguard as PH, parts_lower as PL
    out = []
    up = parts['SM_AR15_UpperReceiver']; rail_rx = list(up.rail_slots)
    hg = parts['SM_AR15_HandguardMLOK' if config == 'MLOK' else 'SM_AR15_HandguardQuad']; hs = hg.slots
    # --- INTEGRATION table
    out.append(S('Muzzle', (0.0, SP.MUZZLE_Y, 0.0), rot=FWD, part='SM_AR15_Birdcage', check='muzzle',
                 note='A2 birdcage tip on the bore axis; muzzle devices mount here with their X forward'))
    out.append(S('Chamber', (0.0, SP.BOLT_FACE + 22.4, 0.0), rot=FWD, part='SM_AR15_Barrel', check='axis',
                 note='bore axis at the middle of a 5.56 case (bolt face + 22.4 mm)'))
    aim = parts['SM_AR15_BUIS'].aim
    out.append(S('Aim', aim, rot=FWD, part='SM_AR15_BUIS', check='aperture',
                 note='rear BUIS aperture on the sight line (co-witness with the A2 post on the quad build)'))
    mid = (rail_rx[0] + rail_rx[-1]) / 2.0; opt_y = min(rail_rx, key=lambda y: abs(y - mid))
    out.append(S('Optic_Socket', (0.0, opt_y, SP.RAIL_TOP), rot=(0, 0, 0), part='SM_AR15_UpperReceiver', check='rail',
                 note='receiver 1913 rail top, centred on the middle slot (an optic recoil lug drops into it); optics Y-forward, pivot at the bottom'))
    if config == 'MLOK':
        bot = hs['mlok_bot_z']; L_ = SP.MLOK_LEN
        gy = min(hs['mlok'], key=lambda y: abs(y - (SP.MLOK_REAR + L_ / 3.0)))
        out.append(S('Grip_Socket', (0.0, gy, bot), rot=FWD, part=hg.name, check='mlok', nrm=(0, 0, -1),
                     note='6 o\'clock M-LOK slot nearest 1/3 of the handguard'))
        ty = max(hs['mlok'])
        out.append(S('TacticalSocket', (-hs['mlok_side_x'], ty, hs['mlok_side_z']), rot=(270, 0, 0), part=hg.name, check='mlok', nrm=(-1, 0, 0),
                     note='3 o\'clock (right) M-LOK slot, front-most'))
        sup_z = (SP.MLOK_TOP + SP.MLOK_BOT) / 2.0; radius = (2 * SP.MLOK_HALF_W + (SP.RAIL_TOP - SP.MLOK_BOT)) / 4.0
    else:
        q0, q1 = SP.QUAD
        gy = min(hs['top'], key=lambda y: abs(y - (q0 + (q1 - q0) / 3.0)))
        out.append(S('Grip_Socket', (0.0, gy, -SP.QUAD_R), rot=FWD, part=hg.name, check='rail_down', nrm=(0, 0, -1),
                     note='bottom (6 o\'clock) rail surface, slot nearest 1/3 of the quad rail'))
        ty = max(hs['top'])
        out.append(S('TacticalSocket', (-SP.QUAD_R, ty, 0.0), rot=(270, 0, 0), part=hg.name, check='rail_right', nrm=(-1, 0, 0),
                     note='right (3 o\'clock) rail surface, front-most slot'))
        sup_z = 0.0; radius = SP.QUAD_R
    out.append(S('MagazineSocket', PR.MAG_SOCKET, rot=(0, 0, 0), part='SM_AR15_LowerReceiver', check='magwell',
                 note='where the top of SM_M4_Mag / SM_AR15_Mag30 sits (their pivot: feed-lip top, 5.8 mm ahead of the top centre)'))
    # stock: butt-plate centre with the stock half extended (position 3)
    bc = PR.STOCK_BUTT                                   # butt-pad face centre (parts_rear, refs/01 outline)
    out.append(S('Stock', (0.0, bc[0], bc[1]), rot=FWD, part='SM_AR15_Stock', check='surface',
                 note='butt-plate centre, stock at position %d of 0-5 (half extended)' % SP.STOCK_ASSEMBLED))
    out.append(S('Butt', (0.0, bc[0], bc[1]), X=(0, -1, 0), Z=(0, 0, 1), part='SM_AR15_Stock', check='surface',
                 note='butt-plate centre, X out of the plate toward the shoulder (modular-hold branch)'))
    import parts_lower as PLW
    tz = SP.TRIG_FACE[1]; ty = PLW.trig_face_y(tz)                                         # on the finger-face arc (parts_lower.trigger)
    out.append(S('Trigger', (0.0, ty + 0.05, tz), rot=(0, -90, 0), part='SM_AR15_Trigger', check='surface',
                 note='trigger blade face, finger contact point'))
    ej = V((-1.0, -0.28, 0.42)).normalized()
    out.append(S('EjectionSocket', (-SP.LOWER_HALF_W - 0.6, -60.0, 4.2), X=tuple(ej), Z=(0, 0, 1), part='SM_AR15_UpperReceiver', check='port',
                 note='ejection port centre; X = ejection direction (right, slightly up and back)'))
    # grip cylinders (Tools/Hands convention: X = cylinder axis toward the thumb, Y = side the hand comes from,
    # scale.X = radius cm, scale.Y = half length cm)
    import numpy as np
    gax = V((0.0, -PL.GRIP_AXIS[0], -PL.GRIP_AXIS[1])).normalized()            # up the grip (toward the thumb)
    t0, t1 = 0.10, 0.80
    fa, ra = PL._at_height(PL.FRONT, t0), PL._at_height(PL.REAR, t0); fb, rb = PL._at_height(PL.FRONT, t1), PL._at_height(PL.REAR, t1)
    ca = (fa + ra) / 2.0; cb = (fb + rb) / 2.0; gc = (ca + cb) / 2.0
    half_len = float(np.linalg.norm(ca - cb)) / 2.0
    grip_r = (float(np.linalg.norm(fa - ra)) + float(np.linalg.norm(fb - rb))) / 4.0 * 0.92
    hand_side = V((-0.45, -0.89, 0.0))
    out.append(S('GripCyl_R', (0.0, gc[0], gc[1]), X=tuple(gax), Z=tuple(gax.cross(hand_side.normalized()).normalized()),
                 scale=(round(grip_r / 10, 3), round(half_len / 10, 3), 1.0), part='SM_AR15_Grip', check='inside',
                 note='pistol-grip cylinder fitted to the A2 grip (heights 10-80 %)'))
    gl_side = V((0.55, 0.0, -0.83)).normalized()
    out.append(S('GripCyl_L', (0.0, gy, sup_z), X=(0, 1, 0), Z=tuple(V((0, 1, 0)).cross(gl_side)),
                 scale=(round(radius / 10, 3), 5.0, 1.0), part=hg.name, check='inside',
                 note='support-hand cylinder on the handguard at the Grip_Socket station; thumb forward, hand from the left-below'))
    out.append(S('RightHandSocket', (0.0, gc[0], gc[1]), X=tuple(gax), Z=(0, 0, 1), part='SM_AR15_Grip', check='inside', note='legacy: pistol-grip centre'))
    out.append(S('LeftHandSocket', (0.0, gy, sup_z - radius), rot=FWD, part=hg.name, check=None, note='legacy: AI left-hand target under the handguard'))
    # modular-hold branch: support seeded from M4Tactical's HandPose_L (16.49, 127.99, 71.02), moved to our handguard station
    m4t_grip_y = 35.3; our_grip_y = g2f((0, gy, 0))[1]
    sd = (43.4, (30.93 + (our_grip_y - m4t_grip_y)) * 10 - SP.G2F[1], 52.4 - SP.G2F[2])
    out.append(S('Support_Default', sd, rot=(16.49, 127.99, 71.02), tag='RailWrap:%.1f' % (2 * radius / 10), part=hg.name, check=None,
                 note='hand_l bone frame on the bare handguard, SEEDED from M4Tactical HandPose_L and shifted to this station: re-solve with Tools/Hands'))
    out.append(S('Eye', (0.0, aim[1] - 75.0, aim[2]), rot=FWD, part=None, check=None, note='iron-sight eye point 75 mm behind the rear aperture'))
    # interaction points (X = the press / pull direction)
    my, mz = SP.MAGCATCH
    out.append(S('MagRelease', (-16.3, my, mz), X=(1, 0, 0), Z=(0, 0, 1), part='SM_AR15_MagCatch', check='surface', note='button face; X = press direction'))
    out.append(S('BoltCatch', (17.6, -87.75, -3.6), X=(-1, 0, 0), Z=(0, 0, 1), part='SM_AR15_BoltCatch', check='surface', note='paddle face; X = press direction'))
    out.append(S('ChargingHandle', (13.0, SP.UPPER_REAR - 6.3, 28.6), X=(0, -1, 0), Z=(0, 0, 1), part='SM_AR15_ChargingHandle', check='surface',
                 note='latch on the left wing; X = pull direction'))
    sy, sz = SP.SELECTOR
    out.append(S('Selector', (SP.LOWER_HALF_W + 0.9 + 3.4, sy + 19.0, sz), X=(0, 0, 1), Z=(1, 0, 0), part='SM_AR15_Selector', check='surface',
                 note='lever tip at SAFE; X = swing direction toward SEMI'))
    fd = PU.FA_DIR; fk = PU.FA_REAR + fd * PU.FA_KNOB_A
    out.append(S('ForwardAssist', tuple(fk), X=tuple(fd), Z=(0, 0, 1), part='SM_AR15_ForwardAssist', check='surface', note='knob face; X = push direction'))
    # rail system: Rail_Top_NN over receiver + handguard top rail, numbered from the rear
    tops = [(y, 'SM_AR15_UpperReceiver', SP.RAIL_TOP) for y in rail_rx] + [(y, hg.name, hs['rail_top_z']) for y in hs['top']]
    import parts_rear as PR2
    for i, (y, pn, z) in enumerate(sorted(tops)):
        occ = PR2.BUIS_BASE[0] - 2.0 < y < PR2.BUIS_BASE[1] + 2.0
        out.append(S('Rail_Top_%02d' % (i + 1), (0.0, y, z), rot=FWD, part=pn, check=None if occ else 'rail',
                     note='under the BUIS base (occupied)' if occ else ''))
    if config == 'MLOK':
        for k, y in enumerate(sorted(hs['mlok'])):
            out.append(S('Mlok_9_%02d' % (k + 1), (hs['mlok_side_x'], y, hs['mlok_side_z']), X=(0, 1, 0), Z=(1, 0, 0), part=hg.name, check='mlok'))
            out.append(S('Mlok_3_%02d' % (k + 1), (-hs['mlok_side_x'], y, hs['mlok_side_z']), X=(0, 1, 0), Z=(-1, 0, 0), part=hg.name, check='mlok'))
            out.append(S('Mlok_6_%02d' % (k + 1), (0.0, y, hs['mlok_bot_z']), X=(0, 1, 0), Z=(0, 0, -1), part=hg.name, check='mlok'))
    else:
        for k, y in enumerate(sorted(hs['top'])):
            out.append(S('Rail_9_%02d' % (k + 1), (SP.QUAD_R, y, 0.0), X=(0, 1, 0), Z=(1, 0, 0), part=hg.name, check='rail_left'))
            out.append(S('Rail_3_%02d' % (k + 1), (-SP.QUAD_R, y, 0.0), X=(0, 1, 0), Z=(-1, 0, 0), part=hg.name, check='rail_right'))
            out.append(S('Rail_6_%02d' % (k + 1), (0.0, y, -SP.QUAD_R), X=(0, 1, 0), Z=(0, 0, -1), part=hg.name, check='rail_down'))
    return out
