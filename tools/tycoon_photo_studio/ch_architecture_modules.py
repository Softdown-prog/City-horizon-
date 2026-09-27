"""Reusable architectural vocabulary for CH Blender / Tycoon Photo Studio.

The goal of this module is to make visual quality cumulative across assets.
New buildings should compose stable, reusable modules instead of re-implementing
small roof/window/trim/garden details in one-off scripts.

This file intentionally owns *geometry vocabulary*, not camera, studio, render,
quality-gate or runtime policy. Callers inject their existing ``box``/``sphere``
helpers and materials so the module library stays compatible with guarded asset
builders.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence


BoxFn = Callable[..., object]
SphereFn = Callable[..., object]

VOCABULARY_CONTRACT = "CH_ARCHITECTURE_VOCABULARY_V1"

MODULE_CATALOG = {
    "roof_form": {
        "phase": 1,
        "purpose": "Reusable roof massing, eaves and ridge silhouette.",
    },
    "roof_surface": {
        "phase": 1,
        "purpose": "Shingle courses, staggered joints and ridge-cap detail.",
    },
    "windows": {
        "phase": 1,
        "purpose": "Readable casing, mullions, sills and warm-glass framing.",
    },
    "entrances": {
        "phase": 1,
        "purpose": "Door panels, porch details, columns and entry lighting.",
    },
    "architectural_trim": {
        "phase": 1,
        "purpose": "Fascia, gutters, corner boards, cornice and edge hierarchy.",
    },
    "foundation": {
        "phase": 2,
        "purpose": "Foundation courses, plinths, steps and ground-contact read.",
    },
    "ornamental_vegetation": {
        "phase": 3,
        "purpose": "Compact shrubs, mulch beds and low flower clusters.",
    },
    "emissive_lighting": {
        "phase": 2,
        "purpose": "Reusable warm emissive treatment for windows and lamps.",
    },
    "wall_surfaces": {
        "phase": 2,
        "purpose": "Siding courses and low-noise facade surface articulation.",
    },
    "small_arch_props": {
        "phase": 3,
        "purpose": "Chimneys, downspouts, vents, small signs and other accents.",
    },
}


@dataclass(frozen=True)
class ModuleUse:
    module_id: str
    variant: str
    detail_level: str = "medium"

    def as_metadata(self) -> dict:
        if self.module_id not in MODULE_CATALOG:
            raise ValueError(f"Unknown CH architecture module: {self.module_id}")
        return {
            "contract": VOCABULARY_CONTRACT,
            "module": self.module_id,
            "variant": self.variant,
            "detailLevel": self.detail_level,
        }


def _material(materials: Mapping[str, object], key: str):
    try:
        return materials[key]
    except KeyError as exc:
        raise RuntimeError(f"CH_ARCH_MATERIAL_MISSING: {key}") from exc


def add_roof_surface_detail(
    *,
    box: BoxFn,
    root,
    materials: Mapping[str, object],
    width: float,
    depth: float,
    eave_z: float,
    ridge_z: float,
    rows: int = 9,
    columns: int = 14,
    edge_material: str = "roofEdge",
    name_prefix: str = "Roof",
) -> None:
    """Add staggered shingle joints and chunky ridge caps to a gable roof."""
    rows = max(4, int(rows))
    columns = max(6, int(columns))
    edge = _material(materials, edge_material)
    usable = float(width) - 0.22
    spacing = usable / columns

    for side, sign in (("S", -1), ("N", 1)):
        for row in range(rows):
            t0 = row / rows
            t1 = (row + 1) / rows
            mid = (t0 + t1) * 0.5
            y = sign * (depth / 2.0) * (1.0 - mid)
            z = eave_z + (ridge_z - eave_z) * mid + 0.028
            offset = spacing * 0.5 if row % 2 else 0.0
            for col in range(columns - 1):
                x = -usable / 2.0 + spacing * (col + 1) + offset
                if x > usable / 2.0:
                    continue
                box(
                    f"{name_prefix}Joint_{side}_{row}_{col}",
                    (x, y, z),
                    (0.022, max(0.12, depth / rows * 0.70), 0.018),
                    edge,
                    root,
                    0.003,
                )

    cap_count = max(8, columns)
    cap_w = (width - 0.12) / cap_count
    for index in range(cap_count):
        x = -width / 2.0 + 0.06 + cap_w * (index + 0.5)
        box(
            f"{name_prefix}RidgeCap_{index}",
            (x, 0, ridge_z + 0.072),
            (cap_w * 0.92, 0.18, 0.13),
            edge,
            root,
            0.018,
        )


def add_eave_and_corner_trim(
    *,
    box: BoxFn,
    root,
    materials: Mapping[str, object],
    body_width: float,
    body_depth: float,
    wall_height: float,
    wall_base_z: float,
    roof_width: float,
    roof_depth: float,
    eave_z: float,
    trim_material: str = "trim",
    edge_material: str = "roofEdge",
) -> None:
    """Add fascia, gutters and oversized corner boards for gameplay readability."""
    trim = _material(materials, trim_material)
    edge = _material(materials, edge_material)
    for sign, label in ((-1, "South"), (1, "North")):
        box(
            f"{label}CreamFasciaV2",
            (0, sign * (roof_depth / 2 + 0.035), eave_z - 0.10),
            (roof_width + 0.06, 0.13, 0.18),
            trim,
            root,
            0.018,
        )
        box(
            f"{label}GutterV2",
            (0, sign * (roof_depth / 2 + 0.115), eave_z - 0.04),
            (roof_width + 0.10, 0.085, 0.085),
            edge,
            root,
            0.018,
        )

    center_z = wall_base_z + wall_height * 0.5
    for x in (-body_width / 2 - 0.035, body_width / 2 + 0.035):
        for y in (-body_depth / 2 - 0.035, body_depth / 2 + 0.035):
            box(
                f"CornerTrim_{'E' if x > 0 else 'W'}_{'N' if y > 0 else 'S'}",
                (x, y, center_z),
                (0.14, 0.14, wall_height + 0.08),
                trim,
                root,
                0.014,
            )


def add_window_casing_south(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, z: float, width: float, height: float,
    trim_material: str = "trim",
) -> None:
    trim = _material(materials, trim_material)
    box(f"{name}Header", (x, y, z + height / 2 + 0.16),
        (width + 0.34, 0.09, 0.11), trim, root, 0.012)
    box(f"{name}Left", (x - width / 2 - 0.12, y, z),
        (0.11, 0.09, height + 0.28), trim, root, 0.012)
    box(f"{name}Right", (x + width / 2 + 0.12, y, z),
        (0.11, 0.09, height + 0.28), trim, root, 0.012)


def add_window_casing_east(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, z: float, width: float, height: float,
    trim_material: str = "trim",
) -> None:
    trim = _material(materials, trim_material)
    box(f"{name}Header", (x, y, z + height / 2 + 0.16),
        (0.09, width + 0.34, 0.11), trim, root, 0.012)


def add_door_panels(
    *, box: BoxFn, root, materials: Mapping[str, object],
    center_x: float, front_y: float, base_z: float, width: float, height: float,
    frame_material: str = "frame", door_material: str = "door",
    name_prefix: str = "Door",
) -> None:
    frame = _material(materials, frame_material)
    door = _material(materials, door_material)
    panel_w = width * 0.58
    panel_h = height * 0.25
    for row, z in enumerate((base_z + height * 0.30, base_z + height * 0.67)):
        box(f"{name_prefix}Panel_{row}", (center_x, front_y - 0.184, z),
            (panel_w, 0.026, panel_h), frame, root, 0.018)
        box(f"{name_prefix}PanelInset_{row}", (center_x, front_y - 0.202, z),
            (panel_w * 0.78, 0.018, panel_h * 0.72), door, root, 0.010)


def add_wall_lamp(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, z: float,
    frame_material: str = "frame", glow_material: str = "glass",
) -> None:
    box(f"{name}Mount", (x, y, z), (0.18, 0.12, 0.22),
        _material(materials, frame_material), root, 0.018)
    box(f"{name}Glow", (x, y - 0.07, z), (0.105, 0.04, 0.13),
        _material(materials, glow_material), root, 0.010)


def add_column_cap_and_plinth(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, eave_z: float, trim_material: str = "trim",
) -> None:
    trim = _material(materials, trim_material)
    box(f"{name}Capital", (x, y, eave_z - 0.11), (0.30, 0.30, 0.14),
        trim, root, 0.020)
    box(f"{name}Plinth", (x, y, 0.54), (0.28, 0.28, 0.16),
        trim, root, 0.018)


def add_foundation_courses(
    *, box: BoxFn, root, materials: Mapping[str, object],
    width: float, depth: float, height: float, courses: int = 2,
    trim_material: str = "trim",
) -> None:
    trim = _material(materials, trim_material)
    for index in range(1, max(1, courses) + 1):
        z = height * index / (courses + 1)
        box(f"FoundationCourseSouth_{index}", (0, -depth / 2 - 0.025, z),
            (width - 0.08, 0.035, 0.025), trim, root, 0.004)
        box(f"FoundationCourseEast_{index}", (width / 2 + 0.025, 0, z),
            (0.035, depth - 0.08, 0.025), trim, root, 0.004)


def add_shrub_cluster(
    *, sphere: SphereFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, radius: float,
    dark_material: str = "green", light_material: str = "greenLight",
) -> None:
    offsets = ((-0.14, -0.03), (0.13, -0.05), (-0.05, 0.11), (0.10, 0.10))
    for index, (dx, dy) in enumerate(offsets):
        sphere(
            f"{name}Lobe_{index}",
            (x + dx, y + dy, radius * 1.10),
            radius * 0.46,
            _material(materials, light_material if index % 3 == 0 else dark_material),
            root,
            (1.0, 0.88, 0.82),
            12,
            7,
        )


def add_mulch_bed(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, width: float = 1.20, depth: float = 0.58,
    material: str = "door",
) -> None:
    box(name, (x, y + 0.02, 0.055), (width, depth, 0.055),
        _material(materials, material), root, 0.018)


def add_siding_courses(
    *, box: BoxFn, root, materials: Mapping[str, object],
    body_width: float, body_depth: float, wall_height: float, wall_base_z: float,
    rows: int = 7, trim_material: str = "trim", name_prefix: str = "Siding",
) -> None:
    """Reusable low-noise horizontal facade articulation for all four walls."""
    trim = _material(materials, trim_material)
    for index in range(1, max(2, rows)):
        z = wall_base_z + wall_height * index / rows
        for name, loc, dims in (
            (f"{name_prefix}S{index}", (0, -body_depth / 2 - 0.022, z), (body_width - .1, .035, .035)),
            (f"{name_prefix}N{index}", (0, body_depth / 2 + 0.022, z), (body_width - .1, .035, .035)),
            (f"{name_prefix}E{index}", (body_width / 2 + 0.022, 0, z), (.035, body_depth - .1, .035)),
            (f"{name_prefix}W{index}", (-body_width / 2 - 0.022, 0, z), (.035, body_depth - .1, .035)),
        ):
            box(name, loc, dims, trim, root, 0.006)


def configure_warm_emission(material, rgba: Sequence[float], strength: float = 0.55) -> None:
    """Standard warm emissive treatment used by windows and compact lamps."""
    if not getattr(material, "use_nodes", False):
        return
    node = material.node_tree.nodes.get("Principled BSDF")
    if node is None:
        return
    key = "Emission Color" if "Emission Color" in node.inputs else "Emission"
    if key in node.inputs:
        node.inputs[key].default_value = tuple(rgba)
    if "Emission Strength" in node.inputs:
        node.inputs["Emission Strength"].default_value = float(strength)


def add_downspout(
    *, box: BoxFn, root, materials: Mapping[str, object], name: str,
    x: float, y: float, bottom_z: float, top_z: float,
    edge_material: str = "roofEdge",
) -> None:
    """Small architectural prop; intended for corners, not as a mandatory detail."""
    height = max(0.05, top_z - bottom_z)
    box(name, (x, y, bottom_z + height / 2), (0.075, 0.075, height),
        _material(materials, edge_material), root, 0.012)


def vocabulary_metadata(uses: Iterable[ModuleUse]) -> dict:
    items = [item.as_metadata() for item in uses]
    return {
        "contract": VOCABULARY_CONTRACT,
        "modules": items,
        "catalogSize": len(MODULE_CATALOG),
    }
