"""Draw layout plans straight from spec.py → SVG. Pure python (no bpy, no deps).
Usage: python -m core.plan_svg <out_dir>"""
import sys, os, math
from . import spec as S

BG, INK, DIM, WELL = "#14161a", "#e8e6e1", "#8a8f98", "#f5c542"
ROOM = {"gate": "#5a3a2a", "watch_post": "#a33", "landing_sq": "#2b3138", "stash": "#2f4f6f",
        "trade_post": "#8a6d2a", "gunsmith": "#7a2a2a", "mechanic": "#8a4f1f", "departure": "#2a5a4a",
        "infirmary": "#3f6f7f", "workshop": "#4a5a7a", "galley": "#7a5a3a", "bunks": "#4a2f3f",
        "black_market": "#4a2a6a", "staff_hall": "#333", "generator": "#5a5a2a"}


class Svg:
    def __init__(s, x0, y0, x1, y1, ppm, title):
        s.x0, s.y1, s.ppm, s.pad = x0, y1, ppm, 40
        s.w, s.h = (x1 - x0) * ppm + 2 * s.pad, (y1 - y0) * ppm + 2 * s.pad + 30
        s.out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.w:.0f}" height="{s.h:.0f}" '
                 f'font-family="Helvetica,Arial,sans-serif"><rect width="100%" height="100%" fill="{BG}"/>',
                 f'<text x="{s.pad}" y="28" fill="{INK}" font-size="18" font-weight="bold">{title}</text>']

    def p(s, x, y):  # world → px (north up)
        return s.pad + (x - s.x0) * s.ppm, s.pad + 30 + (s.y1 - y) * s.ppm

    def rect(s, r, fill, stroke="none", sw=1, op=1, dash=None):
        (ax, ay), (bx, by) = s.p(r[0], r[3]), s.p(r[2], r[1])
        d = f' stroke-dasharray="{dash}"' if dash else ""
        s.out.append(f'<rect x="{ax:.1f}" y="{ay:.1f}" width="{bx-ax:.1f}" height="{by-ay:.1f}" fill="{fill}" '
                     f'fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def poly(s, pts, stroke, sw=2, fill="none", dash=None, op=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        q = " ".join(f"{a:.1f},{b:.1f}" for a, b in (s.p(*pt) for pt in pts))
        s.out.append(f'<polyline points="{q}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(s, x, y, t, size=11, fill=INK, anchor="middle", bold=False):
        px, py = s.p(x, y)
        w = ' font-weight="bold"' if bold else ""
        for i, line in enumerate(t.split("\n")):
            s.out.append(f'<text x="{px:.1f}" y="{py + i*(size+2):.1f}" fill="{fill}" font-size="{size}" '
                         f'text-anchor="{anchor}"{w}>{line}</text>')

    def stair(s, top, d, width, risers):
        run = (risers - 2) * S.TREAD + S.LANDING
        x, y = top
        px, py = -d[1], d[0]
        a = (x + px * width / 2, y + py * width / 2)
        b = (x - px * width / 2 + d[0] * run, y - py * width / 2 + d[1] * run)
        r = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        s.rect(r, "#c9c3b8", INK, 1, 0.9)
        for i in range(0, int(run / S.TREAD), 2):  # tread hatching
            t = i * S.TREAD
            s.poly([(x + d[0] * t + px * width / 2, y + d[1] * t + py * width / 2),
                    (x + d[0] * t - px * width / 2, y + d[1] * t - py * width / 2)], "#6b665e", 1)
        s.poly([(x + d[0] * 0.5, y), (x + d[0] * (run - 0.5), y)], "#222", 2)  # walk-down arrow
        tip = (x + d[0] * (run - 0.5), y)
        s.poly([(tip[0] - d[0] * 1.2 + px * 0.6, tip[1] + py * 0.6), tip,
                (tip[0] - d[0] * 1.2 - px * 0.6, tip[1] - py * 0.6)], "#222", 2)
        return run

    def scale_bar(s, x, y, m=10):
        s.poly([(x, y), (x + m, y)], INK, 3)
        s.text(x + m / 2, y - 1.2, f"{m} m", 10)

    def save(s, path):
        open(path, "w").write("\n".join(s.out + ["</svg>"]))


def mezz(out):
    g = Svg(-46, -14, 46, 14, 13, "MEZZANINE  z 520  — the Arcade (safe hub)")
    g.rect(S.MEZZ, "#1d2126", DIM, 2)
    for k, r in S.MEZZ_ROOMS.items():
        g.rect(r["rect"], ROOM[k], "#000", 1, 0.85)
        x0, y0, x1, y1 = r["rect"]
        if k == "gate":
            g.text((x0 + x1) / 2, 4.6, "GATE", 12, bold=True)
        elif k != "watch_post":
            g.text((x0 + x1) / 2, (y0 + y1) / 2 + 0.4, f"{k.replace('_', ' ').upper()}\nwas: {r['was']}", 10)
        if x0 >= S.FARE_LINE_X and x1 <= S.CONCOURSE[2]:      # glass shopfront line
            fy = S.CONCOURSE[3] if y0 >= 0 else S.CONCOURSE[1]
            g.poly([(x0 + 0.5, fy), (x1 - 0.5, fy)], "#9fd3e6", 3)
    g.text(-35, -3.0, "WATCH POST\n(token booth)", 9)
    g.rect(S.CONCOURSE, "#3a3d42", "none")
    g.rect(S.NODE, "#3a3d42", "none")
    c = S.COMPASS_ROSE
    cx, cy = g.p(*c["center"])
    g.out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{c["r"]*g.ppm:.1f}" fill="#d9d6cf" fill-opacity="0.35" stroke="#d9d6cf"/>')
    for a_ in range(8):
        t = a_ * math.pi / 4
        rr = c["r"] if a_ % 2 == 0 else c["r"] * 0.55
        g.poly([c["center"], (c["center"][0] + rr * math.sin(t), c["center"][1] + rr * math.cos(t))], "#d9d6cf", 2)
    g.text(2, 10.6, "RAID BOARD · muster", 9, "#7fd17f", bold=True)
    g.text(2, 7.4, "THE NODE", 12, bold=True)
    g.text(-17.25, 1.6, "MARKET (glass kiosks)", 10, "#9fd3e6")
    for kx, ky in S.CENTER_KIOSKS:
        g.rect((kx - 1.2, ky - 0.6, kx + 1.2, ky + 0.6), "#9fd3e6", "#000", 1, 0.7)
    for k in range(-10, 11):
        x = k * S.COLUMN_PITCH
        if S.FARE_LINE_X < x < S.CONCOURSE[2]:
            for yy in (-S.CONCOURSE_COLUMNS_Y, S.CONCOURSE_COLUMNS_Y):
                g.rect((x - 0.25, yy - 0.25, x + 0.25, yy + 0.25), "#f2f2f2")
    for st in S.PLATFORM_STAIRS:
        run = g.stair(st["top"], st["dir"], st["width"], S.PLATFORM_STAIR_RISERS)
        x0, x1 = sorted((st["top"][0], st["top"][0] + st["dir"][0] * run))
        w = st["width"] / 2 + 0.3
        far, near = (x1, x0) if st["dir"][0] > 0 else (x0, x1)    # railing on 3 sides, open at the top
        g.poly([(near, w), (far, w), (far, -w), (near, -w)], "#e0b020", 3)
        g.text((x0 + x1) / 2, -w - 1.0, f"{st['name'].replace('Stair_', '').upper()} STAIR down", 9, "#e0b020")
    for st in S.STREET_STAIRS:
        g.stair(st["top"], st["dir"], st["width"], S.STREET_STAIR_RISERS)
        g.text(st["top"][0] + 4, st["top"][1] + (1.5 if st["top"][1] > 0 else -2.2),
               f"from street ({st['globe']}, {st['state']})", 9, DIM)
    g.poly([(S.FARE_LINE_X, S.MEZZ[1]), (S.FARE_LINE_X, S.CONCOURSE[1])], INK, 4)
    g.poly([(S.FARE_LINE_X, S.CONCOURSE[3]), (S.FARE_LINE_X, S.MEZZ[3])], INK, 4)
    for i in range(6):
        y = -3.3 + i * 1.32
        g.rect((S.FARE_LINE_X - 0.4, y - 0.15, S.FARE_LINE_X + 0.4, y + 0.15), INK)
    g.text(S.FARE_LINE_X - 1.0, 4.6, "turnstiles\n+ shutter", 9, INK, "end")
    g.text(38, -2.6, "NO ENTRY", 9, "#e58f8f")
    g.scale_bar(-44, -13.4)
    g.save(os.path.join(out, "plan_mezzanine.svg"))


def platform(out):
    g = Svg(-88, -11, 88, 11, 11, "PLATFORM  z 0  — the way out")
    g.rect((-S.TUNNEL_HALF_LEN, -9.6, S.TUNNEL_HALF_LEN, 9.6), "#0c0d0f", DIM, 1)
    g.rect((-S.STATION_HALF_LEN, -9.3, S.STATION_HALF_LEN, 9.3), "#1d2126", DIM, 2)
    for t, c in ((S.TRACK_A, "#2a2522"), (S.TRACK_B, "#2a2522")):
        g.rect(t, c)
        for yy in (t[1] + 1.5, t[3] - 1.5):
            g.poly([(t[0], yy), (t[2], yy)], "#5a5048", 1)
    g.rect(S.PLATFORM, "#6c6a64", INK, 1)
    for yy in (S.PLATFORM[1] + 0.3, S.PLATFORM[3] - 0.3):
        g.poly([(S.PLATFORM[0], yy), (S.PLATFORM[2], yy)], "#e0b020", 4)
    for k in range(-7, 8):
        for yy in (-S.COLUMN_ROW_Y, S.COLUMN_ROW_Y):
            g.rect((k * S.COLUMN_PITCH - 0.2, yy - 0.2, k * S.COLUMN_PITCH + 0.2, yy + 0.2), "#111")
    car = S.TRAIN_CAR
    for tr, ty, col, lab in ((S.TRAIN_A, -6.75, "#9aa3ad", "LIVE TRAIN"), (S.TRAIN_B, 6.75, "#6b4a33", "DERELICT")):
        for i in range(tr["cars"]):
            x = tr["start_x"] + i * (car["length"] + car["gap"])
            g.rect((x, ty - car["width"] / 2, x + car["length"], ty + car["width"] / 2), col, "#000", 1)
        g.text(tr["start_x"] + 8, ty - 0.5, lab, 10, "#000", bold=True)
    for st in S.PLATFORM_STAIRS:
        top = st["top"]
        run = (S.PLATFORM_STAIR_RISERS - 2) * S.TREAD + S.LANDING
        g.rect((min(top[0], top[0] + st["dir"][0] * run), -st["width"] / 2,
                max(top[0], top[0] + st["dir"][0] * run), st["width"] / 2), "#c9c3b8", INK, 1)
        g.text(top[0] + st["dir"][0] * run / 2, -st["width"] / 2 - 0.9, "stair up", 9)
    for k, z in S.PLATFORM_ZONES.items():
        g.rect(z["rect"], "#7fd17f" if k == "boarding" else "#d18f3f", "none", 0, 0.25)
    g.text(-32, 2.2, "ROUTE\nBOARD", 9)
    g.text(57, 6.2, "TEST RANGE  (Track B tunnel)  10 · 25 · 50 m", 10, "#f0b060")
    for d in (45, 60, 85):
        g.rect((d - 0.15, 5, d + 0.15, 8.5), "#f0b060")
    g.text(-65, -7.2, "← tunnel to raids (loading screen)", 10, DIM)
    g.scale_bar(-86, -10.6)
    g.save(os.path.join(out, "plan_platform.svg"))


def street(out):
    g = Svg(-102, -66, 102, 64, 6, "STREET  z 1000  — danger zone + tutorial")
    g.rect(S.STREET_BOUNDS, "#2c2a28")
    road = "#1a1a1c"
    g.rect((S.STREET_BOUNDS[0], -S.AVENUE_HALF, S.STREET_BOUNDS[2], S.AVENUE_HALF), road)
    for c in S.CROSS_STREETS:
        g.rect((c["x"] - S.CROSS_HALF, S.STREET_BOUNDS[1], c["x"] + S.CROSS_HALF, S.STREET_BOUNDS[3]), road)
        g.text(c["x"], 50, c["name"].upper(), 10, DIM)
    g.text(-80, 0.6, "GREENWICH ST", 11, DIM, bold=True)
    sw = S.AVENUE_HALF + S.SIDEWALK_AVE
    cx = [c["x"] for c in S.CROSS_STREETS]
    edges = [S.STREET_BOUNDS[0], cx[0] - S.CROSS_HALF - S.SIDEWALK_CROSS, cx[0] + S.CROSS_HALF + S.SIDEWALK_CROSS,
             cx[1] - S.CROSS_HALF - S.SIDEWALK_CROSS, cx[1] + S.CROSS_HALF + S.SIDEWALK_CROSS, S.STREET_BOUNDS[2]]
    for x0, x1 in ((edges[0], edges[1]), (edges[2], edges[3]), (edges[4], edges[5])):
        for y0, y1 in ((sw, S.STREET_BOUNDS[3]), (S.STREET_BOUNDS[1], -sw)):
            g.rect((x0, y0, x1, y1), "#5a3328", "#000", 1)
            band = (x0, y0, x1, y0 + S.LOT_DEPTH) if y0 > 0 else (x0, y1 - S.LOT_DEPTH, x1, y1)
            g.rect(band, "#7a4434", "none", 0, 0.9)
    pz = S.STREET_ZONES["plaza"]["rect"]
    g.rect(pz, "#2f4a2a", "#000", 1)
    g.text((pz[0] + pz[2]) / 2, (pz[1] + pz[3]) / 2, "POCKET PLAZA\noverrun FEMA camp", 10)
    ph = S.STREET_ZONES["pharmacy"]["rect"]
    g.rect(ph, "#2a7a4a", "#000", 1)
    g.text((ph[0] + ph[2]) / 2, ph[3] - 4, "CORTLANDT\nDRUGS", 9)
    for r in S.STREET_ZONES["walkups"]["rects"]:
        g.rect(r, "#8a6a4a", "#000", 1)
        g.text((r[0] + r[2]) / 2, (r[1] + r[3]) / 2 + 0.5, "walk-up", 8)
    g.rect(S.MEZZ, "none", WELL, 2, dash="6 5")
    g.text(0, -11.0, "station footprint below", 9, WELL)
    for st in S.STREET_STAIRS:
        g.stair(st["top"], st["dir"], st["width"], S.STREET_STAIR_RISERS)
        g.rect((st["top"][0] - 1.2, st["top"][1] - 1.2, st["top"][0] + 0.2, st["top"][1] + 1.2),
               "#2c2" if st["globe"] == "green" else "#d22")
    sp = S.STREET_ZONES["spawn"]["rect"]
    g.rect(sp, "#3a6aa8", "none", 0, 0.6)
    g.text(-90, -7.8, "START", 10, bold=True)
    g.poly([(-85, 0), (-55, 0), (-46, 4), (-46, 9.5), (-43, 9.5)], "#7fd17f", 3, dash="10 6")
    g.text(-67, -2.8, "tutorial path", 9, "#7fd17f")
    b = S.BARRICADE
    g.poly([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), (b[0], b[1])], "#e04040", 3, dash="4 4")
    for i in range(S.ZOMBIE_SPAWNERS):
        a = i / S.ZOMBIE_SPAWNERS * 2 * math.pi
        x, y = max(-99, min(99, 120 * math.cos(a))), max(-61, min(61, 80 * math.sin(a)))
        g.rect((x - 1, y - 1, x + 1, y + 1), "#e04040")
    g.text(0, -63.4, "zombie fence + spawners (red) — the Tide breaks in at telegraphed points", 10, "#e04040")
    g.scale_bar(-98, -55, 20)
    g.save(os.path.join(out, "plan_street.svg"))


def section(out):
    g = Svg(-50, -3, 46, 12, 12, "SECTION along the station (y = 0, looking north)")
    g.rect((-50, -3, 46, 8.8), "#2a2622")
    g.rect((-45, -1.1, 45, 4.3), "#1d2126")
    g.rect((S.MEZZ[0], 5.2, S.MEZZ[2], 8.8), "#262a30")
    g.rect((S.PLATFORM[0], -1.1, S.PLATFORM[2], 0.0), "#6c6a64")
    g.rect((-50, 8.8, 46, 10.0), "#4a4744", INK, 1)
    run = (S.PLATFORM_STAIR_RISERS - 2) * S.TREAD + S.LANDING
    cuts = sorted(sorted((st["top"][0], st["top"][0] + st["dir"][0] * run)) for st in S.PLATFORM_STAIRS)
    xs = [-45] + [v for c_ in cuts for v in c_] + [45]
    for i in range(0, len(xs), 2):
        g.rect((xs[i], 4.3, xs[i + 1], 5.2), "#4a4744", INK, 1)
    for st in S.PLATFORM_STAIRS:
        x, d, z, pts = st["top"][0], st["dir"][0], 5.2, []
        rise = 5.2 / S.PLATFORM_STAIR_RISERS
        for i in range(S.PLATFORM_STAIR_RISERS):
            pts += [(x, z), (x, z - rise)]
            z -= rise
            x += d * (S.LANDING if i == S.PLATFORM_STAIR_RISERS // 2 else S.TREAD)
        g.poly(pts, INK, 2)
    x, z, pts = -42.0, 10.0, []
    rise = 4.8 / S.STREET_STAIR_RISERS
    for i in range(S.STREET_STAIR_RISERS):
        pts += [(x, z), (x, z - rise)]
        z -= rise
        x += S.LANDING if i == S.STREET_STAIR_RISERS // 2 else S.TREAD
    g.poly(pts, "#2c2", 2, dash="4 3")
    g.text(-30, 9.25, "STREET  z 1000", 10, INK, bold=True)
    g.text(-15, 6.8, "MEZZANINE  z 520  (arcade)", 10, INK, bold=True)
    g.text(-30, 1.8, "PLATFORM  z 0", 10, INK, bold=True)
    g.text(-37.5, 11.0, "sidewalk stair (27, y=8.5)", 9, "#2c2")
    g.text(1.5, 6.0, "main stair (29)", 9)
    g.text(28.5, 6.0, "east stair (29)", 9)
    g.text(15, 0.6, "BOARDING", 10, "#7fd17f", bold=True)
    g.rect((S.TRAIN_A["start_x"], -0.8, S.TRAIN_A["start_x"] + 64.7, 3.0), "none", "#9aa3ad", 1, dash="6 4")
    g.text(-25, -2.2, "live train (Track A, behind)", 9, "#9aa3ad")
    g.save(os.path.join(out, "section_station.svg"))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "plans"
    os.makedirs(out, exist_ok=True)
    for f in (street, mezz, platform, section):
        f(out)
    print("wrote", sorted(os.listdir(out)))
