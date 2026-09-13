import bpy
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REFERENCE = os.path.join(ROOT, 'references', 'worker_cleaner_female_style_target.png')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'city_horizon_worker_female_static_v2.blend')
OUT = os.path.join(ROOT, 'output', 'city_horizon_worker_female_static_v2')
os.makedirs(OUT, exist_ok=True)

def material(name, color, roughness=0.6):
    value = bpy.data.materials.new(name)
    value.use_nodes = True
    node = value.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1.0)
    node.inputs['Roughness'].default_value = roughness
    node.inputs['Specular'].default_value = 0.28
    return value

SKIN = material('CH_Skin', (0.82, 0.46, 0.28))
HAIR = material('CH_Hair', (0.14, 0.050, 0.020), 0.72)
LIME = material('CH_SafetyLime', (0.52, 0.92, 0.12))
TEAL = material('CH_WorkwearTeal', (0.015, 0.38, 0.35))
REFLECT = material('CH_Reflective', (0.78, 0.82, 0.80), 0.34)
DARK = material('CH_BootGloveBelt', (0.025, 0.035, 0.05), 0.66)
EYE = material('CH_Eyes', (0.015, 0.012, 0.009), 0.4)

def finish(obj, mat):
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj

def sphere(name, loc, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, mat)

def cone(name, loc, lower, upper, depth, mat):
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=lower, radius2=upper, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    return finish(obj, mat)

def box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bevel = obj.modifiers.new('SoftEdges', 'BEVEL')
    bevel.width = 0.045
    bevel.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    return finish(obj, mat)

def ring(name, loc, major, minor, mat, squash=0.84):
    bpy.ops.mesh.primitive_torus_add(major_segments=20, minor_segments=8, major_radius=major, minor_radius=minor, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale.y = squash
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, mat)

def make_bone(bones, name, head, tail, parent=None):
    item = bones.new(name)
    item.head = head
    item.tail = tail
    if parent:
        item.parent = bones[parent]

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Entirely owned City Horizon armature.
bpy.ops.object.armature_add(enter_editmode=True)
rig = bpy.context.object
rig.name = 'CITY_HORIZON_HUMANOID_RIG_V1'
bones = rig.data.edit_bones
bones.remove(bones[0])
make_bone(bones, 'root', (0, 0, 0), (0, 0, 0.92))
make_bone(bones, 'hips', (0, 0, 0.92), (0, 0, 1.20), 'root')
make_bone(bones, 'spine', (0, 0, 1.20), (0, 0, 1.55), 'hips')
make_bone(bones, 'chest', (0, 0, 1.55), (0, 0, 1.82), 'spine')
make_bone(bones, 'neck', (0, 0, 1.82), (0, 0, 1.98), 'chest')
make_bone(bones, 'head', (0, 0, 1.98), (0, 0, 2.30), 'neck')
for side, x in [('L', -0.18), ('R', 0.18)]:
    make_bone(bones, side + '_upper_arm', (x, 0, 1.73), (x * 2.8, 0, 1.53), 'chest')
    make_bone(bones, side + '_forearm', (x * 2.8, 0, 1.53), (x * 3.6, 0, 1.28), side + '_upper_arm')
    make_bone(bones, side + '_hand', (x * 3.6, 0, 1.28), (x * 3.8, -0.03, 1.16), side + '_forearm')
    make_bone(bones, side + '_thigh', (x, 0, 1.04), (x, 0, 0.54), 'hips')
    make_bone(bones, side + '_shin', (x, 0, 0.54), (x, 0, 0.13), side + '_thigh')
    make_bone(bones, side + '_foot', (x, 0, 0.13), (x, -0.25, 0.08), side + '_shin')
bpy.ops.object.mode_set(mode='OBJECT')

# Owned stylized worker mesh, assembled as rounded designed volumes.
parts = []
parts += [sphere('Head', (0, 0, 2.20), (0.285, 0.265, 0.315), SKIN)]
# The locked camera sits on the -Y side of the model, therefore the face is
# deliberately authored toward -Y and the ponytail is on the opposite side.
parts += [sphere('HairCap', (0, 0.09, 2.34), (0.30, 0.16, 0.18), HAIR)]
parts += [sphere('PonytailBase', (0, 0.29, 2.27), (0.14, 0.12, 0.18), HAIR)]
parts += [sphere('PonytailTip', (0.02, 0.35, 2.15), (0.105, 0.095, 0.15), HAIR)]
parts += [sphere('HairFringeLeft', (-0.16, -0.205, 2.31), (0.105, 0.050, 0.145), HAIR)]
parts += [sphere('HairFringeRight', (0.16, -0.205, 2.31), (0.105, 0.050, 0.145), HAIR)]
parts += [sphere('Nose', (0, -0.255, 2.17), (0.045, 0.050, 0.050), SKIN)]
parts += [sphere('LeftEye', (-0.095, -0.235, 2.22), (0.028, 0.018, 0.035), EYE)]
parts += [sphere('RightEye', (0.095, -0.235, 2.22), (0.028, 0.018, 0.035), EYE)]
parts += [sphere('Neck', (0, 0, 1.96), (0.095, 0.095, 0.11), SKIN)]
parts += [cone('TealShirt', (0, 0, 1.57), 0.335, 0.255, 0.58, TEAL)]
parts += [cone('SafetyPolo', (0, -0.008, 1.72), 0.355, 0.290, 0.48, LIME)]
parts += [box('CollarLeft', (-0.105, -0.24, 1.91), (0.11, 0.025, 0.10), TEAL)]
parts += [box('CollarRight', (0.105, -0.24, 1.91), (0.11, 0.025, 0.10), TEAL)]
parts += [box('PoloPlacket', (0, -0.286, 1.78), (0.028, 0.018, 0.16), TEAL)]
parts += [ring('VestReflectiveBand', (0, 0, 1.55), 0.295, 0.026, REFLECT)]
parts += [box('VestChestReflectiveBand', (0, -0.285, 1.66), (0.28, 0.022, 0.032), REFLECT)]
parts += [box('VestLeftReflectiveStrap', (-0.19, -0.27, 1.75), (0.025, 0.020, 0.15), REFLECT)]
parts += [box('VestRightReflectiveStrap', (0.19, -0.27, 1.75), (0.025, 0.020, 0.15), REFLECT)]
parts += [box('VestTealHem', (0, -0.285, 1.47), (0.31, 0.023, 0.045), TEAL)]
parts += [ring('UtilityBelt', (0, 0, 1.38), 0.305, 0.035, DARK)]
parts += [box('UtilityPouch', (0.28, 0.14, 1.39), (0.10, 0.065, 0.13), DARK)]
for side, x in [('L', -0.18), ('R', 0.18)]:
    parts += [sphere(side + '_UpperArm', (x * 2.05, 0, 1.61), (0.105, 0.105, 0.17), LIME)]
    parts += [sphere(side + '_Forearm', (x * 3.15, 0, 1.38), (0.085, 0.085, 0.16), SKIN)]
    parts += [sphere(side + '_Glove', (x * 3.75, -0.01, 1.18), (0.10, 0.09, 0.11), DARK)]
    parts += [sphere(side + '_Thigh', (x, 0, 0.80), (0.17, 0.16, 0.31), TEAL)]
    parts += [sphere(side + '_Shin', (x, 0, 0.33), (0.145, 0.14, 0.26), TEAL)]
    parts += [box(side + '_CargoPocket', (x * 1.18, 0.145, 0.78), (0.075, 0.026, 0.11), TEAL)]
    parts += [ring(side + '_ReflectiveCuff', (x, 0, 0.27), 0.125, 0.025, REFLECT)]
    parts += [box(side + '_BootAnkle', (x, 0.00, 0.12), (0.16, 0.18, 0.13), DARK)]
    parts += [box(side + '_BootToe', (x, -0.16, 0.075), (0.17, 0.22, 0.105), DARK)]

# The authored mesh remains composed of deliberately separated mesh parts.
# Unlike automatic weights on disconnected primitives, direct bone parenting
# gives every limb, boot, glove and hair mass a stable, inspectable owner.
mesh = parts[0]
mesh.name = 'CITY_HORIZON_WORKER_FEMALE_MESH_V1_HEAD'

def bone_for_part(name):
    if name.startswith('L_'):
        if any(token in name for token in ('UpperArm', 'Forearm', 'Glove')):
            return 'L_upper_arm' if 'UpperArm' in name else 'L_forearm'
        if any(token in name for token in ('Thigh', 'CargoPocket')):
            return 'L_thigh'
        if any(token in name for token in ('Shin', 'ReflectiveCuff')):
            return 'L_shin'
        if 'Boot' in name:
            return 'L_foot'
    if name.startswith('R_'):
        if any(token in name for token in ('UpperArm', 'Forearm', 'Glove')):
            return 'R_upper_arm' if 'UpperArm' in name else 'R_forearm'
        if any(token in name for token in ('Thigh', 'CargoPocket')):
            return 'R_thigh'
        if any(token in name for token in ('Shin', 'ReflectiveCuff')):
            return 'R_shin'
        if 'Boot' in name:
            return 'R_foot'
    if name in ('Head', 'HairCap', 'Ponytail', 'HairFringeLeft', 'HairFringeRight', 'Nose', 'LeftEye', 'RightEye'):
        return 'head'
    if name == 'Neck':
        return 'neck'
    if name in ('TealShirt', 'SafetyPolo', 'VestReflectiveBand', 'VestChestReflectiveBand', 'VestLeftReflectiveStrap', 'VestRightReflectiveStrap', 'VestTealHem'):
        return 'chest'
    return 'hips'

for item in parts:
    world = item.matrix_world.copy()
    item.parent = rig
    item.parent_type = 'BONE'
    item.parent_bone = bone_for_part(item.name)
    item.matrix_world = world

# Four pose walk, authored from scratch for this owned rig.  The timing/order
# intentionally mirrors the approved runtime convention:
# 25 contact-left -> 1 passing -> 9 contact-right -> 17 passing.
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='POSE')
for item in rig.pose.bones:
    item.rotation_mode = 'XYZ'
for frame, swing, bob in [(1, 0.0, 0.030), (9, -0.40, 0.0), (17, 0.0, 0.030), (25, 0.40, 0.0), (33, 0.0, 0.030)]:
    for left, right, scale in [('L_thigh', 'R_thigh', 1.0), ('L_upper_arm', 'R_upper_arm', -0.58)]:
        rig.pose.bones[left].rotation_euler.x = swing * scale
        rig.pose.bones[right].rotation_euler.x = -swing * scale
        rig.pose.bones[left].keyframe_insert(data_path='rotation_euler', frame=frame)
        rig.pose.bones[right].keyframe_insert(data_path='rotation_euler', frame=frame)
    rig.pose.bones['L_shin'].rotation_euler.x = 0.20 if swing < 0.0 else 0.0
    rig.pose.bones['R_shin'].rotation_euler.x = 0.20 if swing > 0.0 else 0.0
    rig.pose.bones['L_shin'].keyframe_insert(data_path='rotation_euler', frame=frame)
    rig.pose.bones['R_shin'].keyframe_insert(data_path='rotation_euler', frame=frame)
    rig.pose.bones['hips'].location.z = bob
    rig.pose.bones['hips'].keyframe_insert(data_path='location', frame=frame)
bpy.ops.object.mode_set(mode='OBJECT')
rig.animation_data.action.name = 'CITY_HORIZON_WALK_V1_OWNED'

# Locked 2:1 City Horizon camera: 45 degrees around Z and 35.264 degrees
# above the ground plane (the location vector is 6, -6, 6 from the target).
camera_target = Vector((0, 0, 1.18))
bpy.ops.object.camera_add(location=camera_target + Vector((6.0, -6.0, 6.0)))
camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.55
camera.name = 'CITY_HORIZON_CAMERA_2_TO_1_LOCKED'
camera.rotation_euler = (camera_target - camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = camera
for location, energy, size in [((4, -4, 7), 460, 5.0), ((-4, -2, 4), 120, 4.0)]:
    bpy.ops.object.light_add(type='AREA', location=location)
    bpy.context.object.data.energy = energy
    bpy.context.object.data.size = size

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 0.7
scene.eevee.gtao_factor = 1.2
scene.eevee.use_soft_shadows = True
scene.eevee.taa_render_samples = 64
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.frame_start = 1
scene.frame_end = 32
# Deliberately render one approval pose before committing further animation
# output. The motion data remains in the scene, but the visual target comes
# first in this pass.
scene.frame_set(25)
scene.render.filepath = os.path.join(OUT, 'approval_se_frame_25.png')
bpy.ops.render.render(write_still=True)

reference_image = bpy.data.images.load(REFERENCE, check_existing=False)
bpy.ops.object.empty_add(type='IMAGE', location=(2.2, 0.6, 1.5))
reference = bpy.context.object
reference.name = 'REFERENCE_ONLY_TargetWorker'
reference.data = reference_image
reference.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CITY_HORIZON_WORKER_FEMALE_V1_CREATED')
print('RIG=' + rig.name)
print('MESH=' + mesh.name)
print('ACTION=' + rig.animation_data.action.name)
