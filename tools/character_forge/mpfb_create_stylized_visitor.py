"""Build the first dressed/stylized City Horizon visitor from the proven MPFB base.

This remains an approval proxy, not a runtime promotion. It reuses the MPFB male
phenotype and FK idle source, freezes that posed body for visual review, then
builds simple matte garment shells directly from the coherent human surface.

Outputs:
  - large SOUTH review render
  - canonical-studio-scale gameplay preview
  - machine-readable report

Walk A/B is intentionally still blocked until this dressed SOUTH gate is approved.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mpfb_create_basic_human as base  # noqa: E402


REVIEW_RESOLUTION = 768
GAMEPLAY_RESOLUTION = 256
GAMEPLAY_ORTHO_SCALE = 5.6  # frozen CH_TYCOON_STUDIO_V1 canonical framing

STYLE = {
    "headXYScale": 1.08,
    "headZScale": 1.045,
    "shirt": (0.085, 0.36, 0.22, 1.0),
    "pants": (0.055, 0.14, 0.29, 1.0),
    "shoes": (0.085, 0.065, 0.050, 1.0),
    "hair": (0.055, 0.025, 0.012, 1.0),
    "skin": (0.56, 0.33, 0.20, 1.0),
}


def make_matte_material(name: str, rgba, roughness: float = 0.94):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = tuple(rgba)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = tuple(rgba)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def freeze_evaluated_body(human: bpy.types.Object) -> bpy.types.Object:
    """Freeze the posed MPFB mesh into one deterministic review-only surface."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = human.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(
        evaluated,
        preserve_all_data_layers=True,
        depsgraph=depsgraph,
    )
    body = bpy.data.objects.new("CH_Visitor_Male_StylizedBody", mesh)
    bpy.context.scene.collection.objects.link(body)
    body.matrix_world = human.matrix_world.copy()
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    return body


def body_metrics(obj: bpy.types.Object):
    coords = [vertex.co.copy() for vertex in obj.data.vertices]
    if not coords:
        raise RuntimeError("Stylized visitor body has no vertices")
    min_x = min(v.x for v in coords)
    max_x = max(v.x for v in coords)
    min_y = min(v.y for v in coords)
    max_y = max(v.y for v in coords)
    min_z = min(v.z for v in coords)
    max_z = max(v.z for v in coords)
    height = max(max_z - min_z, 1e-6)
    center = Vector(((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, (min_z + max_z) * 0.5))
    return {
        "minX": min_x,
        "maxX": max_x,
        "minY": min_y,
        "maxY": max_y,
        "minZ": min_z,
        "maxZ": max_z,
        "height": height,
        "center": center,
    }


def stylize_head(body: bpy.types.Object) -> None:
    """Slightly enlarge the head with a soft neck-to-head blend for sprite readability."""
    metrics = body_metrics(body)
    z0 = metrics["minZ"] + metrics["height"] * 0.815
    z1 = metrics["minZ"] + metrics["height"] * 0.875
    head_vertices = [v for v in body.data.vertices if v.co.z >= z0]
    if not head_vertices:
        return

    center = sum((v.co for v in head_vertices), Vector()) / len(head_vertices)
    for vertex in head_vertices:
        t = max(0.0, min(1.0, (vertex.co.z - z0) / max(z1 - z0, 1e-6)))
        # cubic smoothstep avoids a visible scale seam around the neck.
        w = t * t * (3.0 - 2.0 * t)
        sx = 1.0 + (STYLE["headXYScale"] - 1.0) * w
        sz = 1.0 + (STYLE["headZScale"] - 1.0) * w
        vertex.co.x = center.x + (vertex.co.x - center.x) * sx
        vertex.co.y = center.y + (vertex.co.y - center.y) * sx
        vertex.co.z = center.z + (vertex.co.z - center.z) * sz
    body.data.update()


def face_center(mesh: bpy.types.Mesh, polygon: bpy.types.MeshPolygon) -> Vector:
    return sum((mesh.vertices[i].co for i in polygon.vertices), Vector()) / len(polygon.vertices)


def create_surface_shell(
    source: bpy.types.Object,
    name: str,
    predicate,
    material: bpy.types.Material,
    thickness: float,
) -> bpy.types.Object:
    """Create a compact static garment/hair shell from selected posed-body faces."""
    mesh = source.data
    chosen = []
    used = set()
    for polygon in mesh.polygons:
        center = face_center(mesh, polygon)
        if predicate(center):
            chosen.append(tuple(polygon.vertices))
            used.update(polygon.vertices)

    if not chosen:
        raise RuntimeError(f"No source faces selected for {name}")

    old_to_new = {old: new for new, old in enumerate(sorted(used))}
    verts = [mesh.vertices[old].co.copy() for old in sorted(used)]
    faces = [tuple(old_to_new[i] for i in face) for face in chosen]

    shell_mesh = bpy.data.meshes.new(f"{name}Mesh")
    shell_mesh.from_pydata(verts, [], faces)
    shell_mesh.update()
    shell = bpy.data.objects.new(name, shell_mesh)
    bpy.context.scene.collection.objects.link(shell)
    shell.matrix_world = source.matrix_world.copy()
    shell.data.materials.append(material)
    for polygon in shell.data.polygons:
        polygon.use_smooth = True

    solidify = shell.modifiers.new("CHGarmentThickness", type="SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = 1.0
    solidify.use_rim = True
    return shell


def build_visual_layers(body: bpy.types.Object):
    metrics = body_metrics(body)
    zmin = metrics["minZ"]
    height = metrics["height"]
    center_x = metrics["center"].x

    def zf(p: Vector) -> float:
        return (p.z - zmin) / height

    mats = {
        "skin": make_matte_material("CHVisitorSkin", STYLE["skin"], 0.91),
        "shirt": make_matte_material("CHVisitorShirt", STYLE["shirt"], 0.96),
        "pants": make_matte_material("CHVisitorPants", STYLE["pants"], 0.97),
        "shoes": make_matte_material("CHVisitorShoes", STYLE["shoes"], 0.98),
        "hair": make_matte_material("CHVisitorHair", STYLE["hair"], 0.99),
    }

    body.data.materials.clear()
    body.data.materials.append(mats["skin"])

    shirt = create_surface_shell(
        body,
        "CH_Visitor_TShirt",
        lambda p: 0.49 <= zf(p) <= 0.79 and abs(p.x - center_x) <= height * 0.37,
        mats["shirt"],
        height * 0.010,
    )
    pants = create_surface_shell(
        body,
        "CH_Visitor_Jeans",
        lambda p: 0.14 <= zf(p) <= 0.525 and abs(p.x - center_x) <= height * 0.19,
        mats["pants"],
        height * 0.011,
    )
    shoes = create_surface_shell(
        body,
        "CH_Visitor_Shoes",
        lambda p: zf(p) <= 0.105,
        mats["shoes"],
        height * 0.016,
    )
    hair = create_surface_shell(
        body,
        "CH_Visitor_ShortHair",
        lambda p: zf(p) >= 0.885 and abs(p.x - center_x) <= height * 0.125,
        mats["hair"],
        height * 0.013,
    )
    return [shirt, pants, shoes, hair]


def configure_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.resolution_percentage = 100


def render(scene: bpy.types.Scene, camera: bpy.types.Object, output: Path, resolution: int, ortho_scale: float) -> None:
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    camera.data.ortho_scale = ortho_scale
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    output_value = argv[0] if argv else os.environ.get(
        "CH_AGENT_OUTPUT_DIR",
        "out/ch_blender_agent/character.forge.mpfb.visitor.manual",
    )
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extension_module = base.find_mpfb_extension_module()
    base.ensure_mpfb_enabled(extension_module)
    base.clear_scene_objects()

    HumanService = base.import_symbol(extension_module, "services.humanservice", "HumanService")
    TargetService = base.import_symbol(extension_module, "services.targetservice", "TargetService")
    RigService = base.import_symbol(extension_module, "services.rigservice", "RigService")
    HumanObjectProperties = base.import_symbol(
        extension_module, "entities.objectproperties", "HumanObjectProperties"
    )

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_MPFB_Source"
    for key, value in base.MALE_PHENOTYPE.items():
        HumanObjectProperties.set_value(key, value, entity_reference=human)
    TargetService.reapply_macro_details(human)
    bpy.context.view_layer.update()

    phenotype = {
        key: HumanObjectProperties.get_value(key, entity_reference=human)
        for key in base.MALE_PHENOTYPE
    }

    rig = HumanService.add_builtin_rig(human, "default_no_toes")
    base.apply_idle_pose(RigService, rig, base.make_neutral_idle_pose())

    body = freeze_evaluated_body(human)
    stylize_head(body)
    visual_layers = build_visual_layers(body)

    human.hide_render = True
    rig.hide_render = True
    human.hide_set(True)
    rig.hide_set(True)

    camera = base.setup_camera_and_light(body)
    scene = bpy.context.scene
    configure_render(scene)

    review_path = output_dir / "visitor_male_stylized_south_review.png"
    gameplay_path = output_dir / "visitor_male_stylized_south_gameplay.png"
    render(scene, camera, review_path, REVIEW_RESOLUTION, base.CAMERA_CONTRACT["reviewOrthoScale"])
    render(scene, camera, gameplay_path, GAMEPLAY_RESOLUTION, GAMEPLAY_ORTHO_SCALE)

    metrics = body_metrics(body)
    report = {
        "contract": "CH_CHARACTER_FORGE_STYLIZED_VISITOR_V1",
        "status": "ok",
        "blender": bpy.app.version_string,
        "mpfbExtension": extension_module,
        "phenotypeApplied": phenotype,
        "rigSource": "default_no_toes",
        "pose": "neutral_idle_fk_v1",
        "direction": "south",
        "visualGate": "dressed_south_idle_only",
        "runtimePromotion": False,
        "walkBlockedUntilApproval": True,
        "style": STYLE,
        "bodyHeight": metrics["height"],
        "visualLayers": [obj.name for obj in visual_layers],
        "review": {
            "resolution": [REVIEW_RESOLUTION, REVIEW_RESOLUTION],
            "orthoScale": base.CAMERA_CONTRACT["reviewOrthoScale"],
            "file": review_path.name,
        },
        "gameplayPreview": {
            "resolution": [GAMEPLAY_RESOLUTION, GAMEPLAY_RESOLUTION],
            "orthoScale": GAMEPLAY_ORTHO_SCALE,
            "studioReference": "CH_TYCOON_STUDIO_V1",
            "file": gameplay_path.name,
        },
        "note": "Garments are static approval shells from the evaluated idle body; rigged clothing comes after SOUTH visual approval.",
    }
    report_path = output_dir / "visitor_male_stylized_south.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
