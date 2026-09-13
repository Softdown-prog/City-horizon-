"""Set up the authored worker-model scene without changing any game assets.

The target PNG is an art reference only.  The canonical Mixamo armature/action
remain the sole animation contract; the custom mesh will be authored around it.
"""
import bpy
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CANONICAL = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
REFERENCE = os.path.join(ROOT, 'references', 'worker_cleaner_female_turnaround.png')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'worker_cleaner_female_custom_model_wip.blend')


bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Rig and approved action: this is the only skeleton/action allowed in the WIP.
bpy.ops.import_scene.fbx(filepath=CANONICAL, use_anim=True)
armature = next(item for item in bpy.context.scene.objects if item.type == 'ARMATURE')
armature.name = 'CANONICAL_RIG_DO_NOT_EDIT'
action = max(bpy.data.actions, key=lambda item: item.frame_range[1] - item.frame_range[0])
action.name = 'CANONICAL_WALK_25_1_9_17_DO_NOT_EDIT'
armature.animation_data.action = action

# The imported generic mesh is deliberately hidden: it supplies the rig only.
for item in bpy.context.scene.objects:
    if item.type == 'MESH':
        item.hide_viewport = True
        item.hide_render = True

# Image-empty reference for manual modelling in Blender.  It is never rendered
# and never copied to City Horizon's runtime assets.
image = bpy.data.images.load(REFERENCE, check_existing=False)
bpy.ops.object.empty_add(type='IMAGE', location=(2.6, 0.0, 1.5))
reference = bpy.context.object
reference.name = 'REFERENCE_ONLY_ApprovedWorkerDesign'
reference.data = image
reference.empty_display_size = 3.0
reference.empty_image_side = 'FRONT'
reference.show_in_front = True

# Organize the scene so future authored objects have a clear, non-donor home.
reference_collection = bpy.data.collections.new('REFERENCE_ONLY')
bpy.context.scene.collection.children.link(reference_collection)
for collection in list(reference.users_collection):
    collection.objects.unlink(reference)
reference_collection.objects.link(reference)

custom_collection = bpy.data.collections.new('CUSTOM_WORKER_MESH_WIP')
bpy.context.scene.collection.children.link(custom_collection)

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 32
bpy.context.scene.render.film_transparent = True
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)

print('CUSTOM_WORKER_MODEL_WIP_READY')
print('RIG={}'.format(armature.name))
print('ACTION={}'.format(action.name))
print('REFERENCE={}'.format(REFERENCE))
print('SCENE={}'.format(SCENE_OUT))
