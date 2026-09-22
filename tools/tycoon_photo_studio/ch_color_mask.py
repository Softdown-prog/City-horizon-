"""CH_COLOR_MASK_V1 helpers for City Horizon Blender authoring.

Blender-side only. R/G/B are semantic recolor channels; alpha is reserved for
object coverage. This keeps mask PNGs inspectable and aligned with the normal
transparent sprite without overloading alpha as a fourth tint channel.
"""

from __future__ import annotations

from contextlib import contextmanager

import bpy

CONTRACT = "CH_COLOR_MASK_V1"
ROLE_PROPERTY = "ch_color_mask_role"
CHANNEL_COLORS = {
    "R": (1.0, 0.0, 0.0, 1.0),
    "G": (0.0, 1.0, 0.0, 1.0),
    "B": (0.0, 0.0, 1.0, 1.0),
}
UNMASKED_COLOR = (0.0, 0.0, 0.0, 1.0)


def normalize_spec(asset: dict) -> dict | None:
    """Validate and normalize an optional asset['colorMask'] declaration."""
    raw = asset.get("colorMask")
    if raw is None or raw is False:
        return None
    if not isinstance(raw, dict):
        raise RuntimeError("colorMask must be an object when enabled")
    if raw.get("enabled", True) is False:
        return None
    if raw.get("contract") != CONTRACT:
        raise RuntimeError(
            f"colorMask.contract must be {CONTRACT}, got {raw.get('contract')!r}"
        )

    raw_channels = raw.get("channels")
    if not isinstance(raw_channels, dict) or not raw_channels:
        raise RuntimeError("CH_COLOR_MASK_V1 requires a non-empty channels object")

    channels = {}
    roles = set()
    for key, role in raw_channels.items():
        channel = str(key).upper()
        if channel not in CHANNEL_COLORS:
            raise RuntimeError(
                f"CH_COLOR_MASK_V1 supports R/G/B recolor channels only; got {channel!r}"
            )
        if not isinstance(role, str) or not role.strip():
            raise RuntimeError(f"Mask channel {channel} must name a semantic role")
        role = role.strip()
        if role in roles:
            raise RuntimeError(f"Mask role {role!r} is assigned to more than one channel")
        roles.add(role)
        channels[channel] = role

    alpha_policy = raw.get("alpha", "coverage")
    if alpha_policy != "coverage":
        raise RuntimeError(
            "CH_COLOR_MASK_V1 reserves alpha for object coverage; "
            "a fourth recolor channel requires a future contract version"
        )

    return {
        "contract": CONTRACT,
        "enabled": True,
        "channels": channels,
        "alpha": "coverage",
        "unmaskedRgb": [0, 0, 0],
        "roleProperty": ROLE_PROPERTY,
    }


def tag_material(material, role: str) -> None:
    material[ROLE_PROPERTY] = str(role)


def tag_object(obj, role: str) -> None:
    obj[ROLE_PROPERTY] = str(role)


def tag_declared_materials(asset: dict) -> None:
    """Apply maskRole from TYCOON_ASSET_SOURCE_V1 material declarations."""
    for key, material_spec in asset.get("materials", {}).items():
        role = material_spec.get("maskRole")
        if not role:
            continue
        material_name = material_spec.get("name", key)
        material = bpy.data.materials.get(material_name)
        if material is None:
            raise RuntimeError(
                f"Mask role {role!r} references material {material_name!r}, "
                "but Blender did not create it"
            )
        tag_material(material, role)


def tag_imported_objects(objects, role: str | None) -> None:
    """Optional coarse override for blend/fbx/glb import parts."""
    if not role:
        return
    for obj in objects:
        tag_object(obj, role)


def _role_channel_map(spec: dict) -> dict[str, str]:
    return {role: channel for channel, role in spec["channels"].items()}


def assignment_summary(authored, spec: dict) -> dict:
    """Validate role names and ensure every declared role is actually used."""
    role_to_channel = _role_channel_map(spec)
    used = set()
    unknown = set()

    for obj in authored:
        object_role = obj.get(ROLE_PROPERTY)
        if object_role:
            if object_role in role_to_channel:
                used.add(object_role)
            else:
                unknown.add(str(object_role))
            continue

        for slot in getattr(obj, "material_slots", ()):
            material = slot.material
            if material is None:
                continue
            role = material.get(ROLE_PROPERTY)
            if not role:
                continue
            if role in role_to_channel:
                used.add(role)
            else:
                unknown.add(str(role))

    if unknown:
        raise RuntimeError(
            "Mask assignments use roles not declared in colorMask.channels: "
            + ", ".join(sorted(unknown))
        )

    missing = set(role_to_channel) - used
    if missing:
        raise RuntimeError(
            "Declared color mask roles are not assigned to any rendered surface: "
            + ", ".join(sorted(missing))
        )

    return {
        "declaredRoles": sorted(role_to_channel),
        "usedRoles": sorted(used),
        "channels": dict(spec["channels"]),
    }


def _emission_material(name: str, rgba):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = rgba
    emission.inputs["Strength"].default_value = 1.0
    tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    material.diffuse_color = rgba
    return material


@contextmanager
def _mask_scene_override(scene, authored, ground, spec: dict):
    """Temporarily replace authored material slots with packed mask emissions."""
    role_to_channel = _role_channel_map(spec)
    mask_materials = {
        channel: _emission_material(f"CHMask_{channel}", CHANNEL_COLORS[channel])
        for channel in CHANNEL_COLORS
    }
    unmasked = _emission_material("CHMask_Unmasked", UNMASKED_COLOR)

    original_engine = scene.render.engine
    original_transparent = scene.render.film_transparent
    original_view_transform = scene.view_settings.view_transform
    original_look = scene.view_settings.look
    original_exposure = scene.view_settings.exposure
    original_gamma = scene.view_settings.gamma
    ground_hidden = ground.hide_render

    slot_state = []
    visibility_state = []

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.film_transparent = True
        try:
            scene.view_settings.view_transform = "Standard"
        except Exception:
            pass
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        ground.hide_render = True
        if hasattr(ground, "is_shadow_catcher"):
            ground.is_shadow_catcher = False

        for obj in authored:
            visibility_state.append(
                (obj, obj.hide_render, getattr(obj, "visible_camera", None))
            )
            obj.hide_render = False
            if hasattr(obj, "visible_camera"):
                obj.visible_camera = True

            object_role = obj.get(ROLE_PROPERTY)
            original_slots = [slot.material for slot in obj.material_slots]
            slot_state.append((obj, original_slots, len(obj.data.materials)))

            if not original_slots:
                role = str(object_role) if object_role else None
                channel = role_to_channel.get(role)
                obj.data.materials.append(mask_materials[channel] if channel else unmasked)
                continue

            for index, original_material in enumerate(original_slots):
                role = object_role
                if not role and original_material is not None:
                    role = original_material.get(ROLE_PROPERTY)
                channel = role_to_channel.get(str(role)) if role else None
                obj.material_slots[index].material = (
                    mask_materials[channel] if channel else unmasked
                )

        bpy.context.view_layer.update()
        yield
    finally:
        for obj, original_slots, original_count in slot_state:
            while len(obj.data.materials) > original_count:
                obj.data.materials.pop(index=len(obj.data.materials) - 1)
            for index, material in enumerate(original_slots):
                if index < len(obj.material_slots):
                    obj.material_slots[index].material = material

        for obj, hide_render, visible_camera in visibility_state:
            obj.hide_render = hide_render
            if visible_camera is not None and hasattr(obj, "visible_camera"):
                obj.visible_camera = visible_camera

        ground.hide_render = ground_hidden
        scene.render.engine = original_engine
        scene.render.film_transparent = original_transparent
        try:
            scene.view_settings.view_transform = original_view_transform
        except Exception:
            pass
        try:
            scene.view_settings.look = original_look
        except Exception:
            pass
        scene.view_settings.exposure = original_exposure
        scene.view_settings.gamma = original_gamma
        bpy.context.view_layer.update()


def render_mask_pass(scene, authored, ground, path: str, spec: dict) -> None:
    """Render one packed RGB mask using the current AssetRoot direction."""
    with _mask_scene_override(scene, authored, ground, spec):
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)


def metadata(spec: dict, assignment: dict) -> dict:
    return {
        **spec,
        "assignment": assignment,
        "sourceFormat": "PNG_RGBA",
        "channelEncoding": "primary_emission",
        "alphaMeaning": "object_coverage",
        "runtimeStatus": "authoring_output_ready_runtime_tint_not_implemented_here",
    }
