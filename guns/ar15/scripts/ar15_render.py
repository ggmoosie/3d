"""ar15_render.py - studio renders of the AR-15 kit (EEVEE previews, Cycles for the finals), orthographic reference
renders for the photo overlays, and 2-D label anchors for the exploded / socket sheets (labels are drawn by ar15_post.py)."""
import bpy, bmesh, math, os, json
import numpy as np
from mathutils import Vector as V, Matrix
from bpy_extras.object_utils import world_to_camera_view
import ar15_lib as L

R = {}

# ------------------------------------------------------------------------------------------------ look-dev materials
LOOK = {   # Principled settings per slot (the FBX only carries the slot names; this is the preview look)
    #           base (linear)            metal  rough  spec  wear colour (bare metal at worn edges)   wear metal
    'Receiver':  dict(base=(0.014, 0.0148, 0.017), metal=0.0, rough=0.44, spec=0.50, wear=(0.26, 0.26, 0.27), wmetal=1.0, wrough=0.30),
    'Handguard': dict(base=(0.016, 0.0168, 0.019), metal=0.0, rough=0.46, spec=0.50, wear=(0.26, 0.26, 0.27), wmetal=1.0, wrough=0.30),
    'Steel':     dict(base=(0.022, 0.023, 0.020), metal=0.35, rough=0.52, spec=0.5, wear=(0.20, 0.20, 0.19), wmetal=1.0, wrough=0.34),
    'BCG':       dict(base=(0.055, 0.055, 0.052), metal=0.90, rough=0.27, spec=0.5, wear=(0.55, 0.55, 0.53), wmetal=1.0, wrough=0.18),
    'Polymer':   dict(base=(0.012, 0.012, 0.012), metal=0.0, rough=0.62, spec=0.4, wear=(0.035, 0.035, 0.035), wmetal=0.0, wrough=0.5),
    'Brass':     dict(base=(0.72, 0.50, 0.19), metal=1.0, rough=0.30, spec=0.5, wear=(0.86, 0.66, 0.30), wmetal=1.0, wrough=0.18),
}

def look_materials(masks=None):
    """(re)build the node trees of the five slot materials.  masks = {slot: dict(ao=path, curv=path, normal=path)} adds the
    baked AO (multiplies the base, dims the specular), curvature edge wear (thin bare-metal edges, lighter polymer edges),
    a subtle macro roughness break-up and the baked normal map (markings, grip texture)"""
    for slot, k in LOOK.items():
        m = L.slot_mat(slot); nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
        b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.location = (600, 0)
        nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
        b.inputs['Base Color'].default_value = (*k['base'], 1.0); b.inputs['Metallic'].default_value = k['metal']
        b.inputs['Roughness'].default_value = k['rough']
        try: b.inputs['Specular IOR Level'].default_value = k['spec']
        except KeyError: pass
        # macro roughness break-up (object-space noise) so flat faces do not read as CG-perfect
        tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1200, -400)
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.location = (-1000, -400); nz.inputs['Scale'].default_value = 90.0; nz.inputs['Detail'].default_value = 6.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        rr = nt.nodes.new('ShaderNodeMapRange'); rr.location = (-800, -400)
        rr.inputs['To Min'].default_value = k['rough'] * 0.85; rr.inputs['To Max'].default_value = k['rough'] * 1.18
        nt.links.new(nz.outputs['Fac'], rr.inputs['Value'])
        rough = rr.outputs['Result']; metal = None; col = None
        mk = (masks or {}).get(slot)
        if mk:
            uv = nt.nodes.new('ShaderNodeUVMap'); uv.location = (-1200, 0); uv.uv_map = 'UVMap'
            def tex(path, y):
                t = nt.nodes.new('ShaderNodeTexImage'); t.location = (-1000, y)
                t.image = bpy.data.images.load(path, check_existing=True); t.image.colorspace_settings.name = 'Non-Color'
                nt.links.new(uv.outputs['UV'], t.inputs['Vector']); return t
            base = nt.nodes.new('ShaderNodeRGB'); base.location = (-600, 300); base.outputs[0].default_value = (*k['base'], 1.0)
            col = base.outputs[0]
            if mk.get('curv'):
                cv = tex(mk['curv'], 200)
                # thin convex edges only: smoothstep(0.60, 0.80, curvature)
                sm = nt.nodes.new('ShaderNodeMapRange'); sm.location = (-700, 200); sm.interpolation_type = 'SMOOTHSTEP'
                sm.inputs['From Min'].default_value = 0.68; sm.inputs['From Max'].default_value = 0.92
                nt.links.new(cv.outputs['Color'], sm.inputs['Value'])
                wear = sm.outputs['Result']
                mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.location = (-300, 300)
                mix.inputs['B'].default_value = (*k['wear'], 1.0)
                nt.links.new(wear, mix.inputs['Factor']); nt.links.new(col, mix.inputs['A']); col = mix.outputs['Result']
                mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-300, 100)
                mr.inputs['To Min'].default_value = k['metal']; mr.inputs['To Max'].default_value = k['wmetal']
                nt.links.new(wear, mr.inputs['Value']); metal = mr.outputs['Result']
                r2 = nt.nodes.new('ShaderNodeMix'); r2.data_type = 'FLOAT'; r2.location = (-300, -400)
                nt.links.new(wear, r2.inputs['Factor']); nt.links.new(rough, r2.inputs[2]); r2.inputs[3].default_value = k['wrough']
                rough = r2.outputs[0]
            if mk.get('ao'):
                ao = tex(mk['ao'], -100)
                gm = nt.nodes.new('ShaderNodeMath'); gm.operation = 'POWER'; gm.inputs[1].default_value = 1.4; gm.location = (-700, -100)
                nt.links.new(ao.outputs['Color'], gm.inputs[0])
                mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.location = (0, 300)
                mx.inputs['Factor'].default_value = 1.0
                nt.links.new(col, mx.inputs['A']); nt.links.new(gm.outputs[0], mx.inputs['B']); col = mx.outputs['Result']
                so = nt.nodes.new('ShaderNodeMath'); so.operation = 'MULTIPLY'; so.location = (300, -200)
                nt.links.new(gm.outputs[0], so.inputs[0]); so.inputs[1].default_value = k['spec']
                try: nt.links.new(so.outputs[0], b.inputs['Specular IOR Level'])
                except KeyError: pass
            nt.links.new(col, b.inputs['Base Color'])
            if metal is not None: nt.links.new(metal, b.inputs['Metallic'])
            if mk.get('normal'):
                nm = tex(mk['normal'], -600)
                nmap = nt.nodes.new('ShaderNodeNormalMap'); nmap.location = (300, -600); nmap.uv_map = 'UVMap'
                nt.links.new(nm.outputs['Color'], nmap.inputs['Color']); nt.links.new(nmap.outputs['Normal'], b.inputs['Normal'])
        nt.links.new(rough, b.inputs['Roughness'])

def aux_mat(name, rgb, emit=None, rough=0.5):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1.0); b.inputs['Roughness'].default_value = rough
    if emit is not None:
        b.inputs['Emission Color'].default_value = (*emit, 1.0); b.inputs['Emission Strength'].default_value = 1.0
    return m

def flat_mat():
    """unlit silhouette material for the overlay renders: a light grey that darkens toward grazing angles"""
    m = bpy.data.materials.get('_Flat')
    if m: return m
    m = bpy.data.materials.new('_Flat'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); lw = nt.nodes.new('ShaderNodeLayerWeight')
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.35
    lw.inputs['Blend'].default_value = 0.45
    nt.links.new(lw.outputs['Facing'], mr.inputs['Value']); nt.links.new(mr.outputs['Result'], em.inputs['Strength'])
    em.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
    nt.links.new(em.outputs['Emission'], out.inputs['Surface']); return m

# ------------------------------------------------------------------------------------------------ studio
def studio(engine='EEVEE', res=(1600, 900), samples=64, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE' if engine == 'EEVEE' else 'CYCLES'
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    sc.render.film_transparent = transparent
    try:
        sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        sc.view_settings.view_transform = 'Filmic'
    sc.view_settings.exposure = 0.0
    if engine == 'EEVEE':
        e = sc.eevee; e.taa_render_samples = samples; e.use_gtao = True; e.gtao_distance = 0.03; e.gtao_factor = 1.0
        e.use_ssr = True; e.use_ssr_halfres = False; e.ssr_thickness = 0.01; e.use_soft_shadows = True
        e.shadow_cube_size = '2048'; e.shadow_cascade_size = '4096'; e.use_shadow_high_bitdepth = True
        e.use_bloom = False
    else:
        c = sc.cycles; c.samples = samples; c.use_denoising = True; c.device = 'GPU' if enable_gpu() else 'CPU'
        c.max_bounces = 6
    w = bpy.data.worlds.get('_World') or bpy.data.worlds.new('_World'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (0.012, 0.013, 0.015, 1.0); bg.inputs['Strength'].default_value = 1.0
    if 'cam' not in R:
        cam = bpy.data.cameras.new('_Cam'); co = bpy.data.objects.new('_Cam', cam); sc.collection.objects.link(co); sc.camera = co
        R['cam'] = co
    return sc

def enable_gpu():
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for t in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = t; prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == t]
                if devs:
                    for d in prefs.devices: d.use = (d.type == t)
                    return True
            except TypeError: continue
    except Exception: pass
    return False

def clear_rig():
    for o in list(bpy.data.objects):
        if o.name.startswith('_L_') or o.name.startswith('_BG'): L.kill(o) if o.type == 'MESH' else bpy.data.objects.remove(o, do_unlink=True)

def area_light(name, loc, target, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size; ld.color = color; ld.shape = 'DISK'
    try: ld.use_contact_shadow = True; ld.contact_shadow_distance = 0.02
    except AttributeError: pass
    o = bpy.data.objects.new(name, ld); bpy.context.scene.collection.objects.link(o); L.look_at(o, target, loc); return o

def area_rect(name, loc, target, energy, sx, sy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.shape = 'RECTANGLE'; ld.size = sx; ld.size_y = sy; ld.color = color
    try: ld.use_contact_shadow = True; ld.contact_shadow_distance = 0.02
    except AttributeError: pass
    o = bpy.data.objects.new(name, ld); bpy.context.scene.collection.objects.link(o); L.look_at(o, target, loc); return o

def soft_light(name, loc, target, radiance, sx, sy, color=(1, 1, 1)):
    """rectangular area light defined by its radiance (W per m2 of emitter) instead of its power: what a glossy surface
    mirrors is the emitter's radiance, so keeping every light within ~1.5x of the key's radiance is what stops a small hot
    strip from clipping to a white band on faces that sit near edge-on to the camera (pass-2 finding, see AR15_BUILD.md)"""
    return area_rect(name, loc, target, radiance * sx * sy, sx, sy, color)

KEY_RADIANCE = 30.0          # W/m2 of emitter at the reference rig distance (1.17 m); all lights are set relative to it

def light_rig(cam_dir, center, radius, mood='studio'):
    """product-shot rig relative to the camera: a long softbox above (reflects along the top surfaces), a soft rim behind,
    a kicker from the far side and a dim fill from the camera.  Emitter sizes scale with the rig distance (constant angular
    size) and every light is specified by radiance, capped at 1.5x the key, so no emitter mirrors as a clipped white strip.
    `mood='moody'` drops the fill and narrows the key."""
    clear_rig(); c = V(center); d = V(cam_dir).normalized(); up = V((0, 0, 1))
    side = d.cross(up).normalized() if abs(d.dot(up)) < 0.98 else V((1, 0, 0))
    dist = max(1.0, radius * 2.6); s = dist / 1.17; K = KEY_RADIANCE
    if mood == 'moody':
        soft_light('_L_key', c + (up * 0.9 + d * 0.35 - side * 0.5).normalized() * dist, c, K * 1.2, 0.8 * s, 0.45 * s, (1.0, 0.94, 0.86))
        soft_light('_L_rim', c + (-d * 0.85 + up * 0.45 + side * 0.25).normalized() * dist, c, K * 1.5, 0.45 * s, 2.0 * s, (0.78, 0.86, 1.0))
        soft_light('_L_kick', c + (-d * 0.4 - side * 0.9 + up * 0.1).normalized() * dist, c, K * 1.0, 0.35 * s, 1.4 * s, (1.0, 0.9, 0.8))
    else:
        soft_light('_L_key', c + (up * 1.0 + d * 0.30 - side * 0.25).normalized() * dist, c, K, 1.8 * s, 0.7 * s, (1.0, 0.97, 0.93))
        soft_light('_L_rim', c + (-d * 0.9 + up * 0.5 + side * 0.15).normalized() * dist, c, K * 1.5, 0.55 * s, 2.2 * s, (0.92, 0.95, 1.0))
        soft_light('_L_kick', c + (-d * 0.3 + side * 0.95 - up * 0.05).normalized() * dist, c, K * 0.45, 0.45 * s, 1.6 * s, (1, 1, 1))
        soft_light('_L_fill', c + (d * 1.0 + up * 0.35 - side * 0.55).normalized() * dist * 1.3, c, K * 0.12, 2.4 * s, 1.6 * s, (0.9, 0.94, 1.0))

def backdrop(cam_loc, center, radius, tone=(0.060, 0.062, 0.068), edge=(0.008, 0.0085, 0.010)):
    """radial-gradient emissive card behind the subject, facing the camera (studio sweep look, no hard horizon)"""
    c = V(center); d = (V(cam_loc) - c).normalized()
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=radius * 6.0)
    me = bpy.data.meshes.new('_BG'); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new('_BG', me); bpy.context.scene.collection.objects.link(o)
    o.location = c - d * (radius * 1.6); o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    m = bpy.data.materials.get('_BGMat') or bpy.data.materials.new('_BGMat'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission')
    tc = nt.nodes.new('ShaderNodeTexCoord'); gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0 / (radius * 2.6),) * 3
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*edge, 1.0); ramp.color_ramp.elements[1].color = (*tone, 1.0)
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[1].position = 0.85
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], gr.inputs['Vector'])
    nt.links.new(gr.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    o.data.materials.append(m); o.visible_shadow = False
    try: o.visible_diffuse = False; o.visible_glossy = True
    except AttributeError: pass
    return o

VIEWS = {   # direction from the subject toward the camera, Blender scene (true-handed: gun's left = +X, muzzle = -Y)
    'left':    (1.0, 0.0, 0.0),
    'right':   (-1.0, 0.0, 0.0),
    'front34': (-0.62, -0.62, 0.36),   # right-front-high (ejection port side)
    'rear34':  (0.66, 0.55, 0.34),     # left-rear-high (selector / bolt catch side)
    'front':   (-0.10, -1.0, 0.12),
    'top':     (0.0, 0.001, 1.0),
    'left34':  (0.65, -0.60, 0.30),
    'below34': (-0.55, -0.45, -0.55),
}

def frame(objs, view, res, margin=1.0, lens=85.0, ortho=False, target=None, fill=0.94):
    """place the camera for `view` so that the objects fill the frame"""
    sc = bpy.context.scene; cam = R['cam']; cd = cam.data
    lo, hi = L.world_bounds(objs); c = V(((lo + hi) * 0.5).tolist()) if target is None else V(target)
    d = V(VIEWS[view] if isinstance(view, str) else view).normalized()
    up = V((0, 0, 1)) if abs(d.z) < 0.95 else V((0, 1, 0))
    rot = (-d).to_track_quat('-Z', 'Y').to_matrix() if abs(d.z) < 0.95 else Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    if abs(d.z) >= 0.95: rot = (-d).to_track_quat('-Z', 'X').to_matrix()
    xa, ya = rot.col[0], rot.col[1]
    aspect = res[0] / res[1]
    corners = [V((x, y, z)) - c for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    if ortho:
        cd.type = 'ORTHO'
        w = max(abs(p.dot(xa)) for p in corners) * 2; h = max(abs(p.dot(ya)) for p in corners) * 2
        cd.ortho_scale = max(w, h * aspect) * margin
        cam.location = c + d * 5.0
    else:
        cd.type = 'PERSP'; cd.lens = lens; cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0
        tx = (cd.sensor_width / 2) / lens; ty = tx / aspect
        need = 0.0
        for p in corners:
            depth = p.dot(d)
            need = max(need, abs(p.dot(xa)) / (tx * fill) + depth, abs(p.dot(ya)) / (ty * fill) + depth)
        cam.location = c + d * need * margin
    cam.rotation_euler = rot.to_euler()
    cd.clip_start = 0.005; cd.clip_end = 100.0
    return c, d

def render(path, res=None):
    sc = bpy.context.scene
    if res: sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    return path

def project(points_world):
    """Blender world points -> pixel coordinates (x right, y down) of the current camera"""
    sc = bpy.context.scene; cam = R['cam']; W, H = sc.render.resolution_x, sc.render.resolution_y; out = []
    for p in points_world:
        q = world_to_camera_view(sc, cam, V(p)); out.append((q.x * W, (1.0 - q.y) * H, q.z))
    return out

def ortho_side(objs, side, mm_per_px, center_g, size_px, path, transparent=True):
    """orthographic side render at a known scale for the photo overlays.  center_g = G (Y, Z) mm at the image centre."""
    sc = bpy.context.scene; cam = R['cam']; cd = cam.data; cd.type = 'ORTHO'
    W, H = size_px; cd.ortho_scale = W * mm_per_px * L.MM; cd.sensor_fit = 'HORIZONTAL'
    c = L.g2b((0.0, center_g[0], center_g[1]))
    d = V((1, 0, 0)) if side == 'left' else V((-1, 0, 0))
    cam.location = c + d * 3.0; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cd.clip_start = 0.01; cd.clip_end = 10.0
    sc.render.film_transparent = transparent; sc.render.image_settings.color_mode = 'RGBA'
    # (view-layer material_override renders black in headless EEVEE 4.0, so the flat material is assigned per slot)
    flat = flat_mat(); saved = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.name.startswith('_'):
            for s in o.material_slots: saved.append((s, s.material)); s.material = flat
    render(path, (W, H))
    for s, m in saved: s.material = m
    sc.render.film_transparent = False; sc.render.image_settings.color_mode = 'RGB'
    return dict(path=path, side=side, mm_per_px=mm_per_px, center_g=list(center_g), size=[W, H])
