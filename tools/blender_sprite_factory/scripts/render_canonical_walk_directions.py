import bpy
import os
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FBX = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'canonical_walk.blend')
OUT_ROOT = os.path.join(ROOT, 'output', 'canonical_walk')

# Canonical biomechanical sample points: never vary by direction.
FRAMES = [25, 1, 9, 17]
# Real model rotations around Z; artwork is never mirrored.
DIRECTIONS = [('se', 0.0), ('sw', 90.0), ('nw', 180.0), ('ne', 270.0)]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def compose_sheet(folder, direction):
    sheet = bpy.data.images.new('walk_' + direction, width=1024, height=256, alpha=True)
    pixels = [0.0] * (1024 * 256 * 4)
    for index in range(4):
        image = bpy.data.images.load(os.path.join(folder, 'frame_{:02d}.png'.format(index)), check_existing=False)
        source = list(image.pixels)
        for y in range(256):
            pixels[(y * 1024 + index * 256) * 4:(y * 1024 + (index + 1) * 256) * 4] = source[y * 256 * 4:(y + 1) * 256 * 4]
        bpy.data.images.remove(image)
    sheet.pixels = pixels
    sheet.filepath_raw = os.path.join(folder, 'walk_{}.png'.format(direction))
    sheet.file_format = 'PNG'
    sheet.save()
    bpy.data.images.remove(sheet)


# Fresh tool-only scene: the supplied FBX is read but never modified.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
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
forward = next(curve for curve in action.fcurves if curve.data_path == hips_path and curve.array_index == 2)
first = forward.keyframe_points[0]
last = forward.keyframe_points[-1]
span = last.co.x - first.co.x
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0.0 else (point.co.x - first.co.x) / span
    drift = first.co.y + (last.co.y - first.co.y) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()

# Use the original model's single root. Its child mesh follows this genuine
# model rotation, preserving lighting/asymmetry instead of mirroring pixels.
model_root = armature
# FBX has an import-space correction on the armature. Compose each yaw around
# the world Z axis from its original matrix; rotating Euler Z locally would
# rotate around the imported axis and can lay the character on its side.
base_matrix = model_root.matrix_world.copy()

tile_mesh = bpy.data.meshes.new('CityHorizonTile128x64')
tile_mesh.from_pydata([(0, -0.64, 0), (1.28, 0, 0), (0, 0.64, 0), (-1.28, 0, 0)], [], [[0, 1, 2, 3]])
tile = bpy.data.objects.new('Calibration_Tile_128x64', tile_mesh)
scene.collection.objects.link(tile)
tile.hide_render = True

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
key.name = 'Key_Light_Soft'
key.data.energy = 350
key.data.size = 5.0
look_at(key, (0, 0, 0.8))
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.name = 'Fill_Light_Soft'
fill.data.energy = 80
fill.data.size = 4.0
look_at(fill, (0, 0, 0.8))

for direction, degrees in DIRECTIONS:
    model_root.matrix_world = Matrix.Rotation(degrees * 3.141592653589793 / 180.0, 4, 'Z') @ base_matrix
    folder = os.path.join(OUT_ROOT, direction)
    os.makedirs(folder, exist_ok=True)
    for index, frame in enumerate(FRAMES):
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(folder, 'frame_{:02d}.png'.format(index))
        bpy.ops.render.render(write_still=True)
    compose_sheet(folder, direction)

scene.frame_start = 1
scene.frame_end = 32
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CANONICAL_WALK_RENDERED directions={} frames={} camera=locked_ortho'.format([item[0] for item in DIRECTIONS], FRAMES))
