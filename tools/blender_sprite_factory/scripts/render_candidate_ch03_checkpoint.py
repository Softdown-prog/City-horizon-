import bpy
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CANDIDATE = os.environ.get('CITY_HORIZON_CANDIDATE', os.path.join(ROOT, 'input', 'candidate_ch03_nonpbr.fbx'))
CANONICAL_SOURCE = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
LABEL = os.environ.get('CITY_HORIZON_CANDIDATE_LABEL', 'candidate_ch03')
SCENE_OUT = os.path.join(ROOT, 'scenes', '{}_checkpoint.blend'.format(LABEL))
OUT = os.path.join(ROOT, 'output', '{}_checkpoint'.format(LABEL), 'se', 'frame_00.png')


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def armatures(scene):
    return [obj for obj in scene.objects if obj.type == 'ARMATURE']


bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Import the furnished, dressed candidate first. Its source file is never
# changed. It contains the standard 65-bone Mixamo naming scheme.
bpy.ops.import_scene.fbx(filepath=CANDIDATE, use_anim=True)
candidate_armature = armatures(bpy.context.scene)[0]
candidate_armature.name = 'Candidate_{}_Armature'.format(LABEL)
candidate_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

# Import canonical source only to take its existing approved Action. The
# second character is hidden; no alternate walk or retiming is introduced.
bpy.ops.import_scene.fbx(filepath=CANONICAL_SOURCE, use_anim=True)
all_armatures = armatures(bpy.context.scene)
walk_armature = next(obj for obj in all_armatures if obj != candidate_armature)
canonical_action = walk_armature.animation_data.action
canonical_action.name = 'CANONICAL_WALK_SOURCE_25_1_9_17'

candidate_armature.animation_data_create()
candidate_armature.animation_data.action = canonical_action
for obj in bpy.context.scene.objects:
    if obj != candidate_armature and (obj == walk_armature or obj.parent == walk_armature):
        obj.hide_render = True

# Preserve natural vertical body motion but cancel the action's forward drift
# in this checkpoint-only imported copy.
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

scene = bpy.context.scene
scene.frame_set(25)  # Canonical left-contact pose.
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

# The existing City Horizon locked orthographic reference camera, SE view.
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
print('CANDIDATE_CHECKPOINT label={} action={} frame=25 SE={}'.format(LABEL, canonical_action.name, OUT))
