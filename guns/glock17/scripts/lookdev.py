"""lookdev.py - G17 v4 PBR shading (Blender module), used by bl_render.py (high-poly lookdev) AND bake.py (the same
networks are baked into BaseColor / ORM / Normal), so the review renders show exactly what the game textures contain.

Measured / real values (linear):  nDLC slide 0.035 base (slightly cool), metallic 1, roughness 0.40 +-0.06 handling smudge;
polymer 0.031 (slightly warmer, less saturated than the nDLC), roughness 0.68 with micro-roughness noise and glossier
stud tops / contact areas; barrel and small steel parts nDLC/black steel.
Masks computed on the high-poly at shading time:
  cavity  = 1 - local AO (1.6 mm)              -> faint darkening + dust in recesses and serration roots
  edge    = Bevel-node normal deviation (0.25 mm) x convexity (local AO ~ 1) x breakup noise
            -> on steel only: slightly lighter base, lower roughness on the sharpest edges (crown, slide corners,
               serration lips, slide-stop tip).  Kept subtle: a new Glock, no silver edges.
Grip texture (measured on the master photo): raised square studs, 0.9 mm flat tops, 1.35 mm bases, 0.5 mm high, 2.2 mm
grid rotated 22.6 deg with the grip; side panels from work/mask_side_[RL].png, front strap / backstrap by normal."""
import bpy, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(HERE, 'work', 'mask_meta.json')))
VAL = {   # base colour (linear), roughness, metallic
    'polymer': ((0.0322, 0.0316, 0.0311), 0.68, 0.0), 'steel': ((0.045, 0.046, 0.049), 0.36, 1.0),
    'slide': ((0.034, 0.0352, 0.0376), 0.40, 1.0), 'barrel': ((0.055, 0.056, 0.059), 0.32, 1.0),
    'white': ((0.80, 0.80, 0.78), 0.45, 0.0), 'orange': ((0.85, 0.20, 0.02), 0.45, 0.0),
    'magbody': ((0.0315, 0.031, 0.0306), 0.52, 0.0), 'base': ((0.0308, 0.0303, 0.0299), 0.62, 0.0),
    'spring': ((0.05, 0.05, 0.052), 0.30, 1.0), 'sightpoly': ((0.0308, 0.0303, 0.0299), 0.58, 0.0)}
MATID = dict(polymer=0, steel=1, slide=2, barrel=3, white=4, orange=5, magbody=6, base=7, spring=8, sightpoly=9)
IDMAT = {v: k for k, v in MATID.items()}
METALS = ('slide', 'barrel', 'steel', 'spring')
WEAR_COL = (0.13, 0.13, 0.135)            # bare nitrided steel peeking through, linear (subtle)

def _m(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: nt.links.new(v, n.inputs[i])
    return n.outputs[0]
def _smooth(nt, e0, e1, x):
    t = _m(nt, 'DIVIDE', _m(nt, 'SUBTRACT', x, e0), e1 - e0); t = _m(nt, 'MINIMUM', _m(nt, 'MAXIMUM', t, 0.0), 1.0)
    return _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', t, t), _m(nt, 'SUBTRACT', 3.0, _m(nt, 'MULTIPLY', t, 2.0)))
def _lerp(nt, a, b, t):
    return _m(nt, 'ADD', a, _m(nt, 'MULTIPLY', _m(nt, 'SUBTRACT', b, a), t))
def gxyz(nt):
    """G-frame mm (x left, y muzzle, z up) of the shading point: object coords (objects sit at the origin)"""
    tc = nt.nodes.new('ShaderNodeTexCoord'); sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sp.inputs[0])
    return _m(nt, 'MULTIPLY', sp.outputs['X'], 1000.0), _m(nt, 'MULTIPLY', sp.outputs['Y'], -1000.0), _m(nt, 'MULTIPLY', sp.outputs['Z'], 1000.0)
def gnormal(nt):
    g = nt.nodes.new('ShaderNodeNewGeometry'); vt = nt.nodes.new('ShaderNodeVectorTransform')
    vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'; nt.links.new(g.outputs['Normal'], vt.inputs[0])
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(vt.outputs[0], sp.inputs[0])
    return sp.outputs['X'], _m(nt, 'MULTIPLY', sp.outputs['Y'], -1.0), sp.outputs['Z']
def noise(nt, scale, detail=2.0, rough=0.5, seed_off=(0.0, 0.0, 0.0)):
    """object-space noise in [-1, 1]; scale per metre (25 -> ~40 mm features)"""
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise'); nz.noise_dimensions = '3D'
    nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = detail; nz.inputs['Roughness'].default_value = rough
    if any(seed_off):
        vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'ADD'; vm.inputs[1].default_value = seed_off
        nt.links.new(tc.outputs['Object'], vm.inputs[0]); nt.links.new(vm.outputs[0], nz.inputs['Vector'])
    else: nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    return _m(nt, 'MULTIPLY', _m(nt, 'SUBTRACT', nz.outputs['Fac'], 0.5), 2.0)
def local_ao(nt, dist_m, samples=8):
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion'); ao.only_local = True; ao.samples = samples; ao.inputs['Distance'].default_value = dist_m
    return ao.outputs['AO']
def edge_mask(nt, radius_m=0.00025, gain=7.0):
    bev = nt.nodes.new('ShaderNodeBevel'); bev.samples = 8; bev.inputs['Radius'].default_value = radius_m
    geo = nt.nodes.new('ShaderNodeNewGeometry'); dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'
    nt.links.new(bev.outputs['Normal'], dot.inputs[0]); nt.links.new(geo.outputs['Normal'], dot.inputs[1])
    return _m(nt, 'MULTIPLY', _m(nt, 'SUBTRACT', 1.0, dot.outputs['Value']), gain, clamp=True)
def studs(nt, u, v):
    p = META['grid_pitch']; t = META['stud_top'] / 2 / p; b = META['stud_base'] / 2 / p
    def d(c): return _m(nt, 'ABSOLUTE', _m(nt, 'SUBTRACT', _m(nt, 'FRACT', _m(nt, 'MULTIPLY', c, 1.0 / p)), 0.5))
    m = _m(nt, 'MAXIMUM', d(u), d(v))
    return _m(nt, 'MINIMUM', _m(nt, 'MAXIMUM', _m(nt, 'DIVIDE', _m(nt, 'SUBTRACT', b, m), b - t), 0.0), 1.0)
def grip_uv(nt, Y, Z):
    a = math.radians(META['grid_angle_deg']); ca, sa = math.cos(a), math.sin(a)
    return _m(nt, 'SUBTRACT', _m(nt, 'MULTIPLY', Y, ca), _m(nt, 'MULTIPLY', Z, sa)), _m(nt, 'ADD', _m(nt, 'MULTIPLY', Y, sa), _m(nt, 'MULTIPLY', Z, ca))
def side_mask(nt, Y, Z, name):
    img = bpy.data.images.get(name) or bpy.data.images.load(os.path.join(HERE, 'work', name))
    img.colorspace_settings.name = 'Non-Color'
    cb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(_m(nt, 'DIVIDE', _m(nt, 'SUBTRACT', Y, META['y0']), META['y1'] - META['y0']), cb.inputs['X'])
    nt.links.new(_m(nt, 'DIVIDE', _m(nt, 'SUBTRACT', Z, META['z0']), META['z1'] - META['z0']), cb.inputs['Y'])
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img; t.extension = 'CLIP'; t.interpolation = 'Closest'
    nt.links.new(cb.outputs[0], t.inputs['Vector']); return t.outputs['Color']
def stipple(nt, amp=0.035, scale=9000.0):
    return _m(nt, 'MULTIPLY', noise(nt, scale, 3.0, 0.6), amp)
def grip_studs(nt, kind):
    """0..1 stud field for 'frame' / 'backstrap' (None for other kinds)"""
    if kind not in ('frame', 'backstrap'): return None
    X, Y, Z = gxyz(nt); nx, ny, nz = gnormal(nt)
    u, v = grip_uv(nt, Y, Z)
    w_side = _smooth(nt, 0.55, 0.85, _m(nt, 'ABSOLUTE', nx))
    zin = lambda lo, hi: _m(nt, 'MULTIPLY', _m(nt, 'GREATER_THAN', Z, lo), _m(nt, 'LESS_THAN', Z, hi))
    if kind == 'frame':
        left = _m(nt, 'GREATER_THAN', X, 0.0)
        msk = _lerp(nt, side_mask(nt, Y, Z, 'mask_side_R.png'), side_mask(nt, Y, Z, 'mask_side_L.png'), left)
        h_side = _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', studs(nt, u, v), msk), w_side)
        w_fr = _m(nt, 'MULTIPLY', _smooth(nt, 0.30, 0.60, ny), zin(*META['strap_z']))
        w_fr = _m(nt, 'MULTIPLY', w_fr, _m(nt, 'LESS_THAN', _m(nt, 'ABSOLUTE', X), 15.5))
        h_fr = _m(nt, 'MULTIPLY', studs(nt, X, v), w_fr)
        h_th = _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', studs(nt, Y, Z), side_mask(nt, Y, Z, 'mask_thumb.png')), w_side)
        return _m(nt, 'MAXIMUM', _m(nt, 'MAXIMUM', h_side, h_fr), h_th)
    w_bk = _m(nt, 'MULTIPLY', _smooth(nt, 0.2, 0.5, _m(nt, 'MULTIPLY', ny, -1.0)), zin(*META['backstrap_z']))
    h = _m(nt, 'MULTIPLY', studs(nt, X, v), _m(nt, 'MULTIPLY', w_bk, _smooth(nt, 0.55, 0.3, _m(nt, 'ABSOLUTE', nx))))
    return _m(nt, 'MAXIMUM', h, _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', studs(nt, u, v), w_side), zin(*META['backstrap_z'])))

def material(name, look, kind):
    """Principled material: real values + breakup + cavity dust + subtle steel edge wear + grip-texture height bump"""
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    c, r, mt = VAL[look]; metal = look in METALS
    lv = noise(nt, 22.0, 2.0, 0.5)                                   # large-scale value / smudge field (~45 mm)
    hv = noise(nt, 9.0, 1.0, 0.5, (3.1, 7.7, 1.3))                   # hue drift
    fine = noise(nt, 2600.0, 2.0, 0.6, (5.0, 1.0, 9.0))               # micro-roughness (~0.4 mm)
    cav = _m(nt, 'SUBTRACT', 1.0, local_ao(nt, 0.0016))               # 0 open .. 1 deep recess
    cav = _smooth(nt, 0.25, 0.85, cav)
    st = grip_studs(nt, kind)
    # ---------------------------------------------------------------- base colour
    val = _m(nt, 'ADD', 1.0, _m(nt, 'MULTIPLY', lv, 0.06))
    rgb = []
    for i, k in enumerate((1.0, 0.0, -1.0)):                          # tiny hue drift: R and B in opposition
        ch = _m(nt, 'MULTIPLY', val, c[i]); ch = _m(nt, 'MULTIPLY', ch, _m(nt, 'ADD', 1.0, _m(nt, 'MULTIPLY', hv, 0.015 * k)))
        ch = _m(nt, 'MULTIPLY', ch, _m(nt, 'SUBTRACT', 1.0, _m(nt, 'MULTIPLY', cav, 0.32)))          # recess darkening
        ch = _m(nt, 'ADD', ch, _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', cav, 0.010), (1.0, 0.96, 0.90)[i]))   # faint dust
        if st is not None: ch = _m(nt, 'MULTIPLY', ch, _m(nt, 'ADD', 1.0, _m(nt, 'MULTIPLY', _m(nt, 'GREATER_THAN', st, 0.98), 0.25)))
        rgb.append(ch)
    rough = _m(nt, 'ADD', r, _m(nt, 'MULTIPLY', fine, 0.035 if not metal else 0.012))
    rough = _m(nt, 'ADD', rough, _m(nt, 'MULTIPLY', cav, 0.07))
    if look == 'slide': rough = _m(nt, 'ADD', rough, _m(nt, 'MULTIPLY', lv, 0.06))                 # handling smudge +-0.06
    elif metal: rough = _m(nt, 'ADD', rough, _m(nt, 'MULTIPLY', lv, 0.04))
    if st is not None: rough = _m(nt, 'SUBTRACT', rough, _m(nt, 'MULTIPLY', _m(nt, 'GREATER_THAN', st, 0.98), 0.13))   # rubbed stud tops
    metallic = mt
    edge = None
    if metal or kind in ('contact', 'trigger'):
        e = edge_mask(nt, 0.00025)
        conv = _smooth(nt, 0.86, 0.98, local_ao(nt, 0.0015, 6))
        brk = _smooth(nt, -0.15, 0.45, noise(nt, 900.0, 2.0, 0.6, (2.0, 4.0, 6.0)))
        edge = _m(nt, 'MULTIPLY', _m(nt, 'MULTIPLY', _smooth(nt, 0.55, 0.95, e), conv), brk)
    if metal:                                                         # subtle bright steel on the sharpest edges only
        w = _m(nt, 'MULTIPLY', edge, 0.55)
        rgb = [_lerp(nt, ch, WEAR_COL[i], w) for i, ch in enumerate(rgb)]
        rough = _lerp(nt, rough, 0.24, w)
    if kind == 'contact' and edge is not None:                        # polymer contact tops (mag catch): a little glossier
        rough = _m(nt, 'SUBTRACT', rough, _m(nt, 'MULTIPLY', edge, 0.12))
    if kind == 'trigger':                                             # trigger face (forward-facing) rubbed glossier
        X, Y, Z = gxyz(nt); nx, ny, nz = gnormal(nt)
        rough = _m(nt, 'SUBTRACT', rough, _m(nt, 'MULTIPLY', _smooth(nt, 0.4, 0.8, ny), 0.10))
    rough = _m(nt, 'MINIMUM', _m(nt, 'MAXIMUM', rough, 0.12), 0.95)
    cc = nt.nodes.new('ShaderNodeCombineColor')
    for ch, sock in zip(rgb, ('Red', 'Green', 'Blue')): nt.links.new(ch, cc.inputs[sock])
    col_out = cc.outputs[0]
    if kind in ('rsight', 'fsight'):                                  # white paint: U outline (rear), dot (front)
        X, Y, Z = gxyz(nt); nx, ny, nz = gnormal(nt); back = _m(nt, 'LESS_THAN', ny, -0.4)
        if kind == 'rsight':
            outer = _m(nt, 'MULTIPLY', _m(nt, 'LESS_THAN', _m(nt, 'ABSOLUTE', X), 2.45), _m(nt, 'GREATER_THAN', Z, 50.75))
            inner = _m(nt, 'MULTIPLY', _m(nt, 'LESS_THAN', _m(nt, 'ABSOLUTE', X), 1.8), _m(nt, 'GREATER_THAN', Z, 51.35))
            paint = _m(nt, 'MULTIPLY', _m(nt, 'SUBTRACT', outer, inner), back)
        else:
            r2 = _m(nt, 'ADD', _m(nt, 'MULTIPLY', X, X), _m(nt, 'MULTIPLY', _m(nt, 'SUBTRACT', Z, 51.9), _m(nt, 'SUBTRACT', Z, 51.9)))
            paint = _m(nt, 'MULTIPLY', _m(nt, 'LESS_THAN', r2, 1.0), back)
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; nt.links.new(paint, mix.inputs['Factor'])
        nt.links.new(col_out, mix.inputs[6]); mix.inputs[7].default_value = (*VAL['white'][0], 1)
        col_out = mix.outputs[2]
        rough = _lerp(nt, rough, 0.45, paint)
    nt.links.new(col_out, b.inputs['Base Color']); nt.links.new(rough, b.inputs['Roughness'])
    b.inputs['Metallic'].default_value = metallic
    # height -> bump: grip studs + polymer stipple, near-smooth steel
    if st is not None: h = _m(nt, 'ADD', _m(nt, 'MULTIPLY', st, META['stud_height']), stipple(nt, 0.03))
    elif metal or kind in ('rsight', 'fsight'): h = stipple(nt, 0.004, 14000.0)
    else: h = stipple(nt, 0.035)
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Distance'].default_value = 0.001
    nt.links.new(h, bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def kind_of(objname, look):
    n = objname.replace('HI_', '').split('.')[0]
    if n in ('frame', 'backstrap', 'rsight', 'fsight', 'trigger'): return n
    if n in ('magcatchL', 'magcatchR'): return 'contact'
    return 'plain'
