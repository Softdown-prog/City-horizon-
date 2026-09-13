import bpy
import json
import os

fbx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'input', 'mixamo_walk_test.fbx'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)
action = bpy.data.actions[0]
curves = []
for fcurve in action.fcurves:
    if 'Hips' in fcurve.data_path:
        curves.append({
            'path': fcurve.data_path,
            'index': fcurve.array_index,
            'points': [[round(p.co.x, 3), round(p.co.y, 6)] for p in fcurve.keyframe_points],
        })
print('HIPS_CURVES=' + json.dumps(curves, indent=2))
