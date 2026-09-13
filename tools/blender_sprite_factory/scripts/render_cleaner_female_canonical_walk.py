import bpy
import os
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FBX = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'cleaner_female_canonical_walk.blend')
OUT_ROOT = os.path.join(ROOT, 'output', 'cleaner_female_canonical_walk')

# These are deliberately identical to CANONICAL_WALK.  This script changes
# only materials and small bone-attached visual accessories.
FRAMES = [25, 1, 9, 17]
DIRECTIONS = [('se', 0.0), ('sw', 90.0), ('nw', 180.0), ('ne', 270.0)]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def make_material(name, color):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    principled = material.node_tree.nodes.get('Principled BSDF')
    principled.inputs['Base Color'].default_value = (*color, 1.0)
    principled.inputs['Roughness'].default_value = 0.78
    material.diffuse_color = (*color, 1.0)
    return material


def add_uv_sphere(name, material, location, scale):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def attach_to_bone(obj, armature, bone_name):
    # Preserve the rest-pose world transform, then make the detail inherit
    # exactly the motion of the original Mixamo bone. No animation data is
    # edited and the character source FBX remains untouched.
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = 'BONE'
    obj.parent_bone = bone_name
    obj.matrix_parent_inverse = (armature.matrix_world @ armature.pose.bones[bone_name].matrix).inverted()
    obj.matrix_world = world


def compose_sheet(folder, direction):
    sheet = bpy.data.images.new('walk_' + direction, width=1024, height=256, alpha=True)
    pixels = [0.0] * (1024 * 256 * 4)
    for index in range(4):
        image = bpy.data.images.load(os.path.join(folder, 'frame_{:02d}.png'.format(index)), check_existing=False)
        source = list(image.pixels)
        for y in range(256):
            pixels[(y * 1024 + index * 256) * 4:(y * 1024 + (index + 1) * 256) * 4] = source[y * 256 * 4:(y + 1) * 256 * 4]
        bpy.data.images.remove(image)
    sheet.pixels = pixels
    sheet.filepath_raw = os.path.join(folder, 'walk_{}.png'.format(direction))
    sheet.file_format = 'PNG'
    sheet.save()
    bpy.data.images.remove(sheet)


# Fresh tool-only scene, importing the supplied FBX read-only.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
bpy.ops.import_scene.fbx(filepath=FBX, use_anim=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.render.fps = 30
scene.eevee.taa_render_samples = 32
scene.world.color = (0.05, 0.05, 0.05)

armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
action = armature.animation_data.action

# Preserve natural bob/weight transfer but remove only the forward root drift.
hips_path = 'pose.bones["mixamorig:Hips"].location'
forward = next(curve for curve in action.fcurves if curve.data_path == hips_path and curve.array_index == 2)
first = forward.keyframe_points[0]
last = forward.keyframe_points[-1]
span = last.co.x - first.co.x
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0.0 else (point.co.x - first.co.x) / span
    drift = first.co.y + (last.co.y - first.co.y) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()

# Palette derived from the approved janitor reference: deep teal workwear,
# lime safety bands, charcoal gloves/boots and a brown tied hairstyle.
# These strong color blocks survive the 32 px runtime reduction.
uniform = make_material('Cleaner_Female_Uniform_Teal', (0.025, 0.31, 0.27))
uniform_dark = make_material('Cleaner_Female_WorkBoots', (0.018, 0.026, 0.04))
vest = make_material('Cleaner_Female_Safety_Lime', (0.46, 0.82, 0.16))
hair = make_material('Cleaner_Female_Hair', (0.075, 0.026, 0.018))

for material in bpy.data.materials:
    if material.name.startswith('Beta_HighLimbs'):
        material.use_nodes = True
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*uniform.diffuse_color[:3], 1.0)
        material.diffuse_color = uniform.diffuse_color
    elif material.name.startswith('Beta_Joints'):
        material.use_nodes = True
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*uniform_dark.diffuse_color[:3], 1.0)
        material.diffuse_color = uniform_dark.diffuse_color

scene.frame_set(1)
# Hair cap + compact bun: modest silhouette change, deliberately simple.
hair_cap = add_uv_sphere('CleanerFemale_HairCap', hair, (-0.008, -0.075, 1.735), (0.155, 0.155, 0.135))
attach_to_bone(hair_cap, armature, 'mixamorig:Head')
hair_bun = add_uv_sphere('CleanerFemale_HairBun', hair, (-0.008, 0.052, 1.705), (0.105, 0.09, 0.10))
attach_to_bone(hair_bun, armature, 'mixamorig:Head')

# One soft torso shell and a slim reflective belt are attached to spine/hips;
# this avoids painting or modifying the source mesh while preserving motion.
vest_shell = add_uv_sphere('CleanerFemale_SafetyVest', vest, (0.0, -0.025, 1.365), (0.225, 0.14, 0.275))
attach_to_bone(vest_shell, armature, 'mixamorig:Spine2')
belt = add_uv_sphere('CleanerFemale_UtilityBelt', uniform_dark, (0.0, -0.02, 1.12), (0.19, 0.12, 0.045))
attach_to_bone(belt, armature, 'mixamorig:Hips')

# Minimal PPE details: they are intentionally geometric rather than fine mesh
# so the silhouette stays legible at city-map scale.
for name, location, bone in (
    ('CleanerFemale_LeftGlove', (0.264, -0.023, 0.858), 'mixamorig:LeftHand'),
    ('CleanerFemale_RightGlove', (-0.258, -0.121, 0.874), 'mixamorig:RightHand'),
):
    glove = add_uv_sphere(name, uniform_dark, location, (0.055, 0.045, 0.055))
    attach_to_bone(glove, armature, bone)

for name, location, bone in (
    ('CleanerFemale_LeftCalfBand', (0.125, -0.19, 0.56), 'mixamorig:LeftLeg'),
    ('CleanerFemale_RightCalfBand', (-0.067, -0.092, 0.523), 'mixamorig:RightLeg'),
):
    band = add_uv_sphere(name, vest, location, (0.095, 0.075, 0.04))
    attach_to_bone(band, armature, bone)

tile_mesh = bpy.data.meshes.new('CityHorizonTile128x64')
tile_mesh.from_pydata([(0, -0.64, 0), (1.28, 0, 0), (0, 0.64, 0), (-1.28, 0, 0)], [], [[0, 1, 2, 3]])
tile = bpy.data.objects.new('Calibration_Tile_128x64', tile_mesh)
scene.collection.objects.link(tile)
tile.hide_render = True

bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = 'Camera_CanonicalWalk_Orthographic_Locked'
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.65
target = Vector((0.0, 0.0, 0.88))
camera.location = target + Vector((6.0, -6.0, 6.0))
look_at(camera, target)
scene.camera = camera

bpy.ops.object.light_add(type='AREA', location=(4, -4, 7))
key = bpy.context.object
key.name = 'Key_Light_Soft'
key.data.energy = 350
key.data.size = 5.0
look_at(key, (0, 0, 0.8))
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.name = 'Fill_Light_Soft'
fill.data.energy = 80
fill.data.size = 4.0
look_at(fill, (0, 0, 0.8))

base_matrix = armature.matrix_world.copy()
for direction, degrees in DIRECTIONS:
    armature.matrix_world = Matrix.Rotation(degrees * 3.141592653589793 / 180.0, 4, 'Z') @ base_matrix
    folder = os.path.join(OUT_ROOT, direction)
    os.makedirs(folder, exist_ok=True)
    for index, frame in enumerate(FRAMES):
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(folder, 'frame_{:02d}.png'.format(index))
        bpy.ops.render.render(write_still=True)
    compose_sheet(folder, direction)

scene.frame_start = 1
scene.frame_end = 32
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CLEANER_FEMALE_CANONICAL_WALK_RENDERED directions={} frames={}'.format([item[0] for item in DIRECTIONS], FRAMES))
