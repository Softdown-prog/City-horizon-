import bpy
import json
import os

fbx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'input', 'mixamo_walk_test.fbx'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)

scene = bpy.context.scene
armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
hips = next((pb for pb in armature.pose.bones if 'hips' in pb.name.lower()), None)
root = next((pb for pb in armature.pose.bones if 'root' in pb.name.lower()), None)
sample_frames = [1, 8, 16, 24, 32]

def sample(bone):
    result = {}
    if bone is None:
        return result
    for frame in sample_frames:
        scene.frame_set(frame)
        result[str(frame)] = [round(v, 6) for v in bone.matrix.translation]
    return result

report = {
    'hip_bone': hips.name if hips else None,
    'root_bone': root.name if root else None,
    'hip_translation_samples': sample(hips),
    'root_translation_samples': sample(root),
}
print('MIXAMO_MOTION=' + json.dumps(report, indent=2))
