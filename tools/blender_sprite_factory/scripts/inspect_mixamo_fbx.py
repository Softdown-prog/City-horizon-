import bpy
import json
import os

fbx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'input', 'mixamo_walk_test.fbx'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)

scene = bpy.context.scene
armatures = [obj for obj in scene.objects if obj.type == 'ARMATURE']
meshes = [obj for obj in scene.objects if obj.type == 'MESH']
actions = list(bpy.data.actions)
action = actions[0] if actions else None

report = {
    'fps': scene.render.fps,
    'mesh_count': len(meshes),
    'mesh_names': [obj.name for obj in meshes],
    'mesh_material_slots': {obj.name: len(obj.material_slots) for obj in meshes},
    'armature_count': len(armatures),
    'armature_names': [obj.name for obj in armatures],
    'bone_counts': {obj.name: len(obj.data.bones) for obj in armatures},
    'action_count': len(actions),
    'action_names': [item.name for item in actions],
    'action_frame_range': list(action.frame_range) if action else None,
    'action_curve_count': len(action.fcurves) if action else 0,
    'object_transforms': {
        obj.name: {'location': list(obj.location), 'scale': list(obj.scale)}
        for obj in armatures + meshes
    },
}
print('MIXAMO_INSPECTION=' + json.dumps(report, indent=2))
