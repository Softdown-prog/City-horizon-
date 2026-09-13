import bpy
import os
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'scenes', 'city_horizon_sprite_factory.blend'))
scene = bpy.context.scene
point = world_to_camera_view(scene, scene.camera, Vector((0.0, 0.0, 0.0)))
print('GROUND_ANCHOR_PIXEL x={:.3f} y={:.3f}'.format(point.x * 256.0, (1.0-point.y) * 256.0))
