import bpy
import os
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCENE_OUT = os.path.join(ROOT, 'scenes', 'worker_cleaner_female_gp_v1.blend')
OUT = os.path.join(ROOT, 'output', 'worker_cleaner_female_gp_v1')
os.makedirs(OUT, exist_ok=True)


def gp_material(name, stroke, fill):
    material = bpy.data.materials.new(name)
    bpy.data.materials.create_gpencil_data(material)
    material.grease_pencil.color = (*stroke, 1.0)
    material.grease_pencil.fill_color = (*fill, 1.0)
    material.grease_pencil.show_fill = True
    return material


INK = gp_material('GP_Ink', (0.035, 0.05, 0.07), (0.035, 0.05, 0.07))
SKIN = gp_material('GP_Skin', (0.30, 0.12, 0.07), (0.72, 0.36, 0.20))
HAIR = gp_material('GP_Hair', (0.06, 0.018, 0.008), (0.12, 0.035, 0.012))
LIME = gp_material('GP_Lime', (0.10, 0.28, 0.06), (0.52, 0.92, 0.12))
TEAL = gp_material('GP_Teal', (0.0, 0.14, 0.14), (0.015, 0.38, 0.35))
REFLECT = gp_material('GP_Reflective', (0.35, 0.35, 0.38), (0.86, 0.88, 0.90))
DARK = gp_material('GP_Dark', (0.01, 0.015, 0.025), (0.045, 0.055, 0.075))


def polygon(frame, coords, mat_index):
    stroke = frame.strokes.new()
    stroke.display_mode = '3DSPACE'
    stroke.material_index = mat_index
    stroke.draw_cyclic = True  # Blender 2.90 name; newer releases call it use_cyclic.
    stroke.points.add(count=len(coords))
    for i, point in enumerate(coords):
        stroke.points[i].co = point
        stroke.points[i].pressure = 1.0
        stroke.points[i].strength = 1.0
    return stroke


def ellipse(cx, cy, rx, ry, count=12):
    from math import cos, sin, pi
    return [(cx + cos(2 * pi * i / count) * rx, cy + sin(2 * pi * i / count) * ry) for i in range(count)]


# This is a purposefully simple 2D production test: it proves the proper
# Grease Pencil data path (layers + frame drawings + transparent PNG), not a
# finished art asset. The four frames use the same approved chronological
# phase labels as the runtime walk contract.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

gp = bpy.data.grease_pencils.new('CITY_HORIZON_WORKER_FEMALE_GP_V1')
worker = bpy.data.objects.new('CITY_HORIZON_WORKER_FEMALE_GP_V1', gp)
bpy.context.collection.objects.link(worker)
for material in (INK, SKIN, HAIR, LIME, TEAL, REFLECT, DARK):
    worker.data.materials.append(material)

# Locked production camera. Strokes are constructed on a camera-facing plane
# so the resulting sprite follows City Horizon's 2:1 visual viewpoint while
# retaining the precision of a 2D drawing.
target = Vector((0.0, 0.0, 1.18))
bpy.ops.object.camera_add(location=target + Vector((6.0, -6.0, 6.0)))
camera = bpy.context.object
camera.name = 'CITY_HORIZON_CAMERA_2_TO_1_LOCKED_GP'
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 3.0
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = camera
# Force Blender 2.90 to evaluate the new camera transform before deriving the
# drawing plane. Without this, the Grease Pencil art can be built in the
# camera's previous (default) orientation.
bpy.context.view_layer.update()

right = camera.matrix_world.to_3x3() @ Vector((1, 0, 0))
up = camera.matrix_world.to_3x3() @ Vector((0, 1, 0))
forward = camera.matrix_world.to_3x3() @ Vector((0, 0, -1))
plane_origin = target + forward * 0.18

def screen_to_world(points):
    return [plane_origin + right * x + up * y for x, y in points]


layer = gp.layers.new('ART_SE_WALK', set_active=True)
phases = [
    (25, 'contact_left', -0.14, 0.14),
    (1, 'passing', 0.02, -0.02),
    (9, 'contact_right', 0.14, -0.14),
    (17, 'passing', -0.02, 0.02),
]

for frame_number, phase, left_step, right_step in phases:
    frame = layer.frames.new(frame_number)
    # Back-to-front drawing order gives the silhouette a clean illustrated
    # hierarchy: hair, body, limbs, uniform details, then face accents.
    polygon(frame, screen_to_world(ellipse(0.12, 0.76, 0.14, 0.19)), 2)  # ponytail
    polygon(frame, screen_to_world(ellipse(0.0, 0.91, 0.22, 0.25)), 1)   # head
    polygon(frame, screen_to_world(ellipse(0.0, 1.04, 0.23, 0.11)), 2)   # hair cap
    polygon(frame, screen_to_world([(-0.24, 0.69), (0.24, 0.69), (0.30, 0.28), (-0.30, 0.28)]), 4)
    polygon(frame, screen_to_world([(-0.27, 0.67), (0.27, 0.67), (0.23, 0.40), (-0.23, 0.40)]), 3)
    # Arms move in counterphase; a deliberately broad glove silhouette keeps
    # them readable after downscaling to the future 32 px runtime size.
    polygon(frame, screen_to_world([(-0.24, 0.63), (-0.39, 0.40 + right_step), (-0.31, 0.34 + right_step), (-0.16, 0.57)]), 1)
    polygon(frame, screen_to_world([(-0.39, 0.40 + right_step), (-0.44, 0.29 + right_step), (-0.33, 0.25 + right_step), (-0.29, 0.35 + right_step)]), 6)
    polygon(frame, screen_to_world([(0.24, 0.63), (0.39, 0.40 + left_step), (0.31, 0.34 + left_step), (0.16, 0.57)]), 1)
    polygon(frame, screen_to_world([(0.39, 0.40 + left_step), (0.44, 0.29 + left_step), (0.33, 0.25 + left_step), (0.29, 0.35 + left_step)]), 6)
    # Separate articulated trouser legs and dark work boots.
    polygon(frame, screen_to_world([(-0.24, 0.30), (-0.02, 0.30), (-0.07 + left_step, -0.32), (-0.25 + left_step, -0.32)]), 4)
    polygon(frame, screen_to_world([(0.02, 0.30), (0.24, 0.30), (0.25 + right_step, -0.32), (0.07 + right_step, -0.32)]), 4)
    polygon(frame, screen_to_world([(-0.28 + left_step, -0.32), (-0.03 + left_step, -0.32), (0.01 + left_step, -0.43), (-0.30 + left_step, -0.43)]), 6)
    polygon(frame, screen_to_world([(0.03 + right_step, -0.32), (0.28 + right_step, -0.32), (0.30 + right_step, -0.43), (-0.01 + right_step, -0.43)]), 6)
    # Safety bands, belt and compact side pouch.
    polygon(frame, screen_to_world([(-0.27, 0.48), (0.27, 0.48), (0.25, 0.42), (-0.25, 0.42)]), 5)
    polygon(frame, screen_to_world([(-0.27, 0.32), (0.27, 0.32), (0.25, 0.27), (-0.25, 0.27)]), 6)
    polygon(frame, screen_to_world([(0.23, 0.34), (0.36, 0.34), (0.36, 0.18), (0.23, 0.18)]), 6)
    polygon(frame, screen_to_world([(-0.24 + left_step, -0.17), (-0.06 + left_step, -0.17), (-0.06 + left_step, -0.21), (-0.24 + left_step, -0.21)]), 5)
    polygon(frame, screen_to_world([(0.06 + right_step, -0.17), (0.24 + right_step, -0.17), (0.24 + right_step, -0.21), (0.06 + right_step, -0.21)]), 5)
    # Minimal face/hair read: it is intentionally not a detailed portrait.
    polygon(frame, screen_to_world(ellipse(-0.075, 0.93, 0.018, 0.024, 8)), 0)
    polygon(frame, screen_to_world(ellipse(0.075, 0.93, 0.018, 0.024, 8)), 0)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 0.7
scene.eevee.gtao_factor = 1.1
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.frame_start = 1
scene.frame_end = 25

for i, frame_number in enumerate((25, 1, 9, 17)):
    scene.frame_set(frame_number)
    scene.render.filepath = os.path.join(OUT, 'se_frame_{:02d}.png'.format(i))
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('CITY_HORIZON_GREASE_PENCIL_WORKER_V1_CREATED')
print('FRAMES=25,1,9,17')
