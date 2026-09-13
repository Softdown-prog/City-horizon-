import bpy
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FBX = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'city_horizon_sprite_factory.blend')
OUT = os.path.join(ROOT, 'output', 'test_walk_se')
# Ordered biomechanically: left contact, passing, right contact, passing.
FRAMES = [25, 1, 9, 17]
os.makedirs(OUT, exist_ok=True)

def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

# Fresh working scene. The original FBX is only read and is never overwritten.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for item in list(bpy.data.actions):
    bpy.data.actions.remove(item)
bpy.ops.import_scene.fbx(filepath=FBX, use_anim=True)

scene = bpy.context.scene
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

armature = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
action = armature.animation_data.action
hips_path = 'pose.bones["mixamorig:Hips"].location'

# Only remove root locomotion: subtract the straight start->end displacement
# from the forward translation curve. The remaining local sway is retained.
forward = next(curve for curve in action.fcurves if curve.data_path == hips_path and curve.array_index == 2)
first = forward.keyframe_points[0]
last = forward.keyframe_points[-1]
start_frame, start_value = first.co.x, first.co.y
end_frame, end_value = last.co.x, last.co.y
span = end_frame - start_frame
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0 else (point.co.x - start_frame) / span
    drift = start_value + (end_value - start_value) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()

# Logical 128x64 City Horizon tile: calibration-only, never rendered.
tile_mesh = bpy.data.meshes.new('CityHorizonTile128x64')
tile_mesh.from_pydata([(0, -0.64, 0), (1.28, 0, 0), (0, 0.64, 0), (-1.28, 0, 0)], [], [[0, 1, 2, 3]])
tile = bpy.data.objects.new('Calibration_Tile_128x64', tile_mesh)
scene.collection.objects.link(tile)
tile.hide_render = True

# Locked SE-style isometric camera: 45-degree horizontal and 35.264-degree elevation.
bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = 'Camera_SE_Orthographic_Locked'
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.65
target = Vector((0.0, 0.0, 0.88))
camera.location = target + Vector((6.0, -6.0, 6.0))
look_at(camera, target)
scene.camera = camera

bpy.ops.object.light_add(type='AREA', location=(4, -4, 7))
key = bpy.context.object
key.name = 'Key_Light_Soft'
key.data.energy = 350
key.data.size = 5.0
look_at(key, (0, 0, 0.8))

# A subtle fill light avoids unreadable black faces at micro-scale.
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.name = 'Fill_Light_Soft'
fill.data.energy = 80
fill.data.size = 4.0
look_at(fill, (0, 0, 0.8))

for index, frame in enumerate(FRAMES):
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(OUT, 'frame_{:02d}.png'.format(index))
    bpy.ops.render.render(write_still=True)

# Assemble a fixed 4x1 source spritesheet without alpha cropping.
sheet = bpy.data.images.new('cleaner_walk_se', width=1024, height=256, alpha=True)
pixels = [0.0] * (1024 * 256 * 4)
for index in range(4):
    image = bpy.data.images.load(os.path.join(OUT, 'frame_{:02d}.png'.format(index)), check_existing=False)
    src = list(image.pixels)
    for y in range(256):
        src_offset = y * 256 * 4
        dst_offset = (y * 1024 + index * 256) * 4
        pixels[dst_offset:dst_offset + 256 * 4] = src[src_offset:src_offset + 256 * 4]
    bpy.data.images.remove(image)
sheet.pixels = pixels
sheet.filepath_raw = os.path.join(OUT, 'cleaner_walk_se.png')
sheet.file_format = 'PNG'
sheet.save()

scene.frame_start = 1
scene.frame_end = 32
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CITY_HORIZON_WALK_RENDER frames={} output={} ortho_scale={}'.format(FRAMES, OUT, camera.data.ortho_scale))
