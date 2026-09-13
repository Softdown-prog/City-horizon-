import bpy
import json
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
scene_path = os.path.join(ROOT, 'scenes', 'city_horizon_sprite_factory.blend')
bpy.ops.wm.open_mainfile(filepath=scene_path)
scene = bpy.context.scene
armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
hips = armature.pose.bones['mixamorig:Hips']
depsgraph = bpy.context.evaluated_depsgraph_get()
result = {}
for frame in [1, 9, 17, 25]:
    scene.frame_set(frame)
    mesh_points = []
    for obj in scene.objects:
        if obj.type == 'MESH' and not obj.name.startswith('Calibration_'):
            evaluated = obj.evaluated_get(depsgraph)
            mesh_points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    result[str(frame)] = {
        'hips_local_translation': [round(v, 6) for v in hips.matrix.translation],
        'world_bounds': {
            'min': [round(min(p[i] for p in mesh_points), 5) for i in range(3)],
            'max': [round(max(p[i] for p in mesh_points), 5) for i in range(3)],
        },
    }
print('WALK_VALIDATION=' + json.dumps(result, indent=2))
