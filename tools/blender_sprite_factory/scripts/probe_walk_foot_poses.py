import bpy
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'scenes', 'city_horizon_sprite_factory.blend'))
scene = bpy.context.scene
armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
names = ['mixamorig:LeftFoot', 'mixamorig:RightFoot']
report = {}
for frame in [1, 9, 17, 25]:
    scene.frame_set(frame)
    report[str(frame)] = {}
    for name in names:
        point = armature.matrix_world @ armature.pose.bones[name].matrix.translation
        report[str(frame)][name] = [round(v, 5) for v in point]
print('FOOT_POSES=' + json.dumps(report, indent=2))
