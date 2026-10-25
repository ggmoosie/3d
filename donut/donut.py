import bpy, bmesh, random, math, sys, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def mat(name, color, rough=0.5, sss=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Coat Weight"].default_value = coat
    return m

# --- dough ---
bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.45, major_segments=96, minor_segments=48)
dough = bpy.context.object
dough.name = "Dough"
dough.scale.z = 0.85
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
# lumpy, hand-made look
tex = bpy.data.textures.new("lumps", "CLOUDS"); tex.noise_scale = 0.4
d = dough.modifiers.new("Displace", "DISPLACE"); d.texture = tex; d.strength = 0.07
dough.data.materials.append(mat("Dough", (0.38, 0.15, 0.03), rough=0.55, sss=0.15))

# --- icing: top half of the dough, thickened, with drips ---
icing = dough.copy(); icing.data = dough.data.copy(); icing.name = "Icing"
icing.modifiers.clear()
bm = bmesh.new(); bm.from_mesh(icing.data)
cut = [v for v in bm.verts if v.co.z < 0.02 + 0.08 * math.sin(math.atan2(v.co.y, v.co.x) * 7)]
bmesh.ops.delete(bm, geom=cut, context="VERTS")
bm.to_mesh(icing.data); bm.free()
icing.data.materials.clear()
icing.data.materials.append(mat("Icing", (0.9, 0.15, 0.4), rough=0.2, sss=0.2, coat=0.6))
s = icing.modifiers.new("Solidify", "SOLIDIFY"); s.thickness = 0.04; s.offset = 1
icing.modifiers.new("Subsurf", "SUBSURF").levels = 2
icing.location.z += 0.01
scene.collection.objects.link(icing)

# --- sprinkles: scattered on upward-facing icing faces ---
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.012, depth=0.07)
proto = bpy.context.object
bpy.ops.object.shade_smooth()
colors = [(1, 1, 1), (0.1, 0.4, 1), (1, 0.85, 0.1), (0.2, 0.8, 0.3), (1, 0.1, 0.1)]
smats = [mat(f"Sprinkle{i}", c, rough=0.35) for i, c in enumerate(colors)]
faces = [p for p in icing.data.polygons if p.normal.z > 0.5]
for _ in range(220):
    f = random.choice(faces)
    sp = proto.copy(); sp.data = proto.data.copy()
    sp.data.materials.append(random.choice(smats))
    sp.location = f.center + f.normal * 0.045 + Vector((0, 0, 0.01))
    sp.rotation_euler = (math.pi / 2, 0, random.uniform(0, math.pi * 2))
    scene.collection.objects.link(sp)
bpy.data.objects.remove(proto)

# --- plate + world ---
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=2.2, depth=0.08, location=(0, 0, -0.42))
plate = bpy.context.object
plate.modifiers.new("Bevel", "BEVEL").width = 0.03
bpy.ops.object.shade_smooth()
plate.data.materials.append(mat("Plate", (0.9, 0.92, 0.95), rough=0.15, coat=1))
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.46))
bpy.context.object.data.materials.append(mat("Table", (0.25, 0.18, 0.12), rough=0.7))

world = bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.85, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3

# --- lights ---
bpy.ops.object.light_add(type="AREA", location=(3, -3, 5))
key = bpy.context.object; key.data.energy = 550; key.data.size = 3
key.rotation_euler = (math.radians(40), 0, math.radians(45))
bpy.ops.object.light_add(type="AREA", location=(-4, 2, 3))
fill = bpy.context.object; fill.data.energy = 250; fill.data.size = 4
fill.rotation_euler = (math.radians(55), 0, math.radians(-120))

# --- camera ---
bpy.ops.object.camera_add(location=(0, -4.2, 3.4))
cam = bpy.context.object; scene.camera = cam
cam.data.lens = 50
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 5.2; cam.data.dof.aperture_fstop = 2.8
c = cam.constraints.new("TRACK_TO"); c.target = dough

# --- render ---
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 64
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = 1080
scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.filepath = os.path.join(HERE, "donut.png")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "donut.blend"))
bpy.ops.render.render(write_still=True)
print("DONE")
