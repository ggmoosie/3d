"""ar15_post.py - 2-D post work for the AR-15 kit, run with SYSTEM Python (PIL + numpy), not Blender:
photo calibration (two-point similarity per reference photo), reference overlays at matching scale, contact sheets,
labelled exploded / socket sheets.

    python ar15_post.py calib                     -> out/progress/m1_calibration_{left,right}.png + out/calibration.json
    python ar15_post.py overlay <render.json>     -> overlay PNG(s) described by the JSON written by build_ar15.py
    python ar15_post.py sheet <out.png> <title> <img> [<img> ...]
    python ar15_post.py labels <labels.json>      -> labelled image (leader lines + names)
"""
import sys, os, json, math, cmath
import numpy as np
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
except ImportError:            # imported from Blender for the photo calibration only
    Image = ImageDraw = ImageFont = ImageOps = ImageFilter = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ar15_spec as SP
OUT = os.path.join(HERE, 'out'); REFS = os.path.join(HERE, 'refs')

def font(size, bold=False):
    for f in (('segoeuib.ttf' if bold else 'segoeui.ttf'), ('arialbd.ttf' if bold else 'arial.ttf')):
        p = os.path.join('C:/Windows/Fonts', f)
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ------------------------------------------------------------------------------------------------ photo calibration
# Each photo: screen coords (sx, sy) = (+-Y, -Z) of the G frame map to photo pixels by a complex similarity q = a*s + b,
# solved from two anchors on the bore line.  'side' = which side of the gun the photo shows.
def _bore11(u): return 264.0 + (u - 557.0) * 0.01411          # barrel centre at the handguard front -> castle-nut centre
def _bore01(u): return 164.0 - 0.0061 * (u - 255.0)           # castle-nut centre -> barrel / birdcage centre
PHOTOS = {
    '11': dict(file='11_freefloat_handguard.jpg', side='left', title='refs/11 (free-float M-LOK, left side)',
               anchors=[((0.0, 0.0), (1411.0, _bore11(1411.0))), ((-200.0, 0.0), (1411.0 + 609.76, _bore11(1411.0 + 609.76)))],
               notes='M-LOK pitch 123.13 px -> 0.3249 mm/px at the handguard skin; 0.328 used (receiver side plane); '
                     'upper front face at u 1411 (handguard joint), bore line through the barrel centre at the handguard '
                     'front (557, 264) and the castle-nut centre (2045, 285), tilt 0.81 deg'),
    '01': dict(file='01_M4A1_flattop.jpg', side='right', title='refs/01 (M4A1 flat-top, right side)',
               anchors=[((0.0, 0.0), (510.0, _bore01(510.0))), ((SP.MUZZLE_Y, 0.0), (1008.0, _bore01(1008.0)))],
               notes='quad-rail top lug period 12.50 px -> 0.801 mm/px (centre plane; the near side rail reads 12.90 px = '
                     '0.776 mm/px, 3 % perspective); upper front face at u 510, birdcage tip at u 1008 = G Y 399.5'),
}

def screen(side, Y, Z): return complex(-Y if side == 'left' else Y, -Z)

def photo_xf(key):
    p = PHOTOS[key]; (g1, q1), (g2, q2) = p['anchors']
    s1, s2 = screen(p['side'], *g1), screen(p['side'], *g2); q1, q2 = complex(*q1), complex(*q2)
    a = (q2 - q1) / (s2 - s1); b = q1 - a * s1
    return a, b

def g_to_photo(key, Y, Z):
    a, b = photo_xf(key); q = a * screen(PHOTOS[key]['side'], Y, Z) + b; return q.real, q.imag

def calib_json():
    out = {}
    for k, p in PHOTOS.items():
        a, b = photo_xf(k)
        out[k] = dict(file=p['file'], side=p['side'], mm_per_px=1.0 / abs(a), tilt_deg=math.degrees(cmath.phase(a)),
                      anchors_G_mm_to_px=[[list(g), list(q)] for g, q in p['anchors']], notes=p['notes'])
    return out

# ------------------------------------------------------------------------------------------------ warping
def warp_photo(key, W, H, mm_per_px, center_g, side, dim=1.0):
    """resample the photo into a render frame (W x H px, mm_per_px, centre (Y, Z) G, viewed from `side`)"""
    p = PHOTOS[key]; im = np.asarray(Image.open(os.path.join(REFS, p['file'])).convert('RGB')).astype(np.float32)
    a, b = photo_xf(key)
    ii, jj = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    sx = (ii - W / 2.0) * mm_per_px; sy = (jj - H / 2.0) * mm_per_px          # screen mm relative to the centre
    Yc, Zc = center_g
    s0 = screen(side, Yc, Zc)
    if side != p['side']: raise ValueError('photo %s shows the %s side' % (key, p['side']))
    S = (s0.real + sx) + 1j * (s0.imag + sy)
    Q = a * S + b
    u, v = Q.real - 0.5, Q.imag - 0.5
    h, w = im.shape[:2]
    u0 = np.clip(np.floor(u).astype(int), 0, w - 2); v0 = np.clip(np.floor(v).astype(int), 0, h - 2)
    fu = np.clip(u - u0, 0, 1)[..., None]; fv = np.clip(v - v0, 0, 1)[..., None]
    c = (im[v0, u0] * (1 - fu) * (1 - fv) + im[v0, u0 + 1] * fu * (1 - fv) + im[v0 + 1, u0] * (1 - fu) * fv + im[v0 + 1, u0 + 1] * fu * fv)
    inside = ((u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1))[..., None]
    lo, hi = np.percentile(im, 1.0), np.percentile(im, 99.5)
    c = np.clip((c - lo) / max(1.0, hi - lo), 0, 1) ** 0.85 * 255.0          # level the photo (refs/11 is dark)
    c = np.where(inside, c * dim, 24.0)
    return c

def g_to_px(Y, Z, W, H, mm_per_px, center_g, side):
    sx = (-(Y - center_g[0]) if side == 'left' else (Y - center_g[0])) / mm_per_px
    sy = -(Z - center_g[1]) / mm_per_px
    return W / 2.0 + sx, H / 2.0 + sy

def draw_grid(d, W, H, mm_per_px, center_g, side, step=10.0, major=50.0, col_minor=(255, 255, 255, 40), col_major=(255, 210, 120, 110)):
    Yc, Zc = center_g; half_w = W * mm_per_px / 2; half_h = H * mm_per_px / 2
    y = math.floor((Yc - half_w) / step) * step
    while y <= Yc + half_w:
        x, _ = g_to_px(y, 0, W, H, mm_per_px, center_g, side); maj = abs(y / major - round(y / major)) < 1e-6
        d.line([(x, 0), (x, H)], fill=col_major if maj else col_minor, width=1)
        if maj: d.text((x + 3, H - 18), '%d' % y, fill=(255, 210, 120, 220), font=font(12))
        y += step
    z = math.floor((Zc - half_h) / step) * step
    while z <= Zc + half_h:
        _, yy = g_to_px(0, z, W, H, mm_per_px, center_g, side); maj = abs(z / major - round(z / major)) < 1e-6
        d.line([(0, yy), (W, yy)], fill=col_major if maj else col_minor, width=1)
        if maj: d.text((4, yy + 2), '%d' % z, fill=(255, 210, 120, 220), font=font(12))
        z += step

def cross(d, x, y, r, col, w=2):
    d.line([(x - r, y), (x + r, y)], fill=col, width=w); d.line([(x, y - r), (x, y + r)], fill=col, width=w)

def f_to_g(p):
    return (None if p[0] is None else p[0] * 10 - SP.G2F[0], None if p[1] is None else p[1] * 10 - SP.G2F[1], p[2] * 10 - SP.G2F[2])

def anchors_layer(d, W, H, mm_per_px, center_g, side, ours=None):
    f = font(13)
    # bore line + F origin
    _, by = g_to_px(0, 0, W, H, mm_per_px, center_g, side); d.line([(0, by), (W, by)], fill=(90, 220, 255, 200), width=1)
    d.text((6, by - 17), 'bore (G Z 0 = F z %.2f cm)' % (SP.G2F[2] / 10), fill=(90, 220, 255, 255), font=f)
    ox, oy = g_to_px(-SP.G2F[1], -SP.G2F[2], W, H, mm_per_px, center_g, side)
    cross(d, ox, oy, 12, (255, 255, 255, 255), 2); d.text((ox + 8, oy + 4), 'F origin', fill=(255, 255, 255, 255), font=f)
    for name, p in SP.M4T.items():
        g = f_to_g(p)
        if g[1] is None: continue
        x, y = g_to_px(g[1], g[2], W, H, mm_per_px, center_g, side)
        cross(d, x, y, 7, (255, 80, 80, 255), 2); d.text((x + 6, y - 16), 'M4T ' + name.split(' (')[0], fill=(255, 120, 120, 255), font=f)
    for name, (Y, Z) in (ours or {}).items():
        x, y = g_to_px(Y, Z, W, H, mm_per_px, center_g, side)
        cross(d, x, y, 7, (110, 255, 140, 255), 2); d.text((x + 6, y + 2), name, fill=(130, 255, 160, 255), font=f)

def compose_overlay(render_path, key, meta, out_path, title, ours=None, alpha=0.62, grid=True):
    W, H = meta['size']; m = meta['mm_per_px']; cg = meta['center_g']; side = meta['side']
    base = warp_photo(key, W, H, m, cg, side, dim=0.9)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGBA')
    if render_path and os.path.exists(render_path):
        r = Image.open(render_path).convert('RGBA'); ra = np.asarray(r).astype(np.float32)
        a = ra[..., 3:4] / 255.0 * alpha
        tint = ra[..., :3] * np.array([1.0, 0.55, 0.18]) * 1.15          # orange ghost, readable on light and dark photos
        mixed = np.asarray(img).astype(np.float32)[..., :3] * (1 - a) + tint * a
        img = Image.fromarray(np.clip(mixed, 0, 255).astype(np.uint8)).convert('RGBA')
        # silhouette edge of the render in cyan
        al = (ra[..., 3] > 127).astype(np.uint8)
        edge = (al ^ np.roll(al, 1, 0)) | (al ^ np.roll(al, 1, 1))
        e = np.zeros((H, W, 4), np.uint8); e[edge > 0] = (60, 230, 255, 255)
        img = Image.alpha_composite(img, Image.fromarray(e))
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if grid: draw_grid(d, W, H, m, cg, side)
    anchors_layer(d, W, H, m, cg, side, ours)
    img = Image.alpha_composite(img, ov)
    band = Image.new('RGBA', (W, 54), (18, 19, 22, 255)); bd = ImageDraw.Draw(band)
    c = calib_json()[key]
    bd.text((10, 6), title, fill=(255, 255, 255, 255), font=font(18, True))
    bd.text((10, 31), '%s  |  %.4f mm/px, tilt %.2f deg  |  grid 10 / 50 mm (G frame)  |  red = M4Tactical anchors, green = ours, cyan = our silhouette'
            % (PHOTOS[key]['title'], c['mm_per_px'], c['tilt_deg']), fill=(190, 195, 205, 255), font=font(13))
    out = Image.new('RGBA', (W, H + 54)); out.paste(band, (0, 0)); out.paste(img, (0, 54))
    out.convert('RGB').save(out_path); return out_path

# ------------------------------------------------------------------------------------------------ sheets + labels
def sheet(paths, out_path, title, cols=2, cell_w=800, gap=6, subtitle='', maxw=1600):
    ims = [Image.open(p).convert('RGB') for p in paths if os.path.exists(p)]
    if not ims: return None
    cells = [im.resize((cell_w, int(im.height * cell_w / im.width)), Image.LANCZOS) for im in ims]
    rows = (len(cells) + cols - 1) // cols; ch = max(c.height for c in cells)
    W = cols * cell_w + (cols + 1) * gap; H = 50 + rows * ch + (rows + 1) * gap
    S = Image.new('RGB', (W, H), (16, 17, 20)); d = ImageDraw.Draw(S)
    d.text((10, 6), title, fill=(255, 255, 255), font=font(20, True))
    if subtitle: d.text((10, 30), subtitle, fill=(180, 185, 195), font=font(13))
    for i, c in enumerate(cells):
        r, k = divmod(i, cols); S.paste(c, (gap + k * (cell_w + gap), 50 + gap + r * (ch + gap)))
    if S.width > maxw: S = S.resize((maxw, int(S.height * maxw / S.width)), Image.LANCZOS)
    S.save(out_path); return out_path

def labels(spec_path):
    J = json.load(open(spec_path)); im = Image.open(J['image']).convert('RGBA'); W, H = im.size
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov); f = font(J.get('font', 15), True)
    placed = []
    items = sorted(J['labels'], key=lambda l: l['xy'][0])
    if J.get('radial'):              # push every label outward from the cluster centre so leaders do not cross
        cx = sum(l['xy'][0] for l in items) / len(items); cy = sum(l['xy'][1] for l in items) / len(items)
        for l in items:
            dx, dy = l['xy'][0] - cx, l['xy'][1] - cy; n = max(1.0, math.hypot(dx, dy))
            tw0 = d.textlength(l['text'], font=f)
            tx = l['xy'][0] + dx / n * J['radial'] - (tw0 if dx < 0 else 0); ty = l['xy'][1] + dy / n * J['radial'] * 0.7 - 10
            l['text_xy'] = (min(max(6, tx), W - tw0 - 6), min(max(6, ty), H - 26)); l['down'] = dy > 0
    for l in items:
        x, y = l['xy']; tx, ty = l.get('text_xy', (x, y - 40))
        # avoid overlapping text boxes by nudging vertically
        tw = d.textlength(l['text'], font=f); box = [tx - 4, ty - 2, tx + tw + 4, ty + 20]
        for _ in range(40):
            if not any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed): break
            ty += 22 if l.get('down', y > H / 2) else -22; box = [tx - 4, ty - 2, tx + tw + 4, ty + 20]
        placed.append(box)
        col = tuple(l.get('color', (255, 200, 90))) + (255,)
        d.line([(x, y), (tx + (0 if tx > x else tw), ty + 10)], fill=col, width=2); d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col)
        d.rectangle(box, fill=(14, 15, 18, 200)); d.text((tx, ty), l['text'], fill=(255, 255, 255, 255), font=f)
    out = Image.alpha_composite(im, ov)
    if J.get('title'):
        band = Image.new('RGBA', (W, 46), (16, 17, 20, 255)); bd = ImageDraw.Draw(band)
        bd.text((12, 10), J['title'], fill=(255, 255, 255, 255), font=font(20, True))
        o2 = Image.new('RGBA', (W, H + 46)); o2.paste(band, (0, 0)); o2.paste(out, (0, 46)); out = o2
    if out.width > 1600: out = out.resize((1600, int(out.height * 1600 / out.width)), Image.LANCZOS)
    out.convert('RGB').save(J['out']); return J['out']

def markings(path):
    """engraving mask for the lower receiver's left side (white = surface, black = engraved), 10 px/mm, x = -G.Y (front at
    the left edge, as seen from the left), y = -G.Z.  Generic markings only: no maker names or trademarks."""
    W, H = 2000, 800; im = Image.new('L', (W, H), 255); d = ImageDraw.Draw(im)
    def put(text, Y, Z, cap_mm, bold=True, track=0.0):
        f = font(int(cap_mm * 10 / 0.72), bold)
        x, y = -Y * 10.0, -Z * 10.0
        w = d.textlength(text, font=f) + track * 10 * (len(text) - 1)
        bb = d.textbbox((0, 0), text, font=f); h = bb[3] - bb[1]
        cx = x - w / 2.0; cy = y - h / 2.0 - bb[1]
        if track:
            for ch in text:
                d.text((cx, cy), ch, fill=0, font=f); cx += d.textlength(ch, font=f) + track * 10
        else:
            d.text((cx, cy), text, fill=0, font=f)
    # roll-mark panel on the magwell (Y -71..-16, Z -56..-40)
    put('LNS-15A1', -43.5, -43.6, 3.6, True, 0.25)
    put('CAL. 5.56 MM', -43.5, -48.6, 2.4, True, 0.15)
    put('SER. LNS 004151', -43.5, -52.8, 2.2, True, 0.1)
    # fire-control markings around the selector (Y -148.6, Z -32)
    put('SAFE', -125.8, -26.6, 2.3, True, 0.2)
    put('SEMI', -148.6, -16.8, 2.3, True, 0.2)
    put('AUTO', -171.2, -27.2, 2.3, True, 0.2)
    im = im.filter(ImageFilter.GaussianBlur(0.7))           # soft engraving walls for the bump
    im.save(path); return path

def packmasks(bake_dir):
    """<gun>_<slot>_Masks.png = R AO, G curvature, B 1 (one sampler instead of two)"""
    import glob
    out = []
    for ao in sorted(glob.glob(os.path.join(bake_dir, '*_AO.png'))):
        cv = ao[:-7] + '_Curv.png'
        if not os.path.exists(cv): continue
        a = Image.open(ao).convert('L'); c = Image.open(cv).convert('L')
        if c.size != a.size: c = c.resize(a.size, Image.BILINEAR)
        b = Image.new('L', a.size, 255)
        p = ao[:-7] + '_Masks.png'; Image.merge('RGB', (a, c, b)).save(p); out.append(p)
    return out

def calibration_sheets():
    os.makedirs(os.path.join(OUT, 'progress'), exist_ok=True)
    json.dump(calib_json(), open(os.path.join(OUT, 'calibration.json'), 'w'), indent=1)
    ours = {'trigger face': SP.TRIG_FACE, 'pivot pin': (SP.PIVOT_Y, SP.PIN_Z), 'takedown pin': (SP.TAKEDOWN_Y, SP.PIN_Z),
            'hammer pin': SP.HAMMER_PIN, 'trigger pin': SP.TRIGGER_PIN, 'selector': SP.SELECTOR, 'mag catch': SP.MAGCATCH,
            'rail top': (-95.0, SP.RAIL_TOP), 'muzzle': (SP.MUZZLE_Y, 0.0), 'sight line': (225.0, SP.SIGHT_Z)}
    outs = []
    for key, side, cg in (('11', 'left', (-20.0, -40.0)), ('01', 'right', (-20.0, -40.0))):
        W, H = 1600, 720; m = 0.62
        meta = dict(size=[W, H], mm_per_px=m, center_g=list(cg), side=side)
        p = os.path.join(OUT, 'progress', 'm1_calibration_%s.png' % side)
        compose_overlay(None, key, meta, p, 'M1 calibration: %s at true scale in the G frame' % PHOTOS[key]['title'], ours=ours)
        outs.append(p)
    return outs

REGIONS = {'lower': ('Lower receiver', ['lower_right', 'lower_left']),
           'upper': ('Upper receiver: forward assist + brass deflector', ['upper_right', 'upper_rear34']),
           'stock': ('6-position stock', ['stock_left', 'stock_rear34']),
           'magazine': ('30-round magazine', ['mag_right', 'mag_top34']),
           'handguard': ('M-LOK handguard: lightening pockets', ['hg_pockets', 'hg_rear34']),
           'magazine_round': ('30-round magazine: top round under the feed lips', ['mag_lips', 'mag_top34'])}

def beforeafter(cdir, tag_a, tag_b, out_dir, notes=None):
    """one sheet per region: row 1 = tag_a close-ups, row 2 = tag_b, same cameras / lights / materials"""
    outs = []
    for key, (title, shots) in REGIONS.items():
        rows = []
        for tag in (tag_a, tag_b):
            ims = [Image.open(os.path.join(cdir, '%s_%s.png' % (tag, s))).convert('RGB') for s in shots
                   if os.path.exists(os.path.join(cdir, '%s_%s.png' % (tag, s)))]
            if ims: rows.append((tag, ims))
        if len(rows) < 2: continue
        cw = 780; gap = 6; lab = 120
        cells = [[im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS) for im in ims] for _, ims in rows]
        ch = cells[0][0].height
        W = lab + 2 * cw + 3 * gap; H = 64 + 2 * ch + 3 * gap
        S = Image.new('RGB', (W, H), (16, 17, 20)); d = ImageDraw.Draw(S)
        d.text((12, 8), 'Before / after - %s' % title, fill=(255, 255, 255), font=font(22, True))
        sub = (notes or {}).get(key, 'same cameras, light rig and look-dev materials (baked AO / curvature / normal masks of each pass)')
        d.text((12, 38), sub, fill=(180, 185, 195), font=font(14))
        for r, ((tag, _), row) in enumerate(zip(rows, cells)):
            y = 64 + gap + r * (ch + gap)
            d.text((12, y + ch // 2 - 14), tag.upper().replace('PASS', 'PASS '), fill=(255, 190, 90) if r else (150, 160, 175), font=font(22, True))
            for k, c in enumerate(row): S.paste(c, (lab + gap + k * (cw + gap), y))
        p = os.path.join(out_dir, 'beforeafter_%s.png' % key); S.save(p); outs.append(p)
    return outs

def composite(a_path, b_path, tris_npy, out_path, dilate=1):
    """out = B inside the UV triangles (rasterised at the texture size, grown by `dilate` px), A elsewhere"""
    A = Image.open(a_path).convert('RGB'); B = Image.open(b_path).convert('RGB'); W, H = A.size
    if B.size != A.size: B = B.resize(A.size, Image.BILINEAR)
    m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
    for t in np.load(tris_npy):
        d.polygon([(float(u) * W, (1.0 - float(v)) * H) for (u, v) in t], fill=255)
    if dilate > 0: m = m.filter(ImageFilter.MaxFilter(2 * int(dilate) + 1))
    Image.composite(B, A, m).save(out_path); return out_path

def freesquare(tris_npy, res=1024, dilate=3):
    """largest empty axis-aligned square in a UV atlas whose used triangles are given (grown by `dilate` px of margin):
    prints {u0, v0, size} in UV units (v up)"""
    m = Image.new('L', (res, res), 0); d = ImageDraw.Draw(m)
    for t in np.load(tris_npy):
        d.polygon([(float(u) * res, (1.0 - float(v)) * res) for (u, v) in t], fill=255)
    if dilate > 0: m = m.filter(ImageFilter.MaxFilter(2 * int(dilate) + 1))
    occ = np.asarray(m) > 0
    dp = np.zeros((res, res), np.int32); best = (0, 0, 0)
    for i in range(res):
        row = dp[i]; prev = dp[i - 1] if i else np.zeros(res, np.int32)
        for j in range(res):
            if occ[i, j]: continue
            v = 1 if (i == 0 or j == 0) else 1 + min(prev[j], row[j - 1], prev[j - 1])
            row[j] = v
            if v > best[0]: best = (v, i, j)
    k, i, j = best
    k, i, j = int(k), int(i), int(j)
    out = dict(u0=(j - k + 1) / res, v0=1.0 - (i + 1) / res, size=k / res, px=k)
    print(json.dumps(out)); return out

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'calib'
    if cmd == 'calib':
        for p in calibration_sheets(): print('wrote', p)
    elif cmd == 'overlay':
        J = json.load(open(sys.argv[2]))
        for o in J['overlays']:
            print('wrote', compose_overlay(o['render'], o['photo'], o['meta'], o['out'], o['title'], o.get('ours'), o.get('alpha', 0.62)))
    elif cmd == 'sheet':
        print('wrote', sheet(sys.argv[4:], sys.argv[2], sys.argv[3]))
    elif cmd == 'sheetw':          # sheetw out title cols cell_w subtitle paths...  (no 1600 px cap)
        print('wrote', sheet(sys.argv[7:], sys.argv[2], sys.argv[3], cols=int(sys.argv[4]), cell_w=int(sys.argv[5]), subtitle=sys.argv[6], maxw=10 ** 6))
    elif cmd == 'labels':
        print('wrote', labels(sys.argv[2]))
    elif cmd == 'markings':
        print('wrote', markings(sys.argv[2]))
    elif cmd == 'beforeafter':
        nt = json.load(open(sys.argv[6])) if len(sys.argv) > 6 else None
        for p in beforeafter(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], nt): print('wrote', p)
    elif cmd == 'composite':
        print('wrote', composite(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]) if len(sys.argv) > 6 else 1))
    elif cmd == 'freesquare':
        freesquare(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1024, int(sys.argv[4]) if len(sys.argv) > 4 else 3)
    elif cmd == 'packmasks':
        print('wrote %d packed mask textures' % len(packmasks(sys.argv[2])))
