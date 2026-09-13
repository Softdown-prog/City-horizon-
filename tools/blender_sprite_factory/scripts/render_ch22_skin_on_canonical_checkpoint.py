import bpy
import os
from math import pi
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CH22 = os.path.join(ROOT, 'input', 'candidate_ch22_nonpbr.fbx')
CANONICAL = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'worker_cleaner_female_3d_static_v3.blend')
OUT_DIR = os.path.join(ROOT, 'output', 'worker_cleaner_female_3d_static_v3')
FRAMES = [25, 1, 9, 17]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def armatures(scene):
    return [obj for obj in scene.objects if obj.type == 'ARMATURE']


def solid_material(name, rgb, roughness=0.58):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    bsdf = result.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    return result


def soft_box(name, location, scale, material, armature, bone):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    item = bpy.context.object
    item.name = name
    item.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = item.modifiers.new('SoftEdges', 'BEVEL')
    bevel.width = 0.015
    bevel.segments = 2
    bpy.context.view_layer.objects.active = item
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    item.data.materials.append(material)
    world = item.matrix_world.copy()
    item.parent = armature
    item.parent_type = 'BONE'
    item.parent_bone = bone
    item.matrix_parent_inverse = (armature.matrix_world @ armature.pose.bones[bone].matrix).inverted()
    item.matrix_world = world
    return item


def soft_sphere(name, location, scale, material, armature, bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=location)
    item = bpy.context.object
    item.name = name
    item.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    item.data.materials.append(material)
    world = item.matrix_world.copy()
    item.parent = armature
    item.parent_type = 'BONE'
    item.parent_bone = bone
    item.matrix_parent_inverse = (armature.matrix_world @ armature.pose.bones[bone].matrix).inverted()
    item.matrix_world = world
    return item


# Import the dressed visual donor first. Its armature and Action are temporary
# extraction data only; neither belongs to the production scene.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=CH22, use_anim=True)
scene = bpy.context.scene
donor_armature = armatures(scene)[0]
donor_meshes = [obj for obj in scene.objects if obj.type == 'MESH' and obj.name != 'Cube']

# Import the proven animated base. This is the sole animation owner.
bpy.ops.import_scene.fbx(filepath=CANONICAL, use_anim=True)
canonical_armature = next(obj for obj in armatures(scene) if obj != donor_armature)
canonical_armature.name = 'CanonicalWalk_AnimationArmature'
# Both FBXs arrive with the generic Mixamo action name. The dressed donor has
# a static 1–2 frame Action; select the actual 32-frame canonical walk rather
# than relying on Blender's import-name collision suffix.
canonical_action = max(bpy.data.actions, key=lambda action: action.frame_range[1] - action.frame_range[0])
canonical_armature.animation_data.action = canonical_action
canonical_action.name = 'CANONICAL_WALK_SOURCE_25_1_9_17'

# Keep only the dressed Ch22 meshes visible; Beta remains only as the
# animation skeleton. Both FBXs use the 65-bone Mixamo name contract, so the
# donor's existing vertex groups bind directly to the canonical armature.
for obj in scene.objects:
    if obj.type == 'MESH' and obj not in donor_meshes:
        obj.hide_render = True
donor_armature.hide_render = True

for mesh in donor_meshes:
    world = mesh.matrix_world.copy()
    mesh.parent = canonical_armature
    mesh.matrix_parent_inverse = canonical_armature.matrix_world.inverted()
    mesh.matrix_world = world
    armature_modifiers = [mod for mod in mesh.modifiers if mod.type == 'ARMATURE']
    if not armature_modifiers:
        modifier = mesh.modifiers.new('CanonicalWalk_Armature', 'ARMATURE')
        modifier.object = canonical_armature
    else:
        for modifier in armature_modifiers:
            modifier.object = canonical_armature
    # Ch22 is Mixamo-compatible but uses the exporter variant `mixamorig2:`.
    # Repoint its existing skin weights at the canonical `mixamorig:` bones;
    # topology and weights themselves are not recalculated or altered.
    for group in mesh.vertex_groups:
        canonical_name = group.name.replace('mixamorig2:', 'mixamorig:', 1)
        if canonical_name in canonical_armature.pose.bones:
            group.name = canonical_name

# The donor rig/action are deliberately discarded after skin binding. The
# saved scene therefore contains exactly one production armature: CANONICAL_RIG.
bpy.data.objects.remove(donor_armature, do_unlink=True)
canonical_armature.name = 'CANONICAL_RIG'
if len(armatures(scene)) != 1:
    raise RuntimeError('Production skin scene must contain exactly one armature')
for mesh in donor_meshes:
    unresolved = [group.name for group in mesh.vertex_groups if group.name.startswith('mixamorig2:')]
    if unresolved:
        raise RuntimeError('Unmapped donor weights on {}: {}'.format(mesh.name, unresolved[:3]))

# Keep Ch22's continuous, production-quality human mesh. Only its material
# treatment is changed into the City Horizon sanitation uniform; this avoids
# the primitive-body look while preserving the single canonical skeleton.
skin = solid_material('CH22_Style_Skin', (0.74, 0.39, 0.23))
hair = solid_material('CH22_Style_Hair', (0.10, 0.028, 0.010), 0.70)
lime = solid_material('CH22_Style_SafetyLime', (0.52, 0.90, 0.12))
teal = solid_material('CH22_Style_WorkwearTeal', (0.015, 0.36, 0.34))
dark = solid_material('CH22_Style_BootsGloves', (0.028, 0.038, 0.055), 0.68)
reflective = solid_material('CH22_Style_Reflective', (0.78, 0.84, 0.86), 0.36)
for mesh in donor_meshes:
    if mesh.name == 'Ch22_Shirt':
        mesh.data.materials.clear()
        mesh.data.materials.append(lime)
        mesh.data.materials.append(teal)
        mesh.data.materials.append(reflective)
        # Face assignments are part of the shirt mesh itself, so the teal hem
        # and reflective band follow the torso perfectly while it animates.
        for polygon in mesh.data.polygons:
            center = mesh.matrix_world @ polygon.center
            if center.z < 1.135:
                polygon.material_index = 1
            elif 1.190 <= center.z <= 1.235:
                polygon.material_index = 2
    elif mesh.name == 'Ch22_Pants':
        mesh.data.materials.clear()
        mesh.data.materials.append(teal)
        mesh.data.materials.append(reflective)
        mesh.data.materials.append(lime)
        # Lower-leg bands are assigned on the continuous trouser geometry,
        # not attached as separate blocks.
        for polygon in mesh.data.polygons:
            center = mesh.matrix_world @ polygon.center
            if 0.150 <= center.z <= 0.205:
                polygon.material_index = 1
            elif 0.205 < center.z <= 0.235:
                polygon.material_index = 2
    elif mesh.name == 'Ch22_Sneakers':
        mesh.data.materials.clear()
        mesh.data.materials.append(dark)
    elif mesh.name == 'Ch22_Hair' or mesh.name == 'Ch22_Eyelashes':
        mesh.data.materials.clear()
        mesh.data.materials.append(hair)
    elif mesh.name == 'Ch22_Body':
        mesh.data.materials.clear()
        mesh.data.materials.append(skin)

# Deliberate minimal uniform additions. These attach to the canonical bones;
# they are clothing accents, never a second rig or a replacement animation.
bpy.context.scene.frame_set(1)
chest = canonical_armature.matrix_world @ canonical_armature.pose.bones['mixamorig:Spine2'].head
hips = canonical_armature.matrix_world @ canonical_armature.pose.bones['mixamorig:Hips'].head
soft_box('Cleaner_UtilityBelt', hips + Vector((0.0, -0.015, 0.02)), (0.19, 0.17, 0.028), dark, canonical_armature, 'mixamorig:Hips')
soft_box('Cleaner_UtilityPouch', hips + Vector((0.18, -0.02, -0.02)), (0.055, 0.055, 0.075), dark, canonical_armature, 'mixamorig:Hips')
for side in ('Left', 'Right'):
    hand = canonical_armature.matrix_world @ canonical_armature.pose.bones['mixamorig:{}Hand'.format(side)].head
    soft_sphere('Cleaner_{}_Glove'.format(side), hand, (0.060, 0.050, 0.060), dark, canonical_armature, 'mixamorig:{}Hand'.format(side))
    thigh = canonical_armature.matrix_world @ canonical_armature.pose.bones['mixamorig:{}UpLeg'.format(side)].head
    soft_box('Cleaner_{}_CargoPocket'.format(side), thigh + Vector((0.10 if side == 'Left' else -0.10, -0.055, -0.20)), (0.055, 0.028, 0.075), teal, canonical_armature, 'mixamorig:{}UpLeg'.format(side))

# Exact established treatment: remove only forward root drift, retaining the
# source action's vertical motion, hips, leg timing and arm swing.
forward_path = 'pose.bones["mixamorig:Hips"].location'
forward = next(curve for curve in canonical_action.fcurves if curve.data_path == forward_path and curve.array_index == 2)
first, last = forward.keyframe_points[0], forward.keyframe_points[-1]
span = last.co.x - first.co.x
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0.0 else (point.co.x - first.co.x) / span
    drift = first.co.y + (last.co.y - first.co.y) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()

scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.render.fps = 30
scene.eevee.taa_render_samples = 32
scene.world.color = (0.05, 0.05, 0.05)

bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = 'Camera_CanonicalWalk_Orthographic_Locked'
camera.data.type = 'ORTHO'
# A 32 px runtime frame needs the character itself near 28 px high: enough
# head/boot/colour read, with a small safe margin for the walk poses.
camera.data.ortho_scale = 1.80
target = Vector((0.0, 0.0, 0.88))
camera.location = target + Vector((6.0, -6.0, 6.0))
look_at(camera, target)
scene.camera = camera
bpy.ops.object.light_add(type='AREA', location=(4, -4, 7))
key = bpy.context.object
key.data.energy = 350
key.data.size = 5.0
look_at(key, target)
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.data.energy = 80
fill.data.size = 4.0
look_at(fill, target)

os.makedirs(OUT_DIR, exist_ok=True)
# Static approval checkpoint only. Do not commit a direction set or runtime
# spritesheet until the visual language has been approved.
scene.frame_set(25)
scene.render.filepath = os.path.join(OUT_DIR, 'approval_se_frame_25.png')
bpy.ops.render.render(write_still=True)
# Runtime legibility checkpoint: same locked camera and anchor, rendered at
# the actual 32 px canvas rather than judged only from the large source.
scene.render.resolution_x = 32
scene.render.resolution_y = 32
scene.render.filepath = os.path.join(OUT_DIR, 'approval_se_frame_25_32.png')
bpy.ops.render.render(write_still=True)

# First runtime-scale motion checkpoint only: the unchanged canonical phases
# become a 4×1 SE sheet. Other directions remain deliberately out of scope.
DIRECTIONS = [('se', 0.0), ('sw', pi * 0.5), ('nw', pi), ('ne', -pi * 0.5)]
for direction, angle in DIRECTIONS:
    direction_dir = os.path.join(OUT_DIR, 'runtime_32', direction)
    os.makedirs(direction_dir, exist_ok=True)
    canonical_armature.rotation_euler = (0.0, 0.0, angle)
    bpy.context.view_layer.update()
    runtime_frames = []
    for index, frame in enumerate(FRAMES):
        scene.frame_set(frame)
        path = os.path.join(direction_dir, 'frame_{:02d}.png'.format(index))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        runtime_frames.append(path)
    sheet = bpy.data.images.new('worker_cleaner_female_walk_{}_32'.format(direction), width=128, height=32, alpha=True)
    pixels = [0.0] * (128 * 32 * 4)
    for index, path in enumerate(runtime_frames):
        image = bpy.data.images.load(path, check_existing=False)
        source = list(image.pixels)
        for y in range(32):
            target_start = (y * 128 + index * 32) * 4
            source_start = y * 32 * 4
            pixels[target_start:target_start + 32 * 4] = source[source_start:source_start + 32 * 4]
        bpy.data.images.remove(image)
    sheet.pixels = pixels
    sheet.filepath_raw = os.path.join(direction_dir, 'walk_{}_32.png'.format(direction))
    sheet.file_format = 'PNG'
    sheet.save()
    bpy.data.images.remove(sheet)
canonical_armature.rotation_euler = (0.0, 0.0, 0.0)

bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('WORKER_CLEANER_FEMALE_3D_STATIC_V3 output={}'.format(OUT_DIR))
