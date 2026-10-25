"""parts.py - G17 Gen5 v4 parts as signed distance functions (G frame, mm) -> high-poly meshes (system python).

usage: python parts.py <h_mm> [parts=frame,slide,barrel,mag] [out=work/high.npz] [--detail]
Each assembly is complete on all sides (they come apart in game): the frame has its magwell, top channel, rails and locking
block; the slide its hollow interior, rail grooves, breech face and front wall; the barrel its chamber, lug and the
guide rod + recoil spring; the magazine its body, feed lips, follower and baseplate; the backstrap its inner face.
Every shell carries a per-vertex 'mat' id (see MAT) used by the bakes."""
import sys, os, time, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sdf as S
import g17v4_spec as G
from PIL import Image, ImageDraw

DETAIL = '--detail' in sys.argv
MAT = dict(polymer=0, steel=1, slide=2, barrel=3, white=4, orange=5, magbody=6, base=7, spring=8, sightpoly=9)
P = np.load(os.path.join(HERE, 'work', 'prof.npz'))
RES = float(P['res']); Y0 = float(P['y0']); Z1 = float(P['z1']); NY = int(P['ny']); NZ = int(P['nz'])
def F2(name, outside=60.0): return S.Field2D(P['d_' + name], Y0, Z1, RES, outside)
dFRAME, dSLIDE, dMAG, dBARREL = F2('frame'), F2('slide'), F2('mag'), F2('barrel')
dRS, dFS, dSHOE, dSAF = F2('rsight'), F2('fsight'), F2('shoe'), F2('safety')

def poly_sdf2(pts_g, res=0.05, pad=6.0):
    """2-D signed distance field of a (y, z) polygon, rasterised (exact to ~res)"""
    from scipy import ndimage
    pts = np.asarray(pts_g, float); y0, z0 = pts.min(0) - pad; y1, z1 = pts.max(0) + pad
    ny, nz = int((y1 - y0) / res) + 1, int((z1 - z0) / res) + 1
    img = Image.new('L', (ny, nz), 0); ImageDraw.Draw(img).polygon([((y - y0) / res, (z1 - z) / res) for y, z in pts], fill=255)
    m = np.asarray(img) > 127
    d = (ndimage.distance_transform_edt(~m) - ndimage.distance_transform_edt(m)) * res + np.where(m, 0.5 * res, -0.5 * res)
    return S.Field2D(d, y0, z1, res, outside=pad)

# =========================================================================== FRAME
def _hw_frame(Y, Z):
    fs = G.front_strap(Z)
    grip = G.GRIP_HW + (G.FLARE_HW - G.GRIP_HW) * S.sstep(-68.0, -76.5, Z)
    hw = S.lerp(G.RECV_HW, grip, S.sstep(18.5, 14.5, Z))
    w_tg = S.sstep(fs + 0.5, fs + 3.5, Y) * S.sstep(13.8, 10.8, Z)
    hw = S.lerp(hw, G.GUARD_HW, w_tg)
    hw = S.lerp(hw, G.DUST_HW, S.sstep(60.0, 64.0, Y) * S.sstep(9.0, 11.5, Z))
    tang = S.lerp(13.2, 9.2, S.sstep(-47.0, -65.0, Y))
    hw = S.lerp(hw, tang, S.sstep(-44.0, -49.0, Y) * S.sstep(8.0, 13.0, Z))
    return hw
def _r_frame(Y, Z):
    fs = G.front_strap(Z); rl = G.rear_line(Z); mid = 0.5 * (fs + rl)
    r = S.lerp(9.0, 7.2, S.sstep(mid - 4.0, mid + 4.0, Y))
    r = S.lerp(1.3, r, S.sstep(17.0, 11.0, Z))
    r = S.lerp(r, 1.9, S.sstep(fs + 0.5, fs + 3.5, Y) * S.sstep(13.8, 10.8, Z))
    r = S.lerp(r, 1.0, S.sstep(60.0, 64.0, Y) * S.sstep(9.0, 11.5, Z))
    r = S.lerp(r, S.lerp(3.2, 2.2, S.sstep(-47.0, -65.0, Y)), S.sstep(-42.0, -47.0, Y) * S.sstep(6.0, 12.0, Z))
    r = np.where(Z > G.ZSB - 1.0, np.minimum(r, 0.6), r)                     # crisp top edges under the slide
    return r
HWF = S.field_from_fn(_hw_frame, -72, 130, -92, 34, 0.1)
RF = S.field_from_fn(_r_frame, -72, 130, -92, 34, 0.1)

def frame_outer(X, Y, Z):
    return S.rinter(dFRAME(Y, Z), np.abs(X) - HWF(Y, Z), RF(Y, Z))

def mag_xs(X, Y, Z, grow=0.0):
    """magazine body cross-section distance (x, s) + raked band; grow inflates it"""
    c = 1.0 / math.sqrt(1 + G.MAG_RAKE ** 2)
    s = (Y - G.mag_rear(Z)) * c; D = (G.mag_front(Z) - G.mag_rear(Z)) * c
    r = np.where(s > 0.5 * D, 5.0, 2.2) + grow
    return S.rect2(X, s, (-G.MAG_HW - grow, -grow), (G.MAG_HW + grow, D + grow), r)

def magwell(X, Y, Z):
    grow = 0.2 + 2.0 * S.sstep(-72.5, -78.6, Z)                            # funnel at the bottom
    return np.maximum(mag_xs(X, Y, Z, grow), S.slab(Z, -95.0, 27.0))

SEAM_REGION = None
def bs_region():
    global SEAM_REGION
    if SEAM_REGION is None:
        sm = G.SEAM; top = sm[0]; bot = sm[-1]
        poly = list(map(tuple, sm)) + [(bot[0] - 12.0, bot[1] - 0.4), (-80.0, bot[1] - 0.6), (-80.0, top[1]), (top[0] - 30.0, top[1])]
        SEAM_REGION = poly_sdf2(poly)
    return SEAM_REGION

def frame_body(X, Y, Z):
    """frame (without backstrap): outer shell minus the cavities"""
    o = frame_outer(X, Y, Z)
    d = S.rdiff(o, magwell(X, Y, Z), 0.5)
    d = S.rdiff(d, S.box(X, Y, Z, (-G.TOPCH_HW, -45.5, 15.5), (G.TOPCH_HW, 62.0, 45.0), 1.0), 0.5)    # fire-control channel
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, G.GUIDE_Z), G.DUSTCH_R, 58.0, 130.0), 0.5)               # recoil spring channel
    d = S.rdiff(d, S.box(X, Y, Z, (-3.7, 19.0, 4.0), (3.7, 35.5, 20.0), 0.5), 0.3)                   # trigger slot
    # backstrap cut: the outer 3 mm of the grip behind the seam (0.24 mm seam gap)
    reg = bs_region()(Y, Z)
    q = np.maximum(-(o + G.BS_THICK), reg - 0.12)
    d = S.rdiff(d, q, 0.35)
    if DETAIL: d = frame_details(d, X, Y, Z)
    return d

# --------------------------------------------------------------------------- frame details (photo positions, G mm)
_XS = None
def XS(Y, Z):
    """outer |x| of the frame side surface at (y, z) (rasterised once, bisection on frame_outer)"""
    global _XS
    if _XS is None:
        res = 0.2; y0, y1, z0, z1 = -68.0, 126.0, -84.0, 31.0
        ys = y0 + (np.arange(int((y1 - y0) / res)) + 0.5) * res; zs = z1 - (np.arange(int((z1 - z0) / res)) + 0.5) * res
        YY, ZZ = np.meshgrid(ys, zs); lo = np.zeros_like(YY); hi = np.full_like(YY, 19.0)
        inside0 = frame_outer(lo, YY, ZZ) < 0
        for _ in range(28):
            m = 0.5 * (lo + hi); ins = frame_outer(m, YY, ZZ) < 0; lo = np.where(ins, m, lo); hi = np.where(ins, hi, m)
        xs = np.where(inside0, 0.5 * (lo + hi), 0.0)
        _XS = S.Field2D(xs, y0, z1, res, outside=0.0)
    return _XS(Y, Z)
RAIL_Y0, RAIL_Y1 = 83.5, 140.0
SS_PAD = ((-0.5, 22.8), (8.3, 27.7)); SS_RIBS = (26.1, 25.0, 23.7); SS_DISH = ((-4.6, 17.4), (12.2, 24.0))
TD = ((43.8, 16.6), (47.0, 24.0))
MC_QUAD = [(1.05, -1.14), (12.87, -5.11), (9.69, -14.62), (-2.13, -10.64)]
THUMB = [(50.3, 27.8), (84.8, 28.0), (84.9, 24.7), (51.0, 19.7)]
PLATE = ((-45.7, -62.95), (-21.25, -52.3))
_MCF = None; _THF = None
def mc2(Y, Z):
    global _MCF
    if _MCF is None: _MCF = poly_sdf2(MC_QUAD, 0.03, 4.0)
    return _MCF(Y, Z)
def th2(Y, Z):
    global _THF
    if _THF is None: _THF = poly_sdf2(THUMB, 0.05, 4.0)
    return _THF(Y, Z)
def recess(d, X, Y, Z, reg2, depth, r=0.25, side=0):
    xs = XS(Y, Z); ax = np.abs(X) if side == 0 else (X if side > 0 else -X)
    return S.rdiff(d, np.maximum(reg2, (xs - depth) - ax), r)
def frame_details(d, X, Y, Z):
    d = recess(d, X, Y, Z, S.rect2(Y, Z, (RAIL_Y0, 20.0), (RAIL_Y1, 21.6), 0.8), 1.1, 0.25)        # rail side groove
    d = recess(d, X, Y, Z, S.rect2(Y, Z, (RAIL_Y0, 17.8), (RAIL_Y1, 19.1), 0.6), 0.45, 0.2)        # rail lower step
    d = S.rdiff(d, S.box(X, Y, Z, (-20, 110.3, 0.0), (20, 115.7, 16.06), 0.3), 0.25)              # single cross slot
    d = recess(d, X, Y, Z, th2(Y, Z), 0.35, 0.3)                                                    # thumb-rest panel
    d = recess(d, X, Y, Z, S.rect2(Y, Z, SS_DISH[0], SS_DISH[1], 3.4), 0.7, 0.9)                   # slide-stop dish
    d = recess(d, X, Y, Z, S.rect2(Y, Z, (TD[0][0] - 0.5, TD[0][1] - 0.5), (TD[1][0] + 0.5, TD[1][1] + 0.5), 1.0), 1.2, 0.2)  # takedown slot
    d = recess(d, X, Y, Z, mc2(Y, Z) - 0.35, 0.5, 0.2)                                             # mag-catch pocket (both sides)
    d = recess(d, X, Y, Z, S.rect2(Y, Z, PLATE[0], PLATE[1], 1.6), 0.3, 0.2, side=-1)             # blank text-plate recess (right)
    rr = np.sqrt((Y - PIN_TRIGGER[0]) ** 2 + (Z - PIN_TRIGGER[1]) ** 2)
    d = recess(d, X, Y, Z, np.maximum(rr - 2.15, 1.55 - rr), 0.3, 0.1)
    # trigger-guard front face grooves (8 x 0.75 mm, 1.6 mm pitch)
    o = frame_outer(X, Y, Z)
    zz = np.mod(Z + 9.4, 1.6) - 0.8; band = np.abs(zz) - 0.37
    g = np.maximum(np.maximum(band, S.slab(Z, -9.6, 7.9)), np.maximum(np.abs(X) - 7.8, np.maximum(63.5 - Y, -(o + 0.45))))
    d = S.rdiff(d, g, 0.12)
    # magwell front cutout at the bottom of the front strap
    d = S.rdiff(d, S.box(X, Y, Z, (-6.5, -16.0, -90.0), (6.5, -8.5, -77.4), 1.0), 0.6)
    return d
def slide_stop(X, Y, Z):
    xs = XS(Y, Z); ax = np.abs(X)
    pad = S.rinter(S.rect2(Y, Z, SS_PAD[0], SS_PAD[1], 1.2), np.maximum(ax - (xs + 1.3), (xs - 0.7) - ax), 0.35)
    for zr in SS_RIBS:
        rib = np.maximum(np.maximum(np.abs(Z - zr) - 0.24, S.slab(Y, 0.2, 7.6)), (xs + 1.3 - 0.4) - ax)
        pad = S.rdiff(pad, rib, 0.08)
    return pad
def takedown(X, Y, Z):
    xs = XS(Y, Z); ax = np.abs(X)
    tab = S.rinter(S.rect2(Y, Z, TD[0], TD[1], 0.8), np.maximum(ax - (xs + 0.9), (xs - 1.6) - ax), 0.3)
    for k in range(5):
        zr = TD[0][1] + 1.3 + k * 1.3
        tab = S.rdiff(tab, np.maximum(np.maximum(np.abs(Z - zr) - 0.22, S.slab(Y, TD[0][0] - 1, TD[1][0] + 1)), (xs + 0.9 - 0.3) - ax), 0.06)
    return tab
def mag_catch_L(X, Y, Z):
    xs = XS(Y, Z)
    b = S.rinter(mc2(Y, Z), np.maximum(X - (xs + 2.0), (xs - 0.9) - X), 0.45)
    c, s = math.cos(math.radians(-19.0)), math.sin(math.radians(-19.0)); v = -(Y - 1.05) * s + (Z + 1.14) * c
    for k in range(4):
        b = S.rdiff(b, np.maximum(np.abs(v + 2.3 + k * 2.1) - 0.3, (xs + 2.0 - 0.35) - X), 0.08)
    return b
def mag_catch_R(X, Y, Z):
    xs = XS(Y, Z)
    return S.rinter(mc2(Y, Z) + 0.05, np.maximum(-X - (xs + 0.15), (xs - 0.9) + X), 0.25)

def backstrap(X, Y, Z):
    o = frame_outer(X, Y, Z)
    sh = np.maximum(o, -(o + G.BS_THICK))
    d = S.rinter(sh, bs_region()(Y, Z) + 0.12, 0.35)
    return S.rdiff(d, S.cyl(X, Y, Z, 'x', PIN_HOUSING, 1.6, -20, 20), 0.15)

PIN_TRIGGER = tuple(G.px2g([(777.5, 325.0)])[0]); PIN_HOUSING = tuple(G.px2g([(305.5, 438.0)])[0])
def surface_x(fn, y, z, x0=0.0, x1=25.0):
    """outermost x of the surface of fn along +x at (y, z) (bisection on the last inside->outside crossing)"""
    xs = np.linspace(x0, x1, 2001); d = fn(xs, np.full_like(xs, y), np.full_like(xs, z))
    inside = np.nonzero(d < 0)[0]
    if not len(inside): return None
    i = inside[-1]; a, b = xs[i], xs[min(i + 1, len(xs) - 1)]
    for _ in range(40):
        m = 0.5 * (a + b); dm = fn(np.array([m]), np.array([y]), np.array([z]))[0]
        a, b = (m, b) if dm < 0 else (a, m)
    return 0.5 * (a + b)

def pins():
    out = []
    for (py, pz), fn in ((PIN_TRIGGER, frame_outer), (PIN_HOUSING, frame_outer)):
        xs = surface_x(fn, py, pz)
        out.append((py, pz, xs))
    def f(X, Y, Z):
        d = np.full(X.shape, 1e3)
        for py, pz, xs in out:
            d = np.minimum(d, S.cyl(X, Y, Z, 'x', (py, pz), 1.5, -(xs + 0.25), xs + 0.25, 0.2))
        return d
    return f, out

def locking_block(X, Y, Z):
    d = S.box(X, Y, Z, (-8.8, 37.0, 15.3), (8.8, 60.0, 30.0), 0.6)
    d = np.minimum(d, S.box(X, Y, Z, (-10.4, 44.0, 29.9), (10.4, 56.0, 31.5), 0.3))         # front rail tabs
    d = S.rdiff(d, S.box(X, Y, Z, (-4.8, 43.4, 19.5), (4.8, 50.8, 40.0), 0.4), 0.2)       # lug / spring seat clearance
    return d
def housing(X, Y, Z):
    d = S.box(X, Y, Z, (-8.8, -45.0, 15.3), (8.8, -26.0, 31.2), 0.6)
    d = np.minimum(d, S.box(X, Y, Z, (-10.4, -44.0, 29.9), (10.4, -36.0, 31.5), 0.3))       # rear rail tabs
    d = np.minimum(d, S.box(X, Y, Z, (3.6, -27.0, 26.0), (5.0, -22.0, 33.4), 0.3))         # ejector
    return d

def trigger(X, Y, Z):
    ax = np.abs(X)
    shoe = S.rinter(dSHOE(Y, Z), ax - 3.3, 1.0)
    shoe = S.runion(shoe, S.box(X, Y, Z, (-3.0, 22.5, 8.0), (3.0, 33.0, 18.6), 0.6), 0.8)     # bar tab up to the pin
    yc = 0.5 * (21.0 + 33.6)
    slot = np.maximum(np.maximum(ax - 1.3, -dSHOE(Y, Z) - 1.4), yc - Y)
    shoe = S.rdiff(shoe, slot, 0.2)
    saf = S.rinter(np.minimum(dSAF(Y, Z), np.maximum(np.maximum(dSHOE(Y, Z), -dSHOE(Y, Z) - 1.6), yc - Y)), ax - 1.1, 0.45)
    return np.minimum(shoe, saf)

# =========================================================================== SLIDE
def _hw_slide(Y, Z):
    hw = S.lerp(G.SLIDE_HW, G.LOBE_HW, S.sstep(G.ZSB - 0.2, G.ZSB - 0.9, Z))
    return hw - np.maximum(Y - G.NOSE_Y, 0.0) * G.NOSE_SLOPE
def slide_outer(X, Y, Z):
    ax = np.abs(X); hw = _hw_slide(Y, Z)
    d = S.rinter(dSLIDE(Y, Z), ax - hw, 0.55)
    dch = (ax + Z - (hw + G.ZST - G.TOP_CHAMF)) * (1 / math.sqrt(2))
    return S.rinter(d, dch, 0.6)

def slide(X, Y, Z):
    ax = np.abs(X)
    d = slide_outer(X, Y, Z)
    # serrations: stadium pockets on both sides, floor parallel to the side face, rounded lips
    for (y0, w) in G.REAR_SERR + G.FRONT_SERR:
        yc = y0 + 0.5 * w; rr = 0.5 * w
        st = S.rect2(Y, Z, (y0, G.ZSB - 5.0), (y0 + w, G.SERR_TOP), 0.7)        # square-topped grooves (photo), 0.7 mm corners
        hw = _hw_slide(Y, Z)
        g = np.maximum(st, (hw - G.SERR_DEPTH) - ax)
        d = S.rdiff(d, g, 0.28)
    # ejection port (right side + top) with the rounded bottom-front corner
    # parting groove across the front lobe (continues the slide/frame line of the side photo)
    d = S.rdiff(d, np.maximum(np.maximum(np.abs(Z - (G.ZSB - 0.35)) - 0.28, G.ylobe - 0.2 - Y if hasattr(G, 'ylobe') else 122.5 - Y), (_hw_slide(Y, Z) - 0.35) - ax), 0.12)
    port = S.extrude(S.rect2(Y, Z, (G.PORT_Y0, G.PORT_ZB), (G.PORT_Y1, 70.0), 2.0), X, -30.0, G.HOOD_HW + 0.12)
    d = S.rdiff(d, port, 0.35)
    # interior: barrel channel (front), rear channel, rail grooves, front-wall holes, breech face
    d = S.rdiff(d, S.box(X, Y, Z, (-G.SLIDE_IN_HW, G.BREECH_Y, G.ZSB - 3.0), (G.SLIDE_IN_HW, 127.0, 46.9), 0.8), 0.3)
    d = S.rdiff(d, S.box(X, Y, Z, (-6.0, -46.5, G.ZSB - 3.0), (6.0, G.BREECH_Y + 0.5, 35.5), 0.8), 0.3)
    z0, z1, xg = G.RAIL_GROOVE
    d = S.rdiff(d, S.box(X, Y, Z, (-xg, -46.0, z0), (xg, 122.0, z1), 0.3), 0.2)
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, G.BORE_Z), G.BARREL_R + 0.05, 120.0, 145.0), 0.45)
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, G.GUIDE_Z), G.GUIDE_HOLE_R, 118.0, 145.0), 0.6)
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, G.GUIDE_Z), 5.35, 118.0, 127.3, 0.5), 0.3)         # flange pocket in the lobe
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, G.BORE_Z), 0.9, 15.0, G.BREECH_Y + 1.0), 0.1)   # firing-pin hole
    # rear face: cover-plate recess
    d = S.rdiff(d, S.extrude(S.rect2(X, Z, (-5.6, 31.3), (5.6, 44.2), 1.6), Y, G.YS0 - 2.0, G.YS0 + 0.4), 0.15)
    if DETAIL:
        # extractor slot (right side), rear-sight dovetail, front-sight socket
        d = S.rdiff(d, np.maximum(S.capsule2(Y, Z, (-8.0, 42.0), (30.0, 42.0), 3.0), X + (G.SLIDE_HW - 1.0)), 0.25)
        d = S.rdiff(d, S.box(X, Y, Z, (-7.45, -46.95, G.ZST - 1.3), (7.45, -39.6, G.ZST + 3.0), 0.2), 0.12)
        d = S.rdiff(d, S.box(X, Y, Z, (-1.95, 124.35, G.ZST - 1.2), (1.95, 130.75, G.ZST + 3.0), 0.2), 0.1)
    return d

def extractor(X, Y, Z):
    return S.extrude(S.rect2(Y, Z, (8.6, 39.3), (26.2, 44.7), 0.9), X, -(G.SLIDE_HW + 0.1), -(G.SLIDE_HW - 1.6), 0.25)   # fills the slot height (photo)

def cover_plate(X, Y, Z):
    return S.extrude(S.rect2(X, Z, (-5.4, 31.5), (5.4, 44.0), 1.4), Y, G.YS0 - 0.25, G.YS0 + 1.2, 0.3)

def rear_sight(X, Y, Z):
    prof = np.minimum(dRS(Y, Z), S.rect2(Y, Z, (-46.75, G.ZST - 1.45), (-39.9, G.ZST + 0.5)))
    d = S.rinter(prof, np.abs(X) - 7.2, 0.45)
    notch = S.extrude(S.rect2(X, Z, (-1.75, 51.4), (1.75, 60.0), 0.5), Y, -60.0, 0.0)
    return S.rdiff(d, notch, 0.25)
def front_sight(X, Y, Z):
    prof = np.minimum(dFS(Y, Z), S.rect2(Y, Z, (124.55, G.ZST - 1.35), (130.5, G.ZST + 0.5)))
    return S.rinter(prof, np.abs(X) - 1.75, 0.35)

# =========================================================================== BARREL (+ guide rod / recoil spring)
def barrel(X, Y, Z):
    BZ = G.BORE_Z
    tube = S.cyl(X, Y, Z, 'y', (0.0, BZ), G.BARREL_R, 52.0, G.MUZZLE_Y, 0.45)
    chamber = S.cyl(X, Y, Z, 'y', (0.0, BZ), 7.75, G.BREECH_Y, 55.0, 0.6)
    taper = S.cyl(X, Y, Z, 'y', (0.0, BZ), 7.2, 54.0, 57.5, 0.5)
    hood = S.box(X, Y, Z, (-G.HOOD_HW, G.BREECH_Y, BZ), (G.HOOD_HW, 54.2, G.HOOD_TOP), 0.5)
    d = S.runion(S.runion(chamber, hood, 1.2), S.runion(tube, taper, 1.0), 1.0)
    lug = np.minimum(S.box(X, Y, Z, (-4.5, 28.0, 29.6), (4.5, 50.2, BZ - 5.0), 0.6),
                     S.box(X, Y, Z, (-4.5, 44.0, 21.0), (4.5, 50.2, 31.0), 0.6))
    d = S.runion(d, lug, 1.0)
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, BZ), 4.5, 20.0, 150.0), 0.3)                  # bore
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, BZ), 4.95, 20.0, 44.0), 0.4)                  # chamber
    d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, BZ), 5.6, G.MUZZLE_Y - 0.35, 150.0), 0.25)    # recessed crown
    return d

def guide_rod(X, Y, Z):
    GZ = G.GUIDE_Z
    rod = S.cyl(X, Y, Z, 'y', (0.0, GZ), 2.0, 49.4, 133.5, 0.4)
    fl = S.cyl(X, Y, Z, 'y', (0.0, GZ), 5.05, 49.4, 51.6, 0.4)           # covers the spring's cut end (R 4.05 + wire 0.72)
    cap = np.minimum(S.cyl(X, Y, Z, 'y', (0.0, GZ), 5.05, 125.6, 126.9, 0.3), S.cyl(X, Y, Z, 'y', (0.0, GZ), 3.0, 125.6, G.YS1 - 0.4, 0.6))
    # recoil spring: helix SDF around the rod (R 4.05, wire 0.72, pitch 3.6)
    u, v = X, Z - GZ; rho = np.sqrt(u * u + v * v); th = np.arctan2(v, u)
    pitch, R, wr = 3.6, 4.05, 0.72
    s = (Y - 51.6) - pitch * th / (2 * np.pi); s = s - pitch * np.round(s / pitch)
    hel = np.sqrt((rho - R) ** 2 + s * s) - wr
    hel = np.maximum(hel, S.slab(Y, 50.4, 126.1))            # cut ends buried inside the rear flange / front cap flange
    return np.minimum(np.minimum(np.minimum(rod, fl), cap), hel)

# =========================================================================== MAGAZINE
def mag_body(X, Y, Z):
    d = S.rinter(mag_xs(X, Y, Z), S.slab(Z, -80.9, G.MAG_TOP), 0.6)
    c = 1.0 / math.sqrt(1 + G.MAG_RAKE ** 2); s = (Y - G.mag_rear(Z)) * c; D = (G.mag_front(Z) - G.mag_rear(Z)) * c
    cav = np.maximum(mag_xs(X, Y, Z, -0.9), S.slab(Z, 18.0, 40.0))
    lower = np.maximum(cav, Z - 23.0)                       # full inner cavity below the lips
    front = np.maximum(cav, 0.74 * D - s)                   # open front quarter
    slot = np.maximum(cav, np.abs(X) - 3.6)                 # feed-lip slot over the rear 3/4
    d = S.rdiff(d, np.minimum(np.minimum(lower, front), slot), 0.3)
    if DETAIL:
        for zc in (-52.0, -38.0, -24.0, -10.0, 4.0):                                       # witness holes in the rear wall
            yc = G.mag_rear(zc)
            d = S.rdiff(d, S.cyl(X, Y, Z, 'y', (0.0, zc), 1.3, yc - 2.0, yc + 1.4), 0.15)
        d = S.rdiff(d, np.maximum(np.maximum(np.abs(X) - 4.5, S.slab(Z, -13.0, -6.0)), (G.mag_front(Z) - 1.6) - Y), 0.3)   # catch notch
    return d
def follower(X, Y, Z):
    d = np.maximum(mag_xs(X, Y, Z, -1.05), S.slab(Z, 17.7, 21.6))
    c = 1.0 / math.sqrt(1 + G.MAG_RAKE ** 2); s = (Y - G.mag_rear(Z)) * c
    step = np.maximum(np.maximum(mag_xs(X, Y, Z, -1.05), S.slab(Z, 17.7, 22.6)), X - 0.0)      # raised rib on the left half
    return S.rinter(np.minimum(d, step), Z - 30.0, 0.3)
def baseplate(X, Y, Z):
    # plate = magazine profile below the visible body band (z < -80.1) + the front lip; no thin slivers of the band
    prof = np.maximum(dMAG(Y, Z), np.minimum(Z + 80.1, S.rect2(Y, Z, (-15.2, -81.5), (-9.0, -79.35), 0.6)))
    return S.rinter(prof, np.abs(X) - G.BASE_HW, 1.5)

# =========================================================================== mesh all
def bbox_of(m, pad=1.0):
    zz, yy = np.nonzero(P['m_' + m] > 0)
    return (Y0 + yy.min() * RES - pad, Y0 + (yy.max() + 1) * RES + pad, Z1 - (zz.max() + 1) * RES - pad, Z1 - zz.min() * RES + pad)

def run(h, which, out):
    res = {}
    def add(name, fn, lo, hi, mat, hh=None):
        V, F = S.mesh(fn, lo, hi, hh or h, name=name)
        res[name] = (V, F, {'mat': np.full(len(V), MAT[mat], np.float32)})
    if 'frame' in which:
        y0, y1, z0, z1 = bbox_of('frame', 1.5)
        add('frame', frame_body, (-17, y0, z0), (17, y1, z1 + 0.5), 'polymer')
        add('backstrap', backstrap, (-17, -70, -75), (17, -20, 20), 'polymer')
        add('trigger', trigger, (-4, 18, -13), (4, 43, 20), 'polymer', min(h, 0.12))
        pf, pinfo = pins()
        for i, (py, pz, xs) in enumerate(pinfo):
            add('pin%d' % i, lambda X, Y, Z, py=py, pz=pz, xs=xs: S.cyl(X, Y, Z, 'x', (py, pz), 1.5, -(xs + 0.25), xs + 0.25, 0.2),
                (-xs - 1, py - 3, pz - 3), (xs + 1, py + 3, pz + 3), 'steel', min(h, 0.1))
        if DETAIL:
            add('slidestop', slide_stop, (-17, -2, 21), (17, 10, 29), 'steel', min(h, 0.07))
            add('takedown', takedown, (-17, 42, 15), (17, 49, 25.5), 'steel', min(h, 0.07))
            add('magcatchL', mag_catch_L, (8, -4, -16.5), (20, 15, 1), 'polymer', min(h, 0.08))
            add('magcatchR', mag_catch_R, (-20, -4, -16.5), (-8, 15, 1), 'polymer', min(h, 0.08))
        add('lockblock', locking_block, (-11, 35, 14), (11, 62, 33), 'steel', min(h, 0.15))
        add('housing', housing, (-11, -47, 14), (11, -20, 35), 'steel', min(h, 0.15))
    if 'slide' in which:
        add('slide', slide, (-14, G.YS0 - 1.5, 15.0), (14, G.YS1 + 1.0, G.ZST + 1.0), 'slide', min(h, 0.12))
        add('rsight', rear_sight, (-8, -47.5, 47.5), (8, -38.5, 55.5), 'sightpoly', min(h, 0.08))
        add('fsight', front_sight, (-2.5, 123.5, 47.5), (2.5, 131.5, 54.5), 'sightpoly', min(h, 0.08))
        if DETAIL: add('extractor', extractor, (-14, 6, 38), (-10, 28, 46), 'steel', min(h, 0.07))
        add('plate', cover_plate, (-6.5, G.YS0 - 1.0, 30.0), (6.5, G.YS0 + 2.0, 45.5), 'steel', min(h, 0.1))
    if 'barrel' in which:
        add('barrel', barrel, (-9.5, 24.0, 19.5), (9.5, G.MUZZLE_Y + 0.8, 51.0), 'barrel', min(h, 0.12))
        add('guiderod', guide_rod, (-5.5, 49.0, 18.5), (5.5, 136.5, 30.0), 'spring', min(h, 0.1))
    if 'mag' in which:
        add('magbody', mag_body, (-12.5, -60, -81.5), (12.5, 35, 27.5), 'magbody')
        add('follower', follower, (-12, -20, 16.5), (12, 32, 24), 'orange', min(h, 0.12))
        add('baseplate', baseplate, (-14, -59, -88.5), (14, -9, -77.0), 'base', min(h, 0.12))
    if '--merge' in sys.argv and os.path.exists(out):
        old = np.load(out); keep = {}
        for k in old.files:
            n = k.split('__')[0]
            if n in res: continue
            keep.setdefault(n, {})[k] = old[k]
        S.save(out, res)
        new = dict(np.load(out)); [new.update(v) for v in keep.values()]; np.savez_compressed(out, **new)
    else:
        S.save(out, res)
    print('PARTS_DONE', out, {k: len(v[1]) for k, v in res.items()})
    return res

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    h = float(a[0]) if a else 0.3
    which = set((a[1] if len(a) > 1 else 'frame,slide,barrel,mag').split(','))
    out = a[2] if len(a) > 2 else os.path.join(HERE, 'work', 'high.npz')
    t = time.time(); run(h, which, out); print('total %.1fs' % (time.time() - t))
