"""Every number and registry for Cortlandt Station. Pure data — no bpy, no logic.
Units: metres. X runs along the platform, Y across, Z up. Platform top = 0."""

# --- vertical stack -----------------------------------------------------------------
Z_PLATFORM = 0.0
Z_MEZZ = 5.2
Z_STREET = 10.0          # sidewalk / plaza level
ROAD_DROP = 0.15         # roadway sits below the curb
PLATFORM_CEIL = 4.3
MEZZ_CEIL = 8.6

TREAD = 0.28             # NYC ~11 in
LANDING = 1.5
STREET_STAIR_RISERS = 27
PLATFORM_STAIR_RISERS = 29

# --- platform level -------------------------------------------------------------------
PLATFORM_LEN = 70.0
PLATFORM_W = 9.0
TRACK_W = 4.5
TRACKBED_Z = -1.1
STATION_HALF_LEN = 45.0          # station box; tunnels continue past it
TUNNEL_HALF_LEN = 85.0
TUNNEL_CEIL = 4.0
COLUMN_PITCH = 4.572             # 15 ft
COLUMN_ROW_Y = 3.3
COLUMN_COUNT_PER_ROW = 15        # k = -7..7
EDGE_STRIP = 0.6                 # yellow warning strip

PLATFORM_STAIRS = [              # top nosing (x,y) at mezz level, descend +x
    dict(name="PlatformStair_A", top=(7.0, 0.0), width=2.4),
    dict(name="PlatformStair_B", top=(21.0, 0.0), width=2.4),
]

TRAIN_CAR = dict(length=15.5, width=2.7, gap=0.9, floor=0.0, roof=3.0, doors_per_side=4, door_w=1.27)
TRAIN_A = dict(track="A", cars=4, start_x=-31.0, kit="SM_TrainCar_R142")
TRAIN_B = dict(track="B", cars=3, start_x=-26.0, kit="SM_TrainCar_Derelict")

# --- mezzanine ----------------------------------------------------------------------
MEZZ_RECT = (-42.0, -13.0, 40.0, 13.0)
FARE_LINE_X = -22.0
ROW_X = (-22.0, 6.0)
ROW_HALF_W = 3.3                 # corridor = column rows
STREET_STAIRS = [                # top nosing at street level, descend +x into the unpaid hall
    dict(name="StreetStair_North", top=(-40.0, 8.5), width=1.8, globe="SM_EntranceGlobe_Green"),
    dict(name="StreetStair_South", top=(-40.0, -8.5), width=1.8, globe="SM_EntranceGlobe_Red"),
]
# The Row: old shop → new use. side +1 = north of corridor
ROW_SHOPS = [
    dict(key="trade_post", was="Newsstand",   side=+1, x=(-22.0, -8.0), npc="Trader"),
    dict(key="mechanic",   was="Locksmith",   side=+1, x=(-8.0, 6.0),   npc="Mechanic"),
    dict(key="gunsmith",   was="Shoe Repair", side=-1, x=(-22.0, -8.0), npc="Gunsmith"),
    dict(key="infirmary",  was="Barber",      side=-1, x=(-8.0, 6.0),   npc="Medic"),
]
# Commons zones (rects in mezz plan) — kit pieces scattered per zone by layout_mezz
COMMONS = dict(
    bunks=(26.0, 5.0, 39.5, 12.5),
    galley=(8.0, 7.0, 20.0, 12.5),
    market=(8.0, -2.0, 20.0, 2.0),
    stash=(8.0, -12.5, 20.0, -10.5),
    workshop=(21.0, -12.5, 31.0, -6.0),
    black_market=(32.0, -13.0, 40.0, -5.0),
    raid_board=(33.5, 0.0),
)

# --- street -------------------------------------------------------------------------
AVENUE_HALF = 6.0                # Greenwich St, curb to curb 12 m
SIDEWALK_AVE = 4.5
CROSS_X = (-50.0, 50.0)          # Cortlandt St, Dey St
CROSS_HALF = 5.0
SIDEWALK_CROSS = 4.0
STREET_BOUNDS = (-100.0, -62.0, 100.0, 62.0)
BARRICADE_X = 96.0
BARRICADE_Y = 58.0
LOT_DEPTH = 15.0
STOREFRONT_COUNT = 84
INTERIOR_COUNT = 18
WALKUP_COUNT = 3
WALKUP_W = 7.5
WALKUP_FLOORS = 5
WALKUP_FLOOR_H = 3.0
GROUND_FLOOR_H = 4.5
UPPER_FLOOR_H = 3.2
PLAZA_BLOCK = "C_N"
SEED = 1782

LOOT_TARGET = 110                # interiors 18*4 + walkups 3*8 + street rest
LOOT_PER_INTERIOR = 4
LOOT_PER_WALKUP = 8
ZOMBIE_SPAWNERS = 12

# --- materials (slot name → blockout RGBA; UE material instances bind by slot name) --
MATERIALS = {
    "M_Concrete":       (0.42, 0.42, 0.40, 1),
    "M_Tile_White":     (0.85, 0.84, 0.78, 1),
    "M_Tile_Trim":      (0.30, 0.45, 0.35, 1),
    "M_Terrazzo":       (0.55, 0.52, 0.47, 1),
    "M_Platform_Edge":  (0.85, 0.65, 0.05, 1),
    "M_Trackbed":       (0.12, 0.10, 0.09, 1),
    "M_Rail":           (0.35, 0.30, 0.27, 1),
    "M_Steel_Painted":  (0.18, 0.25, 0.22, 1),
    "M_Steel_Bare":     (0.50, 0.50, 0.52, 1),
    "M_Asphalt":        (0.10, 0.10, 0.11, 1),
    "M_Sidewalk":       (0.55, 0.54, 0.51, 1),
    "M_Brick":          (0.45, 0.22, 0.15, 1),
    "M_Facade_Stone":   (0.62, 0.58, 0.52, 1),
    "M_Glass_Dark":     (0.05, 0.07, 0.08, 1),
    "M_Wood":           (0.40, 0.27, 0.16, 1),
    "M_Sandbag":        (0.52, 0.47, 0.35, 1),
    "M_Fabric":         (0.25, 0.30, 0.22, 1),
    "M_Train_Body":     (0.62, 0.64, 0.66, 1),
    "M_Train_Rust":     (0.38, 0.22, 0.12, 1),
    "M_Globe_Green":    (0.10, 0.80, 0.25, 1),
    "M_Globe_Red":      (0.85, 0.10, 0.08, 1),
    "M_Light_Emissive": (1.00, 0.95, 0.85, 1),
    "M_Barricade":      (0.70, 0.70, 0.68, 1),
    "M_Planter":        (0.20, 0.30, 0.15, 1),
}
EMISSIVE = {"M_Light_Emissive": 8.0, "M_Globe_Green": 4.0, "M_Globe_Red": 4.0}
