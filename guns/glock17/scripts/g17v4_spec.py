"""g17v4_spec.py - Glock 17 Gen5 v4 measurements in the G frame (mm; x gun-left, y muzzle, z up; contract frame origin).

Everything here is measured on the private reference photos (trace.py homography of g5_right_side.png, scaled to 202 mm
overall, crown on the contract muzzle y 137.4 / bore z 39.5), or is a real Glock 17 Gen 5 dimension.  Widths that the side
photo cannot give (x) are real dimensions, checked later against the 3/4 photos with matched cameras."""
import json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
_T = json.load(open(os.path.join(HERE, 'work', 'trace.json')))
H = np.array(_T['H'])

def px2g(pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ H.T; return p[:, :2] / p[:, 2:3]

# ---------------------------------------------------------------- slide (photo)
ZSB, ZST = _T['slide']['z_bot_rear'], _T['slide']['z_top_rear']      # 29.29 / 50.31
YS0, YS1 = _T['slide']['y0'], _T['slide']['y1']                       # -51.14 / 136.0
SLIDE_HW = 12.75                 # real: slide width 25.5
LOBE_HW = 12.75                  # front lobe around the guide rod: same width as the slide (3/4 photos), parting groove only
NOSE_Y = 128.5                   # nose side taper starts (photo: 8 mm lighter facet before the face)
NOSE_SLOPE = 0.27
TOP_CHAMF = 1.9                  # 45 deg top-edge chamfer (photo: 1.9 mm band)
BORE_Z, MUZZLE_Y = 39.5, 137.4
BARREL_R = 6.7                   # photo crown OD 13.4
def _grooves(cpx, wpx, v=200.0):
    """groove (start y, width) list from photo groove centre columns / width (px)"""
    out = []
    for c in cpx:
        a, b = px2g([(c - wpx / 2.0, v), (c + wpx / 2.0, v)]); out.append((float(a[0]), float(b[0] - a[0])))
    return out
REAR_SERR = _grooves([269.0 + 38.4 * i for i in range(6)], 24.0)          # photo: 6 grooves, 3.25 mm, pitch 5.2
FRONT_SERR = _grooves([1212.0 + 37.35 * i for i in range(7)], 22.0)       # photo: 7 grooves, 3.0 mm, pitch 5.06
SERR_TOP = 48.9                  # groove top (rounded end) - reaches into the chamfer
SERR_DEPTH = 1.1
_p = px2g([(723.0, 168.0), (937.0, 168.0)])
PORT_Y0, PORT_Y1 = float(_p[0, 0]), float(_p[1, 0])                    # ejection port (photo x 723..937)
PORT_ZB = float(_p[0, 1])                                               # port bottom edge on the right side
HOOD_HW = 8.6; HOOD_TOP = ZST - 0.5
BREECH_Y = PORT_Y0
GUIDE_Z = 24.3                   # recoil-spring guide rod axis (34fr photo: 15.2 mm under the bore)
GUIDE_HOLE_R = 3.2
SLIDE_IN_HW = 9.0                # slide inner walls
RAIL_GROOVE = (29.8, 31.8, 10.6)  # slide rail groove z0, z1, x depth

# ---------------------------------------------------------------- frame (photo profile; widths real)
GRIP_HW = 14.6                   # real grip ~29-30 mm wide
FLARE_HW = 15.7                  # magwell flare
RECV_HW = 13.6
DUST_HW = 12.2
GUARD_HW = 9.4
_P = np.load(os.path.join(HERE, 'work', 'prof.npz'))
def _edges(mask, z, which):
    r = int((float(_P['z1']) - z) / float(_P['res'])); c = np.nonzero(_P['m_' + mask][r] > 0)[0]
    ys = float(_P['y0']) + (c + 0.5) * float(_P['res'])
    if which == 'rear': return ys.min()
    run_end = c[np.nonzero(np.diff(c) > 1)[0][0]] if np.any(np.diff(c) > 1) else c.max()
    return float(_P['y0']) + (run_end + 0.5) * float(_P['res'])
_zz = np.arange(-62.0, -21.0, 1.0)
_kf = np.polyfit(_zz, [_edges('frame', z, 'front') for z in _zz], 1)
_kr = np.polyfit(_zz, [_edges('frame', z, 'rear') for z in _zz], 1)
GRIP_RAKE = float(_kf[0])                                                # front strap dy/dz (photo)
def front_strap(z): return _kf[0] * z + _kf[1]
def rear_line(z): return _kr[0] * z + _kr[1]
TOPCH_HW = 10.3                  # frame top channel (inside the slide)
FRAME_TOP = ZSB
DUSTCH_R = 5.4

# ---------------------------------------------------------------- magazine (photo: visible body at z -78.6 spans y -53.2 .. -16.0)
# visible magazine body between the frame bottom and the baseplate (profile rows z -79.6 .. -80.0: y -53.05 .. -15.0)
MAG_FRONT0 = (-15.0, -79.8); MAG_REAR0 = (-53.05, -79.8)
MAG_RAKE = GRIP_RAKE
MAG_HW = 11.0
MAG_TOP = 26.0
def mag_front(z): return MAG_FRONT0[0] + MAG_RAKE * (z - MAG_FRONT0[1])
def mag_rear(z): return MAG_REAR0[0] + MAG_RAKE * (z - MAG_REAR0[1])
BASE_HW = 12.6

# ---------------------------------------------------------------- hand-traced (photo px) features
SEAM_PX = [(331, 360), (330, 400), (328, 440), (322, 465), (311, 485), (306, 500), (301, 515), (297, 530), (292, 545),
           (284, 560), (279, 575), (273, 590), (269, 605), (263, 620), (256, 635), (247, 650), (240, 665), (229, 680),
           (220, 695), (210, 710), (202, 725), (194, 740), (185, 755), (176, 770), (167, 785), (159, 800), (150, 815),
           (142, 830), (134, 845), (127, 860), (121, 875), (116, 890), (110, 905), (101, 925), (93, 941)]
SEAM = px2g(SEAM_PX)
BS_TOP_Z = float(SEAM[0, 1]); BS_BOT = SEAM[-1]
BS_THICK = 3.0
