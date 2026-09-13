import bpy
import os
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CH22 = os.path.join(ROOT, 'input', 'candidate_ch22_nonpbr.fbx')
CANONICAL = os.path.join(ROOT, 'input', 'mixamo_walk_test.fbx')
SCENE_OUT = os.path.join(ROOT, 'scenes', 'worker_cleaner_female_canonical_rig.blend')
OUT_ROOT = os.path.join(ROOT, 'output', 'worker_cleaner_female')
PREVIEW_ONLY = os.environ.get('CH_STYLE_CHECKPOINT') == '1'
if PREVIEW_ONLY:
    OUT_ROOT = os.path.join(ROOT, 'output', 'worker_cleaner_female_style_checkpoint')
FRAMES = [25, 1, 9, 17]
DIRECTIONS = [('se', 0.0), ('sw', 90.0), ('nw', 180.0), ('ne', 270.0)]
if PREVIEW_ONLY:
    DIRECTIONS = [('se', 0.0)]


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def armatures(scene):
    return [obj for obj in scene.objects if obj.type == 'ARMATURE']


def painted_material(name, rgb):
    # Deliberately restrained "painted 3D" treatment: matte fabric with a
    # soft specular rolloff.  It preserves a clean readable silhouette after
    # reduction to 32 px; procedural texture/noise would turn into shimmer.
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    node = result.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*rgb, 1.0)
    node.inputs['Roughness'].default_value = 0.58
    node.inputs['Specular'].default_value = 0.28
    node.inputs['Sheen'].default_value = 0.08
    result.diffuse_color = (*rgb, 1.0)
    return result


def set_solid_material(mesh, material):
    mesh.data.materials.clear()
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.material_index = 0


def set_workwear_bands(mesh, base, teal, reflective, lower_leg=False):
    """Paint stable garment panels on donor topology, never on world space."""
    mesh.data.materials.clear()
    mesh.data.materials.append(base)
    mesh.data.materials.append(teal)
    mesh.data.materials.append(reflective)
    # Mixamo's imported donor uses local Y as the character's vertical axis.
    # This was measured from Ch22 rather than guessed from Blender world axes.
    height_values = [vertex.co.y for vertex in mesh.data.vertices]
    width_values = [vertex.co.x for vertex in mesh.data.vertices]
    low, high = min(height_values), max(height_values)
    height = max(high - low, 0.0001)
    left, right = min(width_values), max(width_values)
    width = max(right - left, 0.0001)
    for polygon in mesh.data.polygons:
        centre = sum((mesh.data.vertices[index].co.y for index in polygon.vertices), 0.0) / len(polygon.vertices)
        normalised = (centre - low) / height
        centre_x = sum((mesh.data.vertices[index].co.x for index in polygon.vertices), 0.0) / len(polygon.vertices)
        normalised_x = (centre_x - left) / width
        # Broad teal workwear panel, then a narrow warm-white reflective band.
        if lower_leg:
            polygon.material_index = 2 if 0.11 <= normalised <= 0.23 else 0
        elif 0.12 <= normalised <= 0.23:
            polygon.material_index = 1
        elif 0.24 <= normalised <= 0.34:
            polygon.material_index = 2
        # Reflective shoulder straps, expressed in donor-local coordinates so
        # they remain stable while the canonical armature animates the mesh.
        elif normalised >= 0.33 and (0.16 <= normalised_x <= 0.27 or 0.70 <= normalised_x <= 0.81):
            polygon.material_index = 2
        else:
            polygon.material_index = 0


def set_trousers_workwear(mesh, base, reflective, belt):
    mesh.data.materials.clear()
    mesh.data.materials.append(base)
    mesh.data.materials.append(reflective)
    mesh.data.materials.append(belt)
    heights = [vertex.co.y for vertex in mesh.data.vertices]
    low, high = min(heights), max(heights)
    span = max(high - low, 0.0001)
    for polygon in mesh.data.polygons:
        centre = sum((mesh.data.vertices[index].co.y for index in polygon.vertices), 0.0) / len(polygon.vertices)
        position = (centre - low) / span
        if 0.10 <= position <= 0.24:
            polygon.material_index = 1
        elif position >= 0.82:
            polygon.material_index = 2
        else:
            polygon.material_index = 0


def apply_chunky_boot_proportions(mesh):
    """Broaden existing donor footwear around its own centre; no primitives."""
    vertices = mesh.data.vertices
    centre_x = sum(vertex.co.x for vertex in vertices) / len(vertices)
    centre_y = sum(vertex.co.y for vertex in vertices) / len(vertices)
    centre_z = sum(vertex.co.z for vertex in vertices) / len(vertices)
    for vertex in vertices:
        vertex.co.x = centre_x + (vertex.co.x - centre_x) * 1.16
        vertex.co.y = centre_y + (vertex.co.y - centre_y) * 1.04
        vertex.co.z = centre_z + (vertex.co.z - centre_z) * 1.14


def scale_mesh_about_centre(mesh, scale_x, scale_y, scale_z):
    vertices = mesh.data.vertices
    centre_x = sum(vertex.co.x for vertex in vertices) / len(vertices)
    centre_y = sum(vertex.co.y for vertex in vertices) / len(vertices)
    centre_z = sum(vertex.co.z for vertex in vertices) / len(vertices)
    for vertex in vertices:
        vertex.co.x = centre_x + (vertex.co.x - centre_x) * scale_x
        vertex.co.y = centre_y + (vertex.co.y - centre_y) * scale_y
        vertex.co.z = centre_z + (vertex.co.z - centre_z) * scale_z


def stylize_weighted_head(mesh):
    """Broaden only donor head geometry to a City Horizon-friendly silhouette."""
    head = mesh.vertex_groups.get('mixamorig:Head')
    if head is None:
        return
    selected = []
    for vertex in mesh.data.vertices:
        weight = next((item.weight for item in vertex.groups if item.group == head.index), 0.0)
        if weight >= 0.45:
            selected.append(vertex)
    if not selected:
        return
    centre_x = sum(vertex.co.x for vertex in selected) / len(selected)
    centre_y = sum(vertex.co.y for vertex in selected) / len(selected)
    centre_z = sum(vertex.co.z for vertex in selected) / len(selected)
    for vertex in selected:
        vertex.co.x = centre_x + (vertex.co.x - centre_x) * 1.12
        vertex.co.y = centre_y + (vertex.co.y - centre_y) * 1.07
        vertex.co.z = centre_z + (vertex.co.z - centre_z) * 1.12


def tint_hand_mesh_as_gloves(mesh, glove):
    """Use the donor's own weighted hand topology as gloves, not new geometry."""
    hand_groups = [mesh.vertex_groups.get('mixamorig:LeftHand'), mesh.vertex_groups.get('mixamorig:RightHand')]
    hand_indices = {group.index for group in hand_groups if group is not None}
    if not hand_indices:
        return
    mesh.data.materials.append(glove)
    glove_index = len(mesh.data.materials) - 1
    for polygon in mesh.data.polygons:
        weighted = 0
        for vertex_index in polygon.vertices:
            if any(weight.group in hand_indices and weight.weight >= 0.20 for weight in mesh.data.vertices[vertex_index].groups):
                weighted += 1
        if weighted >= max(2, len(polygon.vertices) - 1):
            polygon.material_index = glove_index


def duplicate_as_outer_work_vest(source):
    """A fitted outer garment copied from the donor's real shirt mesh.

    This is deliberate garment geometry, not a primitive glued to the body;
    it retains the canonical rig weights and adds only a thin fabric volume.
    """
    vest = source.copy()
    vest.data = source.data.copy()
    vest.name = 'WorkerCleanerFemale_HighVisibilityVest'
    bpy.context.collection.objects.link(vest)
    solidify = vest.modifiers.new('FittedVestFabricVolume', 'SOLIDIFY')
    solidify.thickness = 0.018
    solidify.offset = 1.0
    return vest


def compose_contact_sheet():
    sheet = bpy.data.images.new('worker_cleaner_female_contact_4x4', width=1024, height=1024, alpha=True)
    pixels = [0.0] * (1024 * 1024 * 4)
    for row, (direction, _) in enumerate(DIRECTIONS):
        for column in range(4):
            image = bpy.data.images.load(os.path.join(OUT_ROOT, direction, 'frame_{:02d}.png'.format(column)), check_existing=False)
            source = list(image.pixels)
            for y in range(256):
                destination = ((row * 256 + y) * 1024 + column * 256) * 4
                source_start = y * 256 * 4
                pixels[destination:destination + 256 * 4] = source[source_start:source_start + 256 * 4]
            bpy.data.images.remove(image)
    sheet.pixels = pixels
    sheet.filepath_raw = os.path.join(OUT_ROOT, 'worker_cleaner_female_contact_4x4.png')
    sheet.file_format = 'PNG'
    sheet.save()
    bpy.data.images.remove(sheet)


# Donor import: its armature and static Action exist only during transfer.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=CH22, use_anim=True)
scene = bpy.context.scene
donor_armature = armatures(scene)[0]
donor_meshes = [obj for obj in scene.objects if obj.type == 'MESH' and obj.name != 'Cube']

# Canonical import: this is the only production animation/skeleton.
bpy.ops.import_scene.fbx(filepath=CANONICAL, use_anim=True)
canonical_armature = next(obj for obj in armatures(scene) if obj != donor_armature)
canonical_action = max(bpy.data.actions, key=lambda action: action.frame_range[1] - action.frame_range[0])
canonical_armature.animation_data.action = canonical_action
canonical_armature.name = 'CANONICAL_RIG'
canonical_action.name = 'CANONICAL_WALK_SOURCE_25_1_9_17'

for obj in scene.objects:
    if obj.type == 'MESH' and obj not in donor_meshes:
        obj.hide_render = True

# Skin binding only: existing Ch22 vertex groups are mapped to the compatible
# canonical bone names. No donor animation or rest pose is retained.
for mesh in donor_meshes:
    world = mesh.matrix_world.copy()
    mesh.parent = canonical_armature
    mesh.matrix_parent_inverse = canonical_armature.matrix_world.inverted()
    mesh.matrix_world = world
    modifiers = [modifier for modifier in mesh.modifiers if modifier.type == 'ARMATURE']
    if not modifiers:
        modifier = mesh.modifiers.new('CanonicalRigSkin', 'ARMATURE')
        modifier.object = canonical_armature
    else:
        for modifier in modifiers:
            modifier.object = canonical_armature
    for group in mesh.vertex_groups:
        canonical_name = group.name.replace('mixamorig2:', 'mixamorig:', 1)
        if canonical_name in canonical_armature.pose.bones:
            group.name = canonical_name

# A restrained uniform recolor of Ch22's existing clothing meshes. No new
# primitive clothing or accessories are created.
lime_polo = painted_material('WorkerCleanerFemale_HighVisibilityLime', (0.48, 0.84, 0.18))
teal_uniform = painted_material('WorkerCleanerFemale_WorkwearTeal', (0.025, 0.28, 0.27))
reflective_band = painted_material('WorkerCleanerFemale_ReflectiveWarmWhite', (0.72, 0.88, 0.36))
teal_trousers = painted_material('WorkerCleanerFemale_Trousers_Teal', (0.025, 0.31, 0.29))
dark_work_shoes = painted_material('WorkerCleanerFemale_WorkShoes_Painted', (0.018, 0.028, 0.050))
utility_belt = painted_material('WorkerCleanerFemale_UtilityBelt', (0.035, 0.045, 0.060))
dark_gloves = painted_material('WorkerCleanerFemale_WorkGloves', (0.09, 0.11, 0.14))
for mesh in donor_meshes:
    if mesh.name == 'Ch22_Shirt':
        # Dark fitted polo sits under a separate, visibly thicker safety vest.
        set_solid_material(mesh, teal_uniform)
        safety_vest = duplicate_as_outer_work_vest(mesh)
        scale_mesh_about_centre(safety_vest, 1.07, 1.02, 1.08)
        set_workwear_bands(safety_vest, lime_polo, teal_uniform, reflective_band)
    elif mesh.name == 'Ch22_Pants':
        scale_mesh_about_centre(mesh, 1.06, 1.0, 1.05)
        set_trousers_workwear(mesh, teal_trousers, reflective_band, utility_belt)
    elif mesh.name == 'Ch22_Sneakers':
        set_solid_material(mesh, dark_work_shoes)
        apply_chunky_boot_proportions(mesh)
    elif mesh.name == 'Ch22_Body':
        stylize_weighted_head(mesh)
        tint_hand_mesh_as_gloves(mesh, dark_gloves)
    elif mesh.name == 'Ch22_Hair':
        scale_mesh_about_centre(mesh, 1.12, 1.07, 1.12)

bpy.data.objects.remove(donor_armature, do_unlink=True)
if len(armatures(scene)) != 1:
    raise RuntimeError('Expected exactly CANONICAL_RIG in production skin scene')
for mesh in donor_meshes:
    stale = [group.name for group in mesh.vertex_groups if group.name.startswith('mixamorig2:')]
    if stale:
        raise RuntimeError('Unmapped donor groups on {}: {}'.format(mesh.name, stale[:3]))

# Established canonical forward-drift removal only; preserve the gait itself.
forward_path = 'pose.bones["mixamorig:Hips"].location'
forward = next(curve for curve in canonical_action.fcurves if curve.data_path == forward_path and curve.array_index == 2)
first, last = forward.keyframe_points[0], forward.keyframe_points[-1]
span = last.co.x - first.co.x
for point in forward.keyframe_points:
    ratio = 0.0 if span == 0.0 else (point.co.x - first.co.x) / span
    drift = first.co.y + (last.co.y - first.co.y) * ratio
    point.co.y -= drift
    point.handle_left.y -= drift
    point.handle_right.y -= drift
forward.update()

scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.film_transparent = True
scene.render.fps = 30
scene.eevee.taa_render_samples = 64
scene.eevee.use_gtao = True
scene.eevee.gtao_distance = 0.75
scene.eevee.gtao_factor = 1.25
scene.eevee.use_soft_shadows = True
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.world.color = (0.075, 0.095, 0.12)

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
key.data.energy = 440
key.data.size = 5.0
look_at(key, target)
bpy.ops.object.light_add(type='AREA', location=(-4, -2, 4))
fill = bpy.context.object
fill.data.energy = 115
fill.data.size = 4.0
look_at(fill, target)
# A restrained cool rim separates hair, arms and trousers from transparent
# backgrounds without adding a painted outline in the sprite itself.
bpy.ops.object.light_add(type='AREA', location=(-4, 5, 5))
rim = bpy.context.object
rim.data.energy = 85
rim.data.color = (0.55, 0.76, 1.0)
rim.data.size = 3.5
look_at(rim, target)

base_matrix = canonical_armature.matrix_world.copy()
for direction, degrees in DIRECTIONS:
    canonical_armature.matrix_world = Matrix.Rotation(degrees * 3.141592653589793 / 180.0, 4, 'Z') @ base_matrix
    folder = os.path.join(OUT_ROOT, direction)
    os.makedirs(folder, exist_ok=True)
    for index, frame in enumerate(FRAMES):
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(folder, 'frame_{:02d}.png'.format(index))
        bpy.ops.render.render(write_still=True)

if not PREVIEW_ONLY:
    compose_contact_sheet()
scene.frame_start = 1
scene.frame_end = 32
bpy.ops.wm.save_as_mainfile(filepath=SCENE_OUT)
print('WORKER_CLEANER_FEMALE_RENDERED directions={} frames={}'.format([item[0] for item in DIRECTIONS], FRAMES))
