import bpy
import os

# Minimal compatibility render: intentionally simple and independent from City Horizon.
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.render.filepath = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'output', 'compatibility_render', 'blender_rgba_test.png')
)

# Default cube plus a light and a fixed orthographic camera.
cube = bpy.data.objects.get('Cube')
if cube is None:
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    cube = bpy.context.object

camera = bpy.data.objects.get('Camera')
if camera is None:
    bpy.ops.object.camera_add(location=(5, -5, 5))
    camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 5.0
camera.location = (5, -5, 5)
camera.rotation_euler = (0.9553166, 0.0, 0.7853982)
scene.camera = camera

light = bpy.data.objects.get('Light')
if light is None:
    bpy.ops.object.light_add(type='AREA', location=(4, -4, 6))
    light = bpy.context.object
light.data.energy = 600
if light.data.type == 'AREA':
    light.data.size = 5
elif hasattr(light.data, 'shadow_soft_size'):
    light.data.shadow_soft_size = 2.0

bpy.ops.wm.save_as_mainfile(
    filepath=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scenes', 'city_horizon_sprite_factory.blend'))
)
bpy.ops.render.render(write_still=True)
