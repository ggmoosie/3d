"""landmarks.py - camera_match.py inputs for the four reference photos (system python).
Each landmark: photo pixel (read with pxgrid.py crops) + its 3-D model position in the G frame (mm), written as Blender
world metres (x, -y, z)/1000.  Solve points are rigid slide / sight / muzzle features; grip and frame points are "check"
points (their error measures shape differences).  usage: python landmarks.py <pass> <blend_for_render> [views]"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import g17v4_spec as G
REF = os.path.abspath(os.path.join(HERE, '..', 'refs_user'))
PASS = sys.argv[1] if len(sys.argv) > 1 else 'p1'
VIEWS = sys.argv[3].split(',') if len(sys.argv) > 3 else ['right']
HW, ZSB, ZST, YS0, YS1 = G.SLIDE_HW, G.ZSB, G.ZST, G.YS0, G.YS1

def gpx(px, x):
    """photo px on the right-side reference -> G point (x given)"""
    y, z = G.px2g([px])[0]; return (x, float(y), float(z))
def W(g): return [g[0] / 1000.0, -g[1] / 1000.0, g[2] / 1000.0]

V = {}
# ---- right side (profile master): pixels from the trace; G through the same homography
V['right'] = dict(ref='../v4/work/ref_right_clean.png', dir=[1, 0, 0], f=600, frange=[100, 4000], pts=[
    ('muzzle', (1548.0, 170.5), (0.0, G.MUZZLE_Y, G.BORE_Z), False),
    ('slide_rb', (152.84, 237.1), (-HW, YS0, ZSB), False),
    ('slide_r45', None, (-HW, YS0, 45.0), False),
    ('rsight_tr', (200.0, 51.0), None, False),
    ('rsight_tf', (226.0, 51.0), None, False),
    ('fsight_tr', (1462.0, 68.0), None, False),
    ('fsight_tf', (1478.0, 68.0), None, False),
    ('port_rb', (723.0, 168.0), None, False),
    ('serr_r1', (257.5, 236.5), None, False),
    ('serr_f7', (1447.0, 245.5), None, False),
    ('beaver_tip', (76.0, 280.0), None, True),
    ('guard_bf', (1027.0, 571.0), None, True),
    ('grip_fb', (452.0, 1022.0), None, True),
    ('grip_rb', (52.0, 960.0), None, True),
    ('base_rb', (118.0, 1095.0), None, True),
    ('base_ft', (452.0, 1052.0), None, True),
])

# ---- 3/4 front right photo (Gen 6 render, same CAD family as the master): front + LEFT side visible
V['34fr'] = dict(ref='g5_34front_right.jpg', dir=[-0.55, 0.80, -0.20], f=120, frange=[20, 600], pts=[
    ('muzzle', (50.0, 127.0), (0.0, G.MUZZLE_Y, G.BORE_Z), False),
    ('guide_hole', (57.0, 263.0), (0.0, YS1, G.GUIDE_Z), False),
    ('nose_bot_L', (108.0, 240.0), (HW, G.NOSE_Y, ZSB), False),
    ('rsight_base_fl', (1203.0, 30.0), (7.2, -39.8, ZST), False),
    ('rsight_base_fr', (1077.0, 30.0), (-7.2, -39.8, ZST), False),
    ('fsight_base_fl', (100.0, 39.0), (1.75, 130.5, ZST), False),
    ('fsight_base_fr', (66.0, 39.0), (-1.75, 130.5, ZST), False),
    ('fsight_base_rl', (142.0, 39.0), (1.75, 124.55, ZST), False),
    ('slide_rt_L', (1235.0, 55.0), (HW, YS0, ZST - G.TOP_CHAMF), False),
    ('slide_rb_L', (1235.0, 191.0), (HW, YS0, ZSB), False),
    ('tang_tip', (1269.0, 219.0), (0.0, -61.98, 23.48), False),
    ('base_fl_top', (946.0, 979.0), (11.6, -10.6, -80.3), False),
    ('base_fl_bot', (945.0, 1014.0), (11.6, -12.0, -84.5), False),
    ('guard_fb', (497.0, 567.0), (6.0, 66.5, -13.2), True),
    ('grip_fb', (933.0, 951.0), (12.0, -10.0, -75.0), True),
])

# ---- 3/4 front left photo (real photo, airsoft Gen5 replica on white): front + LEFT side visible
V['34fl'] = dict(ref='g5_34front_left.jpg', dir=[-0.55, 0.80, -0.30], f=60, frange=[15, 800], pts=[
    ('muzzle', (110.0, 483.0), (0.0, G.MUZZLE_Y, G.BORE_Z), False),
    ('guide_hole', (128.0, 588.0), (0.0, YS1, G.GUIDE_Z), False),
    ('fsight_top', (160.0, 373.0), (0.0, 127.5, 53.3), False),
    ('nose_top_L', (200.0, 450.0), (HW, G.NOSE_Y, ZST - G.TOP_CHAMF), False),
    ('nose_bot_L', (200.0, 585.0), (HW, G.NOSE_Y, ZSB), False),
    ('slide_rt_L', (1194.0, 140.0), (HW, YS0, ZST - G.TOP_CHAMF), False),
    ('slide_rb_L', (1193.0, 247.0), (HW, YS0, ZSB), False),
])

# ---- top-rear photo (real photo, Gen5): camera behind-left-above; +x (gun left) appears on the image left
V['toprear'] = dict(ref='g5_top_rear.jpg', dir=[0.3, -0.6, -0.75], f=60, frange=[15, 800], pts=[
    ('fsight_dot', (232.0, 37.0), (0.0, 124.9, 51.9), False),
    ('rsight_U_L', (1020.0, 529.0), (2.45, -46.85, 50.75), False),
    ('rsight_U_R', (1053.0, 510.0), (-2.45, -46.85, 50.75), False),
    ('slide_rt_R', (1103.0, 505.0), (-HW, YS0, ZST - G.TOP_CHAMF), False),
    ('slide_rb_R', (1104.0, 638.0), (-HW, YS0, ZSB), False),
    ('nose_tl', (155.0, 62.0), (11.6, 134.5, ZST - 1.0), False),
    ('nose_bl', (158.0, 176.0), (12.2, 132.5, ZSB), True),
    ('magcatch_L', (671.0, 670.0), (16.6, 1.05, -1.14), False),
    ('slidestop_L', (709.0, 531.0), (14.9, -0.5, 27.7), False),
    ('base_rbl', (980.0, 1255.0), (11.5, -55.6, -87.0), True),
])

def build(view, blend_out, render_out, samples=48):
    c = V[view]; pts = []
    for name, px, g, chk in c['pts']:
        if px is None:                                      # pixel from the model point via the homography
            yz = np.array([[g[1], g[2], 1.0]]) @ np.array(G._T['Hinv']).T; px = tuple((yz[0, :2] / yz[0, 2]).tolist())
        if g is None: g = gpx(px, -HW if not name.startswith(('rsight', 'fsight', 'beaver', 'guard', 'grip', 'base')) else 0.0)
        pts.append(dict(name=name, px=[float(px[0]), float(px[1])], world=W(g), check=bool(chk)))
    J = dict(reference=os.path.join(REF, c['ref']), camera='REFCAM_' + view, points=pts,
             init=dict(focal_mm=c['f'], view_dir=c['dir']), fix_focal=False, focal_range=c.get('frange', [20, 400]),
             render=dict(out=render_out, engine='CYCLES', samples=samples, studio=True, transparent=True),
             save_blend=blend_out)
    p = os.path.join(HERE, 'work', 'match_%s_%s.json' % (view, PASS)); json.dump(J, open(p, 'w'), indent=1); return p
if __name__ == '__main__':
    for v in VIEWS:
        print(build(v, os.path.join(HERE, 'work', 'G17_V4_Cam_%s.blend' % v), os.path.join(HERE, 'review', 'match_%s_%s.png' % (v, PASS))))
