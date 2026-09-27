"""High-detail CH Blender pass for residential_suburban_cottage_3x3_01.

This keeps the approved pilot massing and adds the richer game-readable detail
seen in the latest visual target. The cottage is also the first calibration
asset for CH_ARCHITECTURE_VOCABULARY_V1: shared detail is delegated to
``ch_architecture_modules`` while camera/studio/gate ownership remains in the
guarded builder.

The guarded workflow remains unchanged: preflight -> SOUTH proxy -> approval ->
final four directions.
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_suburban_cottage_guarded as base  # noqa: E402
import ch_architecture_modules as arch  # noqa: E402


def _box(name, loc, dims, mat, root, bevel=0.02):
    return base.box(name, loc, dims, mat, root, bevel)


def _sphere(name, loc, radius, mat, root, scale=(1, 1, 1), seg=14, rings=8):
    return base.sphere(name, loc, radius, mat, root, scale, seg, rings)


def _roof_shingles(root, mats, r):
    roof = r["roof"]
    arch.add_roof_surface_detail(
        box=_box,
        root=root,
        materials=mats,
        width=float(roof["width"]),
        depth=float(roof["depth"]),
        eave_z=float(roof["eaveZ"]),
        ridge_z=float(roof["ridgeZ"]),
        rows=max(8, int(roof.get("tileRows", 7)) + 2),
        columns=14,
        edge_material="roofEdge",
        name_prefix="Roof",
    )


def _fascia_gutters_and_corners(root, mats, r):
    mass = r["mass"]
    roof = r["roof"]
    arch.add_eave_and_corner_trim(
        box=_box,
        root=root,
        materials=mats,
        body_width=float(mass["bodyWidth"]),
        body_depth=float(mass["bodyDepth"]),
        wall_height=float(mass["wallHeight"]),
        wall_base_z=float(mass["wallBaseZ"]),
        roof_width=float(roof["width"]),
        roof_depth=float(roof["depth"]),
        eave_z=float(roof["eaveZ"]),
    )


def _window_casing_details(root, mats, r):
    mass = r["mass"]
    win = r["windows"]
    body_width = float(mass["bodyWidth"])
    body_depth = float(mass["bodyDepth"])
    front = -body_depth / 2.0
    z = float(win["frontCenterZ"])
    width = float(win["frontWidth"])
    height = float(win["frontHeight"])

    for index, xv in enumerate(win["frontCentersX"]):
        arch.add_window_casing_south(
            box=_box,
            root=root,
            materials=mats,
            name=f"FrontWindowCasingV2_{index}",
            x=float(xv),
            y=front - 0.142,
            z=z,
            width=width,
            height=height,
        )

    arch.add_window_casing_east(
        box=_box,
        root=root,
        materials=mats,
        name="EastWindowCasingV2",
        x=body_width / 2.0 + 0.142,
        y=float(win["sideCenterY"]),
        z=float(win["sideCenterZ"]),
        width=float(win["sideWidth"]),
        height=float(win["sideHeight"]),
    )


def _door_and_porch_details(root, mats, r):
    mass = r["mass"]
    ent = r["entry"]
    body_depth = float(mass["bodyDepth"])
    base_z = float(mass["wallBaseZ"])
    front = -body_depth / 2.0
    center_x = float(ent["centerX"])
    door_width = float(ent["doorWidth"])
    door_height = float(ent["doorHeight"])

    arch.add_door_panels(
        box=_box,
        root=root,
        materials=mats,
        center_x=center_x,
        front_y=front,
        base_z=base_z,
        width=door_width,
        height=door_height,
    )

    arch.add_wall_lamp(
        box=_box,
        root=root,
        materials=mats,
        name="PorchLamp",
        x=center_x - door_width * 0.72,
        y=front - 0.19,
        z=base_z + door_height * 0.78,
    )

    portico_depth = float(ent["porticoDepth"])
    portico_y = front - portico_depth * 0.47
    column_y = portico_y - portico_depth * 0.30
    spacing = float(ent["columnSpacing"])
    for label, x in (("L", center_x - spacing / 2), ("R", center_x + spacing / 2)):
        arch.add_column_cap_and_plinth(
            box=_box,
            root=root,
            materials=mats,
            name=f"EntryColumn{label}",
            x=x,
            y=column_y,
            eave_z=float(ent["porticoEaveZ"]),
        )


def _foundation_courses(root, mats, r):
    mass = r["mass"]
    arch.add_foundation_courses(
        box=_box,
        root=root,
        materials=mats,
        width=float(mass["foundationWidth"]),
        depth=float(mass["foundationDepth"]),
        height=float(mass["foundationHeight"]),
        courses=2,
    )


def _garden_detail(root, mats, r):
    """Keep the already-approved cottage-specific shrub arrangement intact."""
    land = r["landscaping"]
    radius = float(land["shrubRadius"])
    all_shrubs = list(land["frontShrubs"]) + list(land["sideShrubs"])
    offsets = ((-0.14, -0.03), (0.13, -0.05), (-0.05, 0.11), (0.10, 0.10))
    for i, (xv, yv) in enumerate(all_shrubs):
        x, y = float(xv), float(yv)
        for j, (dx, dy) in enumerate(offsets):
            _sphere(
                f"ShrubLobe_{i}_{j}",
                (x + dx, y + dy, radius * 1.10),
                radius * 0.46,
                mats["greenLight" if (i + j) % 3 == 0 else "green"],
                root,
                (1.0, 0.88, 0.82),
                12,
                7,
            )

    for i, (xv, yv) in enumerate(land["flowerBeds"]):
        x, y = float(xv), float(yv)
        arch.add_mulch_bed(
            box=_box,
            root=root,
            materials=mats,
            name=f"MulchStrip_{i}",
            x=x,
            y=y,
            width=1.20,
            depth=0.58,
            material="door",
        )


def apply_detail_pass(root, mats, r):
    _roof_shingles(root, mats, r)
    _fascia_gutters_and_corners(root, mats, r)
    _window_casing_details(root, mats, r)
    _door_and_porch_details(root, mats, r)
    _foundation_courses(root, mats, r)
    _garden_detail(root, mats, r)

    root["detailPass"] = "residential_cottage_detail_v2"
    root["detailTarget"] = "latest_user_approved_generated_reference"
    root["architectureVocabularyContract"] = arch.VOCABULARY_CONTRACT
    root["architectureVocabularyCatalogSize"] = len(arch.MODULE_CATALOG)
    root["architectureModulesActive"] = ",".join((
        "roof_form",
        "roof_surface",
        "windows",
        "entrances",
        "architectural_trim",
        "foundation",
        "ornamental_vegetation",
        "emissive_lighting",
        "wall_surfaces",
        "small_arch_props",
    ))


_original_build_house = base.build_house


def _detailed_build_house(root, mats, r):
    _original_build_house(root, mats, r)
    apply_detail_pass(root, mats, r)


base.build_house = _detailed_build_house


if __name__ == "__main__":
    base.main()
