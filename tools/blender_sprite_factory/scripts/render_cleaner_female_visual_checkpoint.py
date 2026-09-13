import bpy
import os
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FBX = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'cleaner_female_visual_checkpoint.blend')
OUT = os.path.join(ROOT, 'output', 'cleaner_female_visual_checkpoint', 'se', 'frame_00.png')


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def material(name, rgb):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    bsdf = result.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.78
    result.diffuse_color = (*rgb, 1.0)
    return result


def attach(obj, armature, bone_name):
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = 'BONE'
    obj.parent_bone = bone_name
    obj.matrix_parent_inverse = (armature.matrix_world @ armature.pose.bones[bone_name].matrix).inverted()
    obj.matrix_world = world
    return obj


def bone_point(armature, name, end='head'):
    bone = armature.pose.bones[name]
    return armature.matrix_world @ getattr(bone, end)


def sphere(name, mat, location, scale, armature=None, bone=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return attach(obj, armature, bone) if armature else obj


def cone_segment(name, mat, armature, bone, radius_a, radius_b, shorten=0.06):
    start = Vector(bone_point(armature, bone, 'head'))
    end = Vector(bone_point(armature, bone, 'tail'))
    axis = end - start
    length = max(0.03, axis.length - shorten)
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=10, radius1=radius_a, radius2=radius_b, depth=length, location=midpoint
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(axis.normalized())
    obj.data.materials.append(mat)
    return attach(obj, armature, bone)


# Isolated checkpoint scene: this intentionally does not overwrite runtime
# sheets or the previously approved canonical animation assets.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=FBX, use_anim=True)
scene = bpy.context.scene
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

armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
for obj in scene.objects:
    if obj.type == 'MESH':
        obj.hide_render = True

# Exact same canonical action, only the forward root drift is neutralized.
action = armature.animation_data.action
forward_path = 'pose.bones["mixamorig:Hips"].location'
forward = next(curve for curve in action.fcurves if curve.data_path == forward_path and curve.array_index == 2)
first, last = forward.keyframe_points[0], forward.keyframe_points[-1]
span = last.co.x - first.co.x
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0.0 else (point.co.x - first.co.x) / span
    drift = first.co.y + (last.co.y - first.co.y) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()
scene.frame_set(25)

# Deliberately simple clothing geometry: the silhouette, not surface detail,
# is the product under review. No source mesh or armature is edited.
lime = material('Cleaner_Shirt_Lime', (0.43, 0.84, 0.18))
teal = material('Cleaner_Trousers_Teal', (0.025, 0.30, 0.27))
teal_dark = material('Cleaner_Shirt_Teal_Detail', (0.015, 0.16, 0.15))
charcoal = material('Cleaner_Boots_Gloves', (0.018, 0.025, 0.04))
skin = material('Cleaner_Skin', (0.62, 0.38, 0.25))
hair = material('Cleaner_Brown_Hair', (0.07, 0.023, 0.015))

# Head and tied hair. The bun sits behind the head and becomes visible as the
# real model rotates to later directions.
head_center = (Vector(bone_point(armature, 'mixamorig:Head', 'head')) + Vector(bone_point(armature, 'mixamorig:Head', 'tail'))) * 0.5
sphere('CleanerFemale_Head', skin, head_center, (0.13, 0.13, 0.15), armature, 'mixamorig:Head')
sphere('CleanerFemale_HairCap', hair, head_center + Vector((0.0, 0.012, 0.075)), (0.145, 0.145, 0.105), armature, 'mixamorig:Head')
sphere('CleanerFemale_Ponytail', hair, head_center + Vector((0.0, 0.13, 0.015)), (0.075, 0.10, 0.09), armature, 'mixamorig:Head')

# Polo shirt: tapered toward the waist, with a dark teal collar/waist detail.
spine_start = Vector(bone_point(armature, 'mixamorig:Spine', 'head'))
spine_end = Vector(bone_point(armature, 'mixamorig:Spine2', 'tail'))
axis = spine_end - spine_start
bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.20, radius2=0.255, depth=axis.length + 0.06, location=(spine_start + spine_end) * 0.5)
shirt = bpy.context.object
shirt.name = 'CleanerFemale_LimePolo'
shirt.rotation_mode = 'QUATERNION'
shirt.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(axis.normalized())
shirt.data.materials.append(lime)
attach(shirt, armature, 'mixamorig:Spine2')
sphere('CleanerFemale_PoloCollar', teal_dark, spine_end + Vector((0.0, -0.005, -0.035)), (0.16, 0.13, 0.035), armature, 'mixamorig:Spine2')

# Arms: lime short sleeves, then exposed forearms and charcoal gloves.
for side in ('Left', 'Right'):
    cone_segment('CleanerFemale_{}_Sleeve'.format(side), lime, armature, 'mixamorig:{}Arm'.format(side), 0.09, 0.11)
    cone_segment('CleanerFemale_{}_Forearm'.format(side), skin, armature, 'mixamorig:{}ForeArm'.format(side), 0.06, 0.07)
    hand = Vector(bone_point(armature, 'mixamorig:{}Hand'.format(side), 'head'))
    sphere('CleanerFemale_{}_Glove'.format(side), charcoal, hand, (0.06, 0.05, 0.055), armature, 'mixamorig:{}Hand'.format(side))

# Hips and trousers: slightly wider hips plus separated upper/lower leg forms
# create a recognizably dressed, natural feminine silhouette at micro scale.
hips = Vector(bone_point(armature, 'mixamorig:Hips', 'head'))
sphere('CleanerFemale_TrouserHips', teal, hips + Vector((0.0, 0.0, -0.025)), (0.22, 0.15, 0.14), armature, 'mixamorig:Hips')
sphere('CleanerFemale_UtilityBelt', teal_dark, hips + Vector((0.0, 0.0, 0.03)), (0.225, 0.155, 0.045), armature, 'mixamorig:Hips')
for side in ('Left', 'Right'):
    cone_segment('CleanerFemale_{}_TrouserUpper'.format(side), teal, armature, 'mixamorig:{}UpLeg'.format(side), 0.11, 0.13)
    cone_segment('CleanerFemale_{}_TrouserLower'.format(side), teal, armature, 'mixamorig:{}Leg'.format(side), 0.09, 0.11)
    lower_start = Vector(bone_point(armature, 'mixamorig:{}Leg'.format(side), 'head'))
    lower_end = Vector(bone_point(armature, 'mixamorig:{}Leg'.format(side), 'tail'))
    band_pos = lower_start.lerp(lower_end, 0.78)
    sphere('CleanerFemale_{}_ReflectiveBand'.format(side), lime, band_pos, (0.105, 0.085, 0.045), armature, 'mixamorig:{}Leg'.format(side))
    foot = Vector(bone_point(armature, 'mixamorig:{}Foot'.format(side), 'head'))
    sphere('CleanerFemale_{}_WorkBoot'.format(side), charcoal, foot + Vector((0.0, -0.03, -0.035)), (0.11, 0.18, 0.065), armature, 'mixamorig:{}Foot'.format(side))

# Locked City Horizon orthographic reference camera, SE only for this review.
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
key.data.energy = 350
key.data.size = 5.0
look_at(key, target)
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.data.energy = 80
fill.data.size = 4.0
look_at(fill, target)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CLEANER_FEMALE_VISUAL_CHECKPOINT frame=25 direction=SE output={}'.format(OUT))
