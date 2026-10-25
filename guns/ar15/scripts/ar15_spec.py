"""ar15_spec.py - every dimension of the modular AR-15 kit in ONE place (no Blender import; usable from system Python).

Frames
  G (modelling frame): millimetres, UE axes: +X = the gun's LEFT, +Y = muzzle, +Z = up.
     Origin = the bore axis at the upper receiver's FRONT FACE (where the handguard butts).
  F (game frame, INTEGRATION.md): centimetres, same axes, origin near the pistol-grip front like M4Tactical:
     F = (G + G2F) / 10.   G2F puts the bore at z 12.14 cm (M4Tactical bore line) and the trigger-blade face at y 5.85 cm
     (M4Tactical's measured blade, Docs/Plan_FPHands_2026-09-27.md: y 6.0-6.5, pad 5.75).
  Blender scene (exports, renders, .blend): metres, TRUE-HANDED: Blender (x, y, z) = (F.x, -F.y, F.z) / 100
     (the UE Y mirror is baked into the data, as in Tools/bpy/station_props: UE imports the FBX as F).

Calibration (Docs/AR15_BUILD.md has the full table)
  refs/11_freefloat_handguard.jpg (left side, 2687 px): M-LOK pitch 123.13 px (autocorrelation of the 9 o'clock row)
     -> 0.3249 mm/px on the handguard skin, 0.328 mm/px used for the receiver side (perspective, 1 %),
     0.330 at the centre plane; bore tilt 0.81 deg (barrel centre at the handguard front vs castle-nut centre).
  refs/01_M4A1_flattop.jpg (right side, 1033 px): Picatinny lug period 12.50 px on the top rail (centre plane)
     -> 0.801 mm/px; 12.90 px on the near side rail (0.776 mm/px, 3 % perspective).
  Both agree on the pins (pivot / takedown 17.3 mm under the bore, 165 mm apart), hammer / trigger pins 21.6 mm apart
  (spec 0.84 in = 21.3), rail top 30.4 mm over the bore (spec ~1.16-1.2 in).
"""

# ---------------------------------------------------------------- frame offset (G mm -> F mm)
G2F = (0.0, 154.5, 121.4)

def g2f_cm(p):
    """G point (mm) -> F point (cm)"""
    return ((p[0] + G2F[0]) / 10.0, (p[1] + G2F[1]) / 10.0, (p[2] + G2F[2]) / 10.0)

# ---------------------------------------------------------------- material slots (the contract names)
SLOTS = ['Receiver', 'Steel', 'BCG', 'Polymer', 'Handguard']
# pass 3: a sixth slot for the brass cartridge only (SM_AR15_MagRound and SM_AR15_Mag30_Loaded); every other mesh keeps the five
ALL_SLOTS = SLOTS + ['Brass']
BRASS_MESHES = ('SM_AR15_MagRound', 'SM_AR15_Mag30_Loaded')

# ---------------------------------------------------------------- receiver datum lines (G, mm)
RAIL_TOP = 30.4            # Picatinny top over the bore (receiver and handguards are co-planar)
PARTING = -9.0             # upper / lower parting line
UPPER_FRONT = 0.0
UPPER_REAR = -190.0
RING_LEN = 13.5            # threaded front ring of the upper (1.25-18), hidden under the barrel nut
RING_OD = 31.75
PIN_Z = -17.3              # pivot + takedown pin height
PIVOT_Y = -4.9
TAKEDOWN_Y = -169.9
PIN_D = 6.35               # 0.250 in
HAMMER_PIN = (-98.1, -26.8)   # (Y, Z)
TRIGGER_PIN = (-119.7, -35.0)
FCG_PIN_D = 3.91           # 0.154 in
SELECTOR = (-148.6, -32.0)
SELECTOR_D = 9.5
MAGCATCH = (-84.6, -31.6)
TRIG_FACE = (-118.9, -62.9)   # finger contact on the blade's front face (pass 4b: blade under the trigger pin, refs 05/06; was -95.8)

# lower receiver
LOWER_HALF_W = 14.0        # body half-width (FCG area); the upper meets it flush
MAGWELL_HALF_W = 15.4      # magwell side walls
MAGWELL_FLARE_HALF_W = 17.6
MAGWELL_FRONT = -9.5       # outer front face
MAGWELL_REAR = -78.4       # outer rear (meets the guard front ear)
MAG_IN_FRONT = -12.0       # inner opening (64.5 mm long, 22.8 wide)
MAG_IN_REAR = -76.5
MAG_IN_HALF_W = 11.4
MAGWELL_BOT_FRONT = -62.8
MAGWELL_BOT_REAR = -71.5
LOWER_BOT = -49.8          # underside at the trigger guard opening / grip mount
GUARD_BOT = -81.1
GUARD_FRONT_PIN = (-81.0, -73.9)
GUARD_REAR_PIN = (-131.5, -73.2)
TOWER_FRONT = -190.5
TOWER_REAR = -200.0
TOWER_OD = 38.0
ENDPLATE = (-200.0, -203.0)
CASTLE = (-203.0, -212.5)
CASTLE_OD = 35.3
BUFFER_OD = 29.3           # mil-spec carbine receiver extension (1.148 in)
BUFFER_REAR = -365.0

# ---------------------------------------------------------------- barrel (SOCOM / M4A1 profile, refs/15 svg 'M4A1' group, 100 px/in)
BOLT_FACE = 0.2
def svg_y(x):
    """svg x (px, 100 px/in, barrel-extension rear at x=81) -> G Y (mm); bolt face 11.8 mm into the extension"""
    return BOLT_FACE - 11.8 + (x - 81.0) * 0.254
BARREL_PROFILE = [  # (Y, diameter) stations, rear to front; steps are written as two stations at the same Y
    (svg_y(81.0), 25.3), (svg_y(180.0), 25.3),          # barrel extension (inside the upper)
    (svg_y(180.0), 29.7), (svg_y(193.1), 29.7),         # indexing flange
    (svg_y(193.1), 24.9), (svg_y(255.6), 24.9),         # chamber section (under the barrel nut)
    (svg_y(330.6), 21.4), (svg_y(868.1), 21.4),         # SOCOM section under the handguard (0.843 in)
    (svg_y(868.1), 19.05), (svg_y(1061.8), 19.05),      # gas block / FSB journal (0.750 in)
    (svg_y(1061.8), 18.8), (svg_y(1199.3), 18.8),
    (svg_y(1224.3), 15.5), (svg_y(1305.6), 15.5),       # M203 mounting cut (0.61 in), chamfered rear, square front
    (svg_y(1305.6), 18.8), (svg_y(1455.6), 18.8),
    (svg_y(1455.6), 17.8), (svg_y(1518.1), 17.8),       # muzzle shoulder
    (svg_y(1518.1), 12.7), (svg_y(1580.6), 12.7),       # 1/2-28 thread
]
JOURNAL = (svg_y(868.1), svg_y(1061.8))   # 188.4 .. 237.6
BARREL_END = svg_y(1580.6)                # 369.4  (bolt face + 369.2 = 14.5 in)
THREAD_SHOULDER = svg_y(1518.1)           # 353.5
BIRDCAGE_LEN = 46.0                       # A2 birdcage, measured on refs/01 (58 px x 0.801)
MUZZLE_Y = THREAD_SHOULDER + BIRDCAGE_LEN # 399.5
BARREL16_EXT = 38.1                       # pass 3: 16 in barrel = the 14.5 in profile with a 1.5 in longer muzzle section
BARREL16_END = BARREL_END + BARREL16_EXT  # 407.5
THREAD_SHOULDER16 = THREAD_SHOULDER + BARREL16_EXT
MUZZLE16_Y = MUZZLE_Y + BARREL16_EXT      # A2 tip on the 16 in barrel
GAS_Z = 15.5                              # gas tube centre over the bore
GAS_PORT_Y = 203.0
FSB = (191.0, 239.0)                      # A2 front sight base barrel ring
LPGB = (194.0, 216.0)                     # low-profile gas block
SIGHT_Z = 62.5                            # A2 front post tip = BUIS aperture centre (refs/01: ear apex 65.0, post 2.5 below)

# ---------------------------------------------------------------- handguards
MLOK_LEN = 381.0                          # 15 in, from the upper front face
MLOK_REAR = 0.6
MLOK_HALF_W = 20.5
MLOK_TOP = 24.4                           # body top face; the integral 1913 rail rises to RAIL_TOP
MLOK_BOT = -23.0
MLOK_WALL = 2.8
MLOK_SLOT = (32.0, 7.0, 2.4)              # length, width, corner radius
MLOK_PITCH = 40.0
QUAD = (30.0, 188.5)                      # M4 RAS between the delta ring and the FSB cap
QUAD_R = RAIL_TOP                         # rail tops at 30.4 from the bore on all four sides
DELTA = (5.0, 28.5)

# ---------------------------------------------------------------- Picatinny MIL-STD-1913
PIC_W = 21.2          # across the dovetail edges (0.835 in)
PIC_TOP_W = 15.67     # top flat (0.617 in)
PIC_SLOT_W = 5.23
PIC_PITCH = 10.01
PIC_SLOT_D = 3.0

# ---------------------------------------------------------------- stock / grip (refs/01, 0.80 mm/px, collapsed stock)
STOCK_LEN = 169.6
STOCK_FRONT = -213.0      # collapsed (position 0) front face
STOCK_POS = [0.0, 16.3, 32.6, 48.9, 65.2, 81.5]   # 6 positions, 81.5 mm of travel (838 - 757 mm)
STOCK_ASSEMBLED = 3       # position used in the static meshes ('half extended')
GRIP_RAKE = 21.0          # deg from vertical (front strap 19, rear 31 on refs/01)

# ---------------------------------------------------------------- magazine (SM_M4_Mag-compatible pivot)
MAG_TOP_Z = -13.0         # feed lips just under the carrier (carrier bottom -12.45 at the magwell)
MAG_TOP_LEN = 64.5
MAG_PIVOT_FWD = 5.8       # SM_M4_Mag pivot is 5.8 mm ahead of the mag top's centre (its bbox Y centre)
MAG_W = 22.4

# ---------------------------------------------------------------- M4Tactical anchors (INTEGRATION.md, F cm)
M4T = {
    'Trigger (socket, on its grip front)': (-0.04, 2.54, 0.19),
    'Trigger blade (measured)': (0.0, 6.25, 5.45),
    'GripCyl_R': (0.03, -2.46, -0.39),
    'bore line z': (None, None, 12.14),
    'MagazineSocket': (-0.18, 14.77, 8.04),
    'Optic_Socket': (0.0, 6.75, 16.45),
    'Grip_Socket': (-0.53, 35.3, 8.59),
    'mag release': (-2.0, 9.3, 6.6),
    'bolt catch': (3.0, 9.5, 9.0),
    'Muzzle': (-0.80, 58.28, 12.14),
    'Stock': (0.37, -27.30, 11.29),
}
