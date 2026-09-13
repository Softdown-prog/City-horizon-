import bpy
import json
import os
from mathutils import Vector

fbx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'input', 'mixamo_walk_test.fbx'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)
scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()

report = {}
for frame in [1, 9, 17, 25]:
    scene.frame_set(frame)
    points = []
    for obj in scene.objects:
        if obj.type == 'MESH':
            evaluated = obj.evaluated_get(depsgraph)
            points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    low = [min(point[i] for point in points) for i in range(3)]
    high = [max(point[i] for point in points) for i in range(3)]
    report[str(frame)] = {'min': [round(v, 4) for v in low], 'max': [round(v, 4) for v in high]}
print('MIXAMO_BOUNDS=' + json.dumps(report, indent=2))
