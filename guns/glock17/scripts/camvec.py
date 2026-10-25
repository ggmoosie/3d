"""camvec.py - print / store the REFCAM_<view> of a blend as the camera_match vector (rodrigues rx ry rz, tx ty tz, focal).
usage: blender -b work/G17_V4_Cam_<view>.blend --python camvec.py -- <view> <json to update>"""
import bpy, sys, json, math
import numpy as np
v, jp = sys.argv[sys.argv.index('--') + 1:][:2]
c = bpy.data.objects['REFCAM_' + v]; M = np.array(c.matrix_world); R = M[:3, :3]
ang = math.acos(max(-1, min(1, (np.trace(R) - 1) / 2)))
w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
r = w / np.linalg.norm(w) * ang if np.linalg.norm(w) > 1e-9 else np.zeros(3)
x = list(r) + list(M[:3, 3]) + [c.data.lens]
J = json.load(open(jp)); J['x0'] = x; json.dump(J, open(jp, 'w'), indent=1); print('CAMVEC', x)
