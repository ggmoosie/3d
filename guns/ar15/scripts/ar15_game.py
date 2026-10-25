"""ar15_game.py - pass 3: the game part split.  The game assembles the rifle from a handful of swappable meshes, all built
from the kit parts and exported so that each one attaches at an identity socket on the core:

    SM_AR15_Lower          core item mesh: lower receiver, fire-control parts, pins, grip, buffer tube, castle nut + end
                           plate; carries the gameplay sockets, the identity part sockets and the fallbacks; UCX hulls
                           sized for the default assembled gun (M-LOK + 16 in + A2)
    SM_AR15_Upper          upper receiver (FA housing, deflector), forward assist, dust cover + rod, charging handle, BCG + bolt
    SM_AR15_Barrel16       16 in barrel + nut + low-profile gas block + gas tube   (default)
    SM_AR15_Barrel145      14.5 in barrel + the same nut / block / tube
    SM_AR15_HG_MLOK        15 in M-LOK handguard                                    (default)
    SM_AR15_HG_M4Quad      quad rail + delta ring + A2 front sight base (the FSB swallows the low-profile block)
    SM_AR15_Stock          M4 6-position stock
    SM_AR15_Muzzle_A2      A2 birdcage in the MUZZLE-DEVICE frame: X forward, origin on the barrel's muzzle face,
                           MuzzleSocket at its tip
    SM_AR15_Sights_BUIS_Set   rear BUIS + front flip-up sight, OPTIC frame: Y forward, origin at Optic_Socket (pivot at the
                           bottom), Aim / AimSocket at the rear aperture.  For the M-LOK handguard.
    SM_AR15_Sights_BUIS_Rear  rear BUIS only (the M4Quad's FSB post is its front sight)
    SM_AR15_Sights_BUIS_Set_Stowed   the Set with both leaves folded (pass 4; same frame and sockets; not used yet)
    SM_AR15_Mag30, SM_AR15_Mag30_Loaded, SM_AR15_MagRound   magazine frame: origin on its pivot (= MagazineSocket)

Gun-frame meshes share the F frame (UE axes, cm, INTEGRATION.md origin), so Part_* sockets are identities.  Everything goes
to out/game/ (+ lod/, sockets/), listed in out/game_parts.json for the UE import script."""
import bpy, bmesh, os, json, math, time, subprocess, shutil
import numpy as np
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree
import ar15_lib as L
import ar15_spec as SP
import ar15_sockets as SK
import ar15_assemble as A

GDIR = os.path.join(L.OUT, 'game'); GLOD = os.path.join(GDIR, 'lod'); GSOCK = os.path.join(GDIR, 'sockets')
GBAKE = os.path.join(L.OUT, 'bake', 'game')
for d in (GDIR, GLOD, GSOCK, GBAKE): os.makedirs(d, exist_ok=True)
POST = os.path.join(L.HERE, 'ar15_post.py')

def log(*a): L.log(*a)

LOWER = ['SM_AR15_LowerReceiver', 'SM_AR15_Trigger', 'SM_AR15_Selector', 'SM_AR15_MagCatch', 'SM_AR15_BoltCatch', 'SM_AR15_LowerPins',
         'SM_AR15_Grip', 'SM_AR15_BufferTube', 'SM_AR15_CastleNut']
UPPER = ['SM_AR15_UpperReceiver', 'SM_AR15_ForwardAssist', 'SM_AR15_DustCover', 'SM_AR15_DustCoverRod', 'SM_AR15_BCG', 'SM_AR15_Bolt',
         'SM_AR15_ChargingHandle']
BARREL_COMMON = ['SM_AR15_BarrelNut', 'SM_AR15_GasBlockLP', 'SM_AR15_GasTube']
GAME = [
    dict(name='SM_AR15_Lower', parts=LOWER, frame='gun', label='Lower (core)', attach=None),
    dict(name='SM_AR15_Upper', parts=UPPER, frame='gun', label='Upper', attach=('SM_AR15_Lower', 'Part_Upper')),
    dict(name='SM_AR15_Barrel16', parts=['SM_AR15_Barrel16'] + BARREL_COMMON, frame='gun', label='16 in barrel', attach=('SM_AR15_Upper', 'Part_Barrel')),
    dict(name='SM_AR15_Barrel145', parts=['SM_AR15_Barrel'] + BARREL_COMMON, frame='gun', label='14.5 in barrel', attach=('SM_AR15_Upper', 'Part_Barrel')),
    dict(name='SM_AR15_HG_MLOK', parts=['SM_AR15_HandguardMLOK'], frame='gun', label='15 in M-LOK handguard', attach=('SM_AR15_Upper', 'Part_Handguard')),
    dict(name='SM_AR15_HG_M4Quad', parts=['SM_AR15_HandguardQuad', 'SM_AR15_DeltaRing', 'SM_AR15_FrontSightBase'], frame='gun',
         label='M4 quad rail + delta ring + A2 FSB', attach=('SM_AR15_Upper', 'Part_Handguard')),
    dict(name='SM_AR15_Stock', parts=['SM_AR15_Stock'], frame='gun', label='M4 6-position stock', attach=('SM_AR15_Lower', 'Part_Stock')),
    dict(name='SM_AR15_Muzzle_A2', parts=['SM_AR15_Birdcage'], frame='muzzle', label='A2 birdcage', attach=('<barrel>', 'Muzzle')),
    dict(name='SM_AR15_Sights_BUIS_Set', parts=['SM_AR15_BUIS', 'SM_AR15_FrontBUIS'], frame='optic', label='BUIS rear + front (M-LOK)',
         attach=('SM_AR15_Lower', 'Optic_Socket')),
    dict(name='SM_AR15_Sights_BUIS_Rear', parts=['SM_AR15_BUIS'], frame='optic', label='BUIS rear only (M4Quad: FSB post in front)',
         attach=('SM_AR15_Lower', 'Optic_Socket')),
    dict(name='SM_AR15_Sights_BUIS_Set_Stowed', parts=['SM_AR15_BUIS', 'SM_AR15_FrontBUIS'], frame='optic', fold=True,
         label='BUIS rear + front, both leaves folded (stowed; not used yet)', attach=('SM_AR15_Lower', 'Optic_Socket')),
    dict(name='SM_AR15_Mag30', parts=['SM_AR15_Mag30'], frame='magazine', label='30-round magazine', attach=('SM_AR15_Lower', 'MagazineSocket')),
    dict(name='SM_AR15_Mag30_Loaded', parts=['SM_AR15_Mag30', 'SM_AR15_MagRound'], frame='magazine', label='30-round magazine, loaded',
         attach=('SM_AR15_Lower', 'MagazineSocket')),
    dict(name='SM_AR15_MagRound', parts=['SM_AR15_MagRound'], frame='magazine', label='top cartridge (toggle)', attach=('SM_AR15_Lower', 'MagazineSocket')),
]
DEFAULT = ['SM_AR15_Lower', 'SM_AR15_Upper', 'SM_AR15_Barrel16', 'SM_AR15_HG_MLOK', 'SM_AR15_Stock', 'SM_AR15_Muzzle_A2',
           'SM_AR15_Sights_BUIS_Set', 'SM_AR15_Mag30_Loaded']
QUADSET = ['SM_AR15_Lower', 'SM_AR15_Upper', 'SM_AR15_Barrel145', 'SM_AR15_HG_M4Quad', 'SM_AR15_Stock', 'SM_AR15_Muzzle_A2',
           'SM_AR15_Sights_BUIS_Rear', 'SM_AR15_Mag30_Loaded']
NEG_G2F = (-SP.G2F[0], -SP.G2F[1], -SP.G2F[2])         # the F origin in G mm

# ------------------------------------------------------------------------------------------------ frames
def optic_g():
    up = L.PARTS['SM_AR15_UpperReceiver']; rx = list(up.rail_slots); mid = (rx[0] + rx[-1]) / 2.0
    return (0.0, min(rx, key=lambda y: abs(y - mid)), SP.RAIL_TOP)

def frame_origin_g(frame):
    return {'gun': None, 'muzzle': (0.0, SP.BARREL_END, 0.0), 'optic': optic_g(), 'magazine': A_MAG_SOCKET()}.get(frame)

def A_MAG_SOCKET():
    import parts_rear as PR; return PR.MAG_SOCKET

def data_matrix(frame):
    """Blender-space matrix taking gun-frame mesh data into the part's local frame (rigid, so custom normals follow)"""
    o = frame_origin_g(frame)
    if o is None: return None
    ob = L.g2b(o)
    if frame == 'muzzle': return Matrix.Rotation(math.radians(90.0), 4, 'Z') @ Matrix.Translation(-ob)
    return Matrix.Translation(-ob)

def g_local(g, frame):
    """a G-frame point -> the fake G point whose g2f() is the point's coordinate in the part's local UE frame"""
    o = frame_origin_g(frame)
    if o is None: return tuple(g)
    d = [g[i] - o[i] for i in range(3)]
    if frame == 'muzzle': d = [d[1], -d[0], d[2]]
    return tuple(d[i] + NEG_G2F[i] for i in range(3))

# ------------------------------------------------------------------------------------------------ meshes
def fold_info():
    """pass 4: hinge pivots of the two flip-up leaves in the optic frame (cm, UE axes) for a later animated / stowed swap"""
    o = frame_origin_g('optic'); out = {}
    for n, key in (('SM_AR15_BUIS', 'rear'), ('SM_AR15_FrontBUIS', 'front')):
        P = L.PARTS.get(n); f = getattr(P, 'fold', None) if P else None
        if not f: continue
        p = f['axis_point']
        out[key] = dict(pivot_cm=[round((p[i] - o[i]) / 10.0, 3) for i in range(3)], axis='X (through the pivot)', angle_deg=abs(f['angle']),
                        leaf_top_goes='+Y (forward)' if f['angle'] < 0 else '-Y (rearward)')
    return out

def fold_copy(name, collection=None):
    """copy of a sight part with its leaf folded: the vertices of the pieces listed in P.fold (per-vertex '_piece', set by
    finalize) rotate about the hinge axis (G X through P.fold['axis_point']) by P.fold['angle'] (G degrees, right-handed
    about +X); the loop normals rotate with them so the weighted normals survive"""
    P = L.PARTS[name]; f = P.fold; o = P.obj
    c = o.copy(); c.data = o.data.copy(); (collection or bpy.context.scene.collection).objects.link(c); me = c.data
    pid = np.empty(len(me.vertices), np.int64); me.attributes['_piece'].data.foreach_get('value', pid)
    sel = np.isin(pid, f['pieces'])
    R3 = Matrix.Rotation(math.radians(-f['angle']), 3, 'X')         # G Rx(a) == Blender Rx(-a) (Y mirror)
    piv = L.g2b(f['axis_point']); M = Matrix.Translation(piv) @ R3.to_4x4() @ Matrix.Translation(-piv)
    me.calc_normals_split()
    ln = np.empty(len(me.loops) * 3); me.loops.foreach_get('normal', ln); ln = ln.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
    R = np.array(R3); lsel = sel[lv]; ln[lsel] = ln[lsel] @ R.T
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    Mn = np.array(M); co[sel] = co[sel] @ Mn[:3, :3].T + Mn[:3, 3]
    me.vertices.foreach_set('co', co.ravel()); me.update()
    me.normals_split_custom_set([tuple(v) for v in ln])
    return c

def build_meshes():
    col = L.coll('AR15_Game'); out = {}
    for d in GAME:
        if d.get('fold'):
            tmp = [fold_copy(n) for n in d['parts']]
            o = A.join_copies(tmp, d['name'] + '__game', col)
            for t in tmp: L.kill(t)
        else:
            o = A.join_copies([L.PARTS[n].obj for n in d['parts']], d['name'] + '__game', col)
        M = data_matrix(d['frame'])
        if M is not None: o.data.transform(M)
        nm, inv, degen, shells = L.topo_check(o.data)
        out[d['name']] = dict(obj=o, tris=L.tri_count(o.data), slots=[m.name for m in o.data.materials], frame=d['frame'], parts=d['parts'],
                              label=d['label'], attach=d['attach'], hulls=[], shells=shells, nm=nm, inv=inv, degen=degen)
        log('GAME %-26s tris %6d  shells %3d  nm %d inv %d degen %d  slots %s  frame %s' % (d['name'], out[d['name']]['tris'], shells, nm, inv, degen,
                                                                                       ','.join(out[d['name']]['slots']), d['frame']))
    for set_name, names in (('default', DEFAULT), ('m4quad', QUADSET)):
        log('GAME assembled %-8s %6d tris (%s)' % (set_name, sum(out[n]['tris'] for n in names), ', '.join(n.replace('SM_AR15_', '') for n in names)))
    return out

# ------------------------------------------------------------------------------------------------ sockets
def _copy(s, **kw):
    t = dict(s); t.update(kw); return t

def _local(s, frame, **kw):
    """re-express a G-frame socket dict in a part's local frame"""
    if frame in ('gun', None): return _copy(s, **kw)
    g = g_local(s['g_mm'], frame)
    X, Z = V(s['x_axis']), V(s['z_axis'])
    if frame == 'muzzle': X, Z = V((X.y, -X.x, X.z)), V((Z.y, -Z.x, Z.z))
    t = SK.S(s['name'], g, X=tuple(X), Z=tuple(Z), scale=tuple(s['scale']), tag=s['tag'], part=s['part'], check=s.get('check'),
             note=s.get('note', ''), nrm=None)
    t.update(kw); return t

def sockets(game):
    lm = {s['name']: s for s in SK.layout('MLOK', L.PARTS)}; lq = {s['name']: s for s in SK.layout('QUAD', L.PARTS)}
    S, FWD = SK.S, SK.FWD
    ident = lambda nm, note: S(nm, NEG_G2F, rot=(0, 0, 0), check=None, note='identity part socket (shared gun frame): ' + note)
    out = {}
    # --- core: gameplay sockets, the identity part sockets, fallbacks for code that only reads the core mesh
    hg = L.PARTS['SM_AR15_HandguardMLOK']; hs = hg.slots
    q0, q1 = SP.QUAD
    inside = [y for y in hs['mlok'] if q0 + 16.0 <= y <= q1 - 16.0]            # M-LOK stations where the quad also has rail
    gy = min(inside, key=lambda y: abs(y - (SP.MLOK_REAR + SP.MLOK_LEN / 3.0)))
    sup_z = (SP.MLOK_TOP + SP.MLOK_BOT) / 2.0; radius = (2 * SP.MLOK_HALF_W + (SP.RAIL_TOP - SP.MLOK_BOT)) / 4.0
    gl_side = V((0.55, 0.0, -0.83)).normalized()
    fb = 'fallback for code that only reads the core mesh; '
    lower = [lm[n] for n in ('MagazineSocket', 'Trigger', 'GripCyl_R', 'RightHandSocket', 'MagRelease', 'BoltCatch', 'Selector')]
    lower += [_copy(lm['Stock'], check=None, note=lm['Stock']['note'] + ' (geometry on SM_AR15_Stock)'),
              _copy(lm['Butt'], check=None, note=lm['Butt']['note'] + ' (geometry on SM_AR15_Stock)'),
              ident('Part_Upper', 'SM_AR15_Upper'), ident('Part_Stock', 'SM_AR15_Stock'),
              S('Muzzle', (0.0, SP.MUZZLE16_Y, 0.0), rot=FWD, check=None, note=fb + 'tip of the A2 on the 16 in barrel (default build); the barrels carry their own Muzzle at the muzzle face'),
              _copy(lm['Chamber'], note=fb + lm['Chamber']['note']),
              _copy(lm['Optic_Socket'], check=None, note=fb + lm['Optic_Socket']['note']),
              _copy(lm['Aim'], check=None, note=fb + 'rear BUIS aperture (SM_AR15_Sights_BUIS_*)'),
              _copy(lm['Eye'], note=fb + lm['Eye']['note']),
              _copy(lm['EjectionSocket'], check=None, note=fb + lm['EjectionSocket']['note']),
              S('Grip_Socket', (0.0, gy, hs['mlok_bot_z']), rot=FWD, check=None,
                note=fb + '6 o\'clock M-LOK slot inside the quad rail span (Y %.1f); on the M4Quad the bottom rail surface is %.1f mm lower' % (gy, SP.QUAD_R + hs['mlok_bot_z'])),
              S('TacticalSocket', (-hs['mlok_side_x'], gy, hs['mlok_side_z']), rot=(270, 0, 0), check=None,
                note=fb + '3 o\'clock M-LOK slot inside the quad span; on the M4Quad the right rail surface is %.1f mm further out' % (SP.QUAD_R - hs['mlok_side_x'])),
              S('LeftHandSocket', (0.0, gy, sup_z - radius), rot=FWD, check=None, note=fb + 'AI left-hand target under the handguard'),
              S('GripCyl_L', (0.0, gy, sup_z), X=(0, 1, 0), Z=tuple(V((0, 1, 0)).cross(gl_side)), scale=(round(radius / 10, 3), 5.0, 1.0),
                check=None, note=fb + 'support-hand cylinder at the Grip_Socket station')]
    out['SM_AR15_Lower'] = lower
    # --- upper
    rx = [s for n, s in lm.items() if n.startswith('Rail_Top_') and s['part'] == 'SM_AR15_UpperReceiver']
    out['SM_AR15_Upper'] = ([lm['Optic_Socket']] + [_copy(s, check='rail', note='receiver rail slot' + (' (under the BUIS base when fitted)' if s['check'] is None else ''))
                                                    for s in sorted(rx, key=lambda s: s['name'])] +
                            [lm['EjectionSocket'], lm['ChargingHandle'], lm['ForwardAssist'], lm['Eye'],
                             _copy(lm['Aim'], check=None, note='fallback sight line with no optic: rear BUIS aperture (SM_AR15_Sights_BUIS_*)'),
                             ident('Part_Barrel', 'SM_AR15_Barrel16 / SM_AR15_Barrel145'), ident('Part_Handguard', 'SM_AR15_HG_MLOK / SM_AR15_HG_M4Quad')])
    # --- barrels: Muzzle on their own muzzle face, Chamber
    for name, end in (('SM_AR15_Barrel16', SP.BARREL16_END), ('SM_AR15_Barrel145', SP.BARREL_END)):
        out[name] = [S('Muzzle', (0.0, end, 0.0), rot=FWD, part=name, check='muzzle',
                       note='barrel muzzle face on the bore axis; muzzle devices attach here (X forward, pivot on this face)'),
                     _copy(lm['Chamber'])]
    # --- handguards
    for name, lay, hgp in (('SM_AR15_HG_MLOK', lm, 'SM_AR15_HandguardMLOK'), ('SM_AR15_HG_M4Quad', lq, 'SM_AR15_HandguardQuad')):
        keep = ['Grip_Socket', 'TacticalSocket', 'LeftHandSocket', 'GripCyl_L', 'Support_Default']
        socks = [lay[n] for n in keep]
        if name == 'SM_AR15_HG_MLOK':     # alone (no barrel inside), the axis rays would leave through the 3/6/9 slots: use the diagonals
            socks = [_copy(x, check='inside_diag') if x['name'] == 'GripCyl_L' else x for x in socks]
        socks += [s for n, s in sorted(lay.items()) if (n.startswith('Rail_') or n.startswith('Mlok_')) and s['part'] == hgp]
        out[name] = socks
    out['SM_AR15_Stock'] = [lm['Stock'], lm['Butt']]
    # --- muzzle device (local: X forward, origin on the barrel's muzzle face)
    tip = SP.MUZZLE_Y - SP.BARREL_END
    out['SM_AR15_Muzzle_A2'] = [S('MuzzleSocket', (tip - SP.G2F[0], -SP.G2F[1], -SP.G2F[2]), rot=(0, 0, 0), check='tip_x',
                                  note='tip of the A2 birdcage, %.1f mm ahead of the barrel muzzle face; X forward' % tip)]
    # --- sights (local: optic frame, origin at Optic_Socket)
    for name in ('SM_AR15_Sights_BUIS_Set', 'SM_AR15_Sights_BUIS_Rear'):
        a = lm['Aim']
        out[name] = [_local(a, 'optic', name='Aim', note='rear aperture on the sight line (front post / FSB post at the same height)'),
                     _local(a, 'optic', name='AimSocket', note='same as Aim (alias)')]
    a = lm['Aim']                     # stowed: same sockets so a mesh swap keeps the Aim line; no aperture there to check
    out['SM_AR15_Sights_BUIS_Set_Stowed'] = [
        _local(a, 'optic', name='Aim', check=None, note='sight line where the deployed rear aperture sits (leaves folded: no sight picture)'),
        _local(a, 'optic', name='AimSocket', check=None, note='same as Aim (alias)')]
    for name in ('SM_AR15_Mag30', 'SM_AR15_Mag30_Loaded', 'SM_AR15_MagRound'): out[name] = []
    return out

def write_sockets(game, socks):
    paths = {}
    for name, D in game.items():
        J = dict(mesh=name, units='cm', frame=FRAME_TEXT[D['frame']],
                 rotator='FRotator (pitch, yaw, roll) degrees; x/y/z_axis = the resulting socket axes in mesh space',
                 import_hint='unreal.StaticMeshSocket: relative_location = loc, relative_rotation = Rotator(pitch=, yaw=, roll=), tag = tag',
                 attach=dict(parent=D['attach'][0], socket=D['attach'][1]) if D['attach'] else None,
                 sockets=[{k: v for k, v in s.items() if k not in ('check', 'part')} for s in socks[name]])
        p = os.path.join(GSOCK, 'sockets_%s.json' % name); json.dump(J, open(p, 'w'), indent=1); paths[name] = p
    return paths

FRAME_TEXT = {
    'gun': 'shared gun frame (UE: +X gun left, +Y muzzle, +Z up; INTEGRATION.md origin, bore at z 12.14): attach at identity',
    'muzzle': 'muzzle-device frame: +X forward along the bore, origin on the barrel muzzle face (the barrel\'s Muzzle socket), +Z up',
    'optic': 'optic frame: +Y forward, +Z up, origin at Optic_Socket (pivot at the bottom, on the rail top)',
    'magazine': 'magazine frame: origin on the pivot = MagazineSocket (same convention as SM_M4_Mag), UE axes',
}

# ------------------------------------------------------------------------------------------------ collision (core only)
def lower_hulls(game):
    """UCX hulls on SM_AR15_Lower for the pickup, sized for the default assembled gun (M-LOK + 16 in barrel + A2)"""
    o = game['SM_AR15_Lower']['obj']; c = lambda n: A.coords(L.PARTS[n].obj)
    cage = c('SM_AR15_Birdcage').copy(); cage[:, 1] -= SP.BARREL16_EXT * L.MM            # the A2 on the 16 in barrel
    b16 = c('SM_AR15_Barrel16'); yb = -b16[:, 1] * 1000 - SP.G2F[1]
    groups = [
        ('receiver', np.concatenate([c(n) for n in ('SM_AR15_LowerReceiver', 'SM_AR15_UpperReceiver', 'SM_AR15_ChargingHandle', 'SM_AR15_BUIS')])),
        ('handguard', c('SM_AR15_HandguardMLOK')),
        ('barrel', np.concatenate([cage, b16[yb > SP.MLOK_REAR + SP.MLOK_LEN - 10]])),
        ('stock', np.concatenate([c(n) for n in ('SM_AR15_Stock', 'SM_AR15_BufferTube', 'SM_AR15_CastleNut')])),
        ('grip', c('SM_AR15_Grip')),
    ]
    hulls = []
    for i, (lab, pts) in enumerate(groups):
        if lab == 'receiver': pts = pts[pts[:, 2] < (SP.RAIL_TOP + 8.0 + SP.G2F[2]) * L.MM]
        hb = None
        for nd in (56, 40, 26):
            if hb is not None: hb.free()
            hb = L.hull_bm(L.support_pts([V(p) for p in pts], nd))
            if L._bm_convexity(hb) < 1e-6: break
        log('HULL SM_AR15_Lower %-9s %3d verts  convexity %.2e m' % (lab, len(hb.verts), L._bm_convexity(hb)))
        ho = L.bm_obj(hb, 'UCX_SM_AR15_Lower_%02d' % i, L.coll('AR15_Game')); ho.parent = o; ho.hide_render = True; ho['hull'] = lab
        hulls.append(ho)
    game['SM_AR15_Lower']['hulls'] = hulls
    return hulls

# ------------------------------------------------------------------------------------------------ FSB vs low-profile block
def fsb_covers_lpgb():
    """the quad build puts the A2 FSB over the barrel's low-profile gas block: every exposed sample of the block (all its
    vertices and face centres outside the barrel journal) must lie inside the FSB solid (ray parity) and at least 0.3 mm
    under its surface (no z-fighting).  Same block on both barrels (same gas port), checked once per barrel mesh."""
    f = L.PARTS['SM_AR15_FrontSightBase'].obj; g = L.PARTS['SM_AR15_GasBlockLP'].obj
    fv = [V(p) for p in A.coords(f)]; bvh = BVHTree.FromPolygons(fv, [list(p.vertices) for p in f.data.polygons])
    pts = [V(p) for p in A.coords(g)] + [p.center.copy() for p in g.data.polygons]
    bore_c = L.g2b((0.0, 0.0, 0.0)); tube_c = L.g2b((0.0, 0.0, SP.GAS_Z))
    res = dict(samples=0, outside=0, too_close=0, min_depth_mm=1e9)
    for p in pts:
        r = math.hypot(p.x - bore_c.x, p.z - bore_c.z) * 1000
        if r < 10.2: continue                                                   # journal bore: covered by the barrel itself
        if math.hypot(p.x - tube_c.x, p.z - tube_c.z) * 1000 < 2.7: continue    # gas-tube socket: filled by the gas tube
        res['samples'] += 1
        hits = 0; o_ = p.copy(); d = V((1.0, 0.0, 0.0))
        while True:
            loc, n, i, t = bvh.ray_cast(o_, d, 1.0)
            if loc is None: break
            hits += 1; o_ = loc + d * 1e-6
        loc, n, i, dist = bvh.find_nearest(p)
        depth = dist * 1000 if loc is not None else 0.0
        if hits % 2 == 0: res['outside'] += 1
        elif depth < 0.3: res['too_close'] += 1
        res['min_depth_mm'] = min(res['min_depth_mm'], depth if hits % 2 == 1 else -depth)
    res['min_depth_mm'] = round(res['min_depth_mm'], 3)
    res['ok'] = res['outside'] == 0 and res['too_close'] == 0
    log('CHECK FSB covers the low-profile block: %d samples, %d outside, %d within 0.3 mm, min depth %.2f mm  %s' %
        (res['samples'], res['outside'], res['too_close'], res['min_depth_mm'], 'OK' if res['ok'] else 'FAIL'))
    return res

# ------------------------------------------------------------------------------------------------ bakes (one texture set per atlas)
def bake(at):
    """one mask set per atlas for the game kit, so every game mesh shares the same textures:
      context A = the default assembly (Lower, Upper, 16 in barrel, M-LOK, stock, A2 at 16 in, BUIS set) bakes every
                  atlas it covers;
      context B = the quad build: the 14.5 in barrel, quad rail, delta ring and FSB baked with the rest of that build as
                  occluders; Kit_Steel takes B inside those parts' UV islands (rasterised, +1 px) and A elsewhere;
      the magazine's own atlases come from the loaded-magazine bake (out/bake/SM_AR15_Mag30_*)"""
    import ar15_bake as B
    t0 = time.time(); B.setup_cycles(64)
    def place(names, shift16=False):
        objs = []
        for n in names:
            c = L.PARTS[n].obj.copy(); c.data = L.PARTS[n].obj.data.copy(); bpy.context.scene.collection.objects.link(c)
            if shift16 and n == 'SM_AR15_Birdcage': c.data.transform(Matrix.Translation((0.0, -SP.BARREL16_EXT * L.MM, 0.0)))
            objs.append(c)
        A.select_only(objs, objs[0])
        if len(objs) > 1:
            with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]): bpy.ops.object.join()
        A.reorder_slots(objs[0]); return objs[0]
    atlas_of_slot = lambda slot, hgname: 'MLOK_Handguard' if slot == 'Handguard' and hgname == 'MLOK' else ('M4Quad_Handguard' if slot == 'Handguard' else 'Kit_%s' % slot)
    a_parts = LOWER + UPPER + ['SM_AR15_Barrel16'] + BARREL_COMMON + ['SM_AR15_HandguardMLOK', 'SM_AR15_Stock', 'SM_AR15_Birdcage',
                                                                       'SM_AR15_BUIS', 'SM_AR15_FrontBUIS']
    oa = place(a_parts, shift16=True); oa.name = '_game_bake_A'
    sizes = {m.name: at[atlas_of_slot(m.name, 'MLOK')]['texture'] for m in oa.data.materials}
    names = lambda tag: {m.name: os.path.join(GBAKE, '%s_%s.png' % (atlas_of_slot(m.name, 'MLOK'), tag)) for m in oa.data.materials}
    B.bake_object(oa, 'AO', sizes, 'GA', samples=96, tag='AO', names=names('AO'))
    B.bake_object(oa, 'EMIT', sizes, 'GA', shader=B.curvature_shader, samples=24, tag='Curv', names=names('Curv'))
    if os.path.exists(B.MARKINGS):
        B.bake_object(oa, 'NORMAL', sizes, 'GA', shader=B.receiver_bump_shader, slots=['Receiver'], samples=8, tag='N', names=names('N'))
    B.bake_object(oa, 'NORMAL', sizes, 'GA', shader=B.polymer_bump_shader, slots=['Polymer'], samples=8, tag='N', names=names('N'))
    # context B
    b_target = ['SM_AR15_Barrel', 'SM_AR15_HandguardQuad', 'SM_AR15_DeltaRing', 'SM_AR15_FrontSightBase']
    ob = place(b_target); ob.name = '_game_bake_B'
    occ = place(LOWER + UPPER + BARREL_COMMON + ['SM_AR15_Stock', 'SM_AR15_Birdcage', 'SM_AR15_BUIS']); occ.name = '_game_bake_B_occ'
    sizes = {m.name: at[atlas_of_slot(m.name, 'QUAD')]['texture'] for m in ob.data.materials}
    nb = lambda tag: {m.name: (os.path.join(GBAKE, '_B_Kit_Steel_%s.png' % tag) if m.name == 'Steel' else
                               os.path.join(GBAKE, '%s_%s.png' % (atlas_of_slot(m.name, 'QUAD'), tag))) for m in ob.data.materials}
    B.bake_object(ob, 'AO', sizes, 'GB', samples=96, tag='AO', occluders=[occ], names=nb('AO'))
    B.bake_object(ob, 'EMIT', sizes, 'GB', shader=B.curvature_shader, samples=24, tag='Curv', occluders=[occ], names=nb('Curv'))
    # composite Kit_Steel: B inside the B parts' Steel islands
    me = ob.data; si = [i for i, m in enumerate(me.materials) if m.name == 'Steel'][0]
    uv = A.uv_array(me); tris = []
    for p in me.polygons:
        if p.material_index != si: continue
        ls = list(p.loop_indices)
        for k in range(1, len(ls) - 1): tris.append([uv[ls[0]], uv[ls[k]], uv[ls[k + 1]]])
    tp = os.path.join(GBAKE, '_B_steel_tris.npy'); np.save(tp, np.array(tris, np.float32))
    for tag in ('AO', 'Curv'):
        r = subprocess.run(['python', POST, 'composite', os.path.join(GBAKE, 'Kit_Steel_%s.png' % tag), os.path.join(GBAKE, '_B_Kit_Steel_%s.png' % tag),
                            tp, os.path.join(GBAKE, 'Kit_Steel_%s.png' % tag), '1'], capture_output=True, text=True)
        if r.returncode: log('composite FAILED', r.stderr[-800:])
    for o in (oa, ob, occ): L.kill(o)
    for f_ in os.listdir(GBAKE):
        if f_.startswith('_B_'): os.remove(os.path.join(GBAKE, f_))
    # the magazine atlases from the loaded-magazine bake
    for slot, atl in (('Receiver', 'Mag30_Receiver'), ('Steel', 'Mag30_Steel'), ('Polymer', 'Mag30_Polymer'), ('Brass', 'MagRound_Brass')):
        for tag in ('AO', 'Curv'):
            src = os.path.join(B.BAKE, 'SM_AR15_Mag30_%s_%s.png' % (slot, tag))
            if os.path.exists(src): shutil.copyfile(src, os.path.join(GBAKE, '%s_%s.png' % (atl, tag)))
    r = subprocess.run(['python', POST, 'packmasks', GBAKE], capture_output=True, text=True)
    log('GAME BAKES done in %.1fs  %s' % (time.time() - t0, r.stdout.strip()))
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

def textures(D, at):
    """per slot of a game mesh: its atlas and the game mask files"""
    out = {}
    for slot in D['slots']:
        part = next(n for n in D['parts'] if slot in L.PARTS[n].info['slots'])
        atl = A.atlas_of(part, slot); t = dict(atlas=atl, size=at[atl]['texture'])
        for tag in ('AO', 'Curv', 'N', 'Masks'):
            p = os.path.join(GBAKE, '%s_%s.png' % (atl, tag))
            if os.path.exists(p): t[tag.lower()] = os.path.relpath(p, L.OUT).replace('\\', '/')
        out[slot] = t
    return out

# ------------------------------------------------------------------------------------------------ export
def _named(name, o):
    """temporarily give the game object its exact mesh name (a kit part may hold it: SM_AR15_Stock, SM_AR15_Mag30, ...)"""
    clash = bpy.data.objects.get(name)
    if clash is not None and clash is not o: clash.name = name + '__keep'
    old = o.name; o.name = name; o.data.name = name
    return clash, old

def _unname(name, o, clash, old):
    o.name = old
    if clash is not None: clash.name = name

def export(game, socks, lods, at, fsb):
    sp = write_sockets(game, socks); manifest = {}; listing = []
    for name, D in game.items():
        o = D['obj']; clash, old = _named(name, o)
        path = os.path.join(GDIR, name + '.fbx'); A.export_fbx([o] + D['hulls'], path)
        co = A.coords(o)
        manifest[name] = dict(fbx=path, tris=D['tris'], slots=D['slots'], hulls=[h.name for h in D['hulls']], lo=co.min(0).tolist(),
                              hi=co.max(0).tolist(), frame=D['frame'])
        _unname(name, o, clash, old)
        lod_paths = []
        for lab in ('LOD1', 'LOD2'):
            lo_, info = lods[name][lab]
            lp = os.path.join(GLOD, '%s_%s.fbx' % (name, lab)); A.export_fbx([lo_], lp); lod_paths.append(lp)
            manifest['%s_%s' % (name, lab)] = dict(fbx=lp, lod=True, **info)
        rel = lambda p: os.path.relpath(p, L.OUT).replace('\\', '/')
        gd = next(d for d in GAME if d['name'] == name); extra = {}
        if 'SM_AR15_BUIS' in D['parts']:
            fi = fold_info(); extra['fold'] = {k: v for k, v in fi.items() if k == 'rear' or 'SM_AR15_FrontBUIS' in D['parts']}
            if gd.get('fold'): extra['stowed'] = True
        listing.append(dict(name=name, label=D['label'], fbx=rel(path), lods=[rel(p) for p in lod_paths], sockets=rel(sp[name]),
                            slots=D['slots'], tris=D['tris'], lod_tris=[lods[name]['LOD1'][1]['tris'], lods[name]['LOD2'][1]['tris']],
                            frame=D['frame'], frame_note=FRAME_TEXT[D['frame']], parts=D['parts'],
                            attach=dict(parent=D['attach'][0], socket=D['attach'][1]) if D['attach'] else None,
                            collision=[h.name for h in D['hulls']] or None, textures=textures(D, at),
                            socket_names=[s['name'] for s in socks[name]], **extra))
    J = dict(note='LootNShoot AR-15 game parts (pass 3; pass 4: MBUS-style polymer sights + SM_AR15_Sights_BUIS_Set_Stowed; pass 4b: '
                  'fire-control group fixed). Paths are relative to Tools/bpy/ar15/out/. Units cm, UE axes. '
                  'Gun-frame meshes attach at identity sockets (Part_*); the muzzle device, sights and magazines have their own frames.',
             default_build=DEFAULT, m4quad_build=QUADSET,
             slots=SP.ALL_SLOTS, brass_slot_only_on=list(SP.BRASS_MESHES),
             texel_px_per_cm=dict(Receiver=at['Kit_Receiver']['texel_px_per_cm'], Handguard=at['MLOK_Handguard']['texel_px_per_cm'],
                                  Steel=at['Kit_Steel']['texel_px_per_cm'], Polymer=at['Kit_Polymer']['texel_px_per_cm'], BCG=at['Kit_BCG']['texel_px_per_cm']),
             assembled_tris=dict(default=sum(game[n]['tris'] for n in DEFAULT), m4quad=sum(game[n]['tris'] for n in QUADSET)),
             checks=dict(fsb_covers_lpgb=fsb), meshes=listing)
    p = os.path.join(L.OUT, 'game_parts.json'); json.dump(J, open(p, 'w'), indent=1)
    log('GAME exported %d meshes -> %s' % (len(listing), os.path.relpath(p, L.OUT)))
    return manifest, J

def make_lods(game):
    out = {}
    for name, D in game.items():
        out[name] = {}
        for ratio, lab in ((0.5, 'LOD1'), (0.2, 'LOD2')):
            o, info = A.make_lod(D, ratio, lab); o.name = '%s_%s' % (name, lab); o.data.name = o.name; o.hide_render = True
            for c in o.users_collection: c.objects.unlink(o)
            L.coll('AR15_Game').objects.link(o)
            out[name][lab] = (o, info)
    return out

def run(bake_maps=True):
    t0 = time.time()
    at = A.REPORT['atlases']
    game = build_meshes()
    fsb = fsb_covers_lpgb()
    socks = sockets(game)
    lower_hulls(game)
    lods = make_lods(game)
    if bake_maps: bake(at)
    manifest, J = export(game, socks, lods, at, fsb)
    mp = os.path.join(L.OUT, '_export_manifest.json'); M = json.load(open(mp))
    M['game'] = {n: e for n, e in manifest.items() if not e.get('lod')}; M['game_lods'] = {n: e for n, e in manifest.items() if e.get('lod')}
    json.dump(M, open(mp, 'w'), indent=1)
    A.REPORT['game'] = dict(meshes={n: dict(tris=D['tris'], slots=D['slots'], frame=D['frame']) for n, D in game.items()},
                            assembled_tris=J['assembled_tris'], fsb_covers_lpgb=fsb)
    json.dump(A.REPORT, open(os.path.join(L.OUT, 'assembly_report.json'), 'w'), indent=1, default=str)
    log('GAME done in %.1fs' % (time.time() - t0))
    return game, socks, J
