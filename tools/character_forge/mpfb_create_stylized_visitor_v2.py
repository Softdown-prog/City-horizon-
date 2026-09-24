"""Refined dressed SOUTH approval proxy for the MPFB City Horizon visitor.

V2 keeps the exact V1 human source/camera/material pipeline but tightens the
surface-shell masks so skin remains visible on forearms/hands, the shirt reads
as a short-sleeve T-shirt, jeans reach the ankle, and shoes stay low-profile.
"""
from __future__ import annotations

import sys
from pathlib import Path

from mathutils import Vector

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mpfb_create_stylized_visitor as v1  # noqa: E402


v1.STYLE["garmentMaskRevision"] = "v2_short_sleeve_low_shoe"


def build_visual_layers_v2(body):
    metrics = v1.body_metrics(body)
    zmin = metrics["minZ"]
    height = metrics["height"]
    center_x = metrics["center"].x

    def zf(p: Vector) -> float:
        return (p.z - zmin) / height

    def shirt_mask(p: Vector) -> bool:
        z = zf(p)
        x = abs(p.x - center_x) / height

        # Main torso shell. Extend high enough to cover the shoulders but carve
        # a compact central neck opening instead of producing an off-shoulder cut.
        torso = 0.485 <= z <= 0.835 and x <= 0.175
        neck_opening = z >= 0.795 and x <= 0.060

        # Only the upper arm is clothed. Forearms and hands must stay skin.
        sleeve = 0.675 <= z <= 0.815 and 0.145 <= x <= 0.300
        return (torso and not neck_opening) or sleeve

    def pants_mask(p: Vector) -> bool:
        z = zf(p)
        x = abs(p.x - center_x) / height
        return 0.095 <= z <= 0.535 and x <= 0.165

    mats = {
        "skin": v1.make_matte_material("CHVisitorSkin", v1.STYLE["skin"], 0.91),
        "shirt": v1.make_matte_material("CHVisitorShirt", v1.STYLE["shirt"], 0.96),
        "pants": v1.make_matte_material("CHVisitorPants", v1.STYLE["pants"], 0.97),
        "shoes": v1.make_matte_material("CHVisitorShoes", v1.STYLE["shoes"], 0.98),
        "hair": v1.make_matte_material("CHVisitorHair", v1.STYLE["hair"], 0.99),
    }

    body.data.materials.clear()
    body.data.materials.append(mats["skin"])

    shirt = v1.create_surface_shell(
        body,
        "CH_Visitor_TShirt_V2",
        shirt_mask,
        mats["shirt"],
        height * 0.008,
    )
    pants = v1.create_surface_shell(
        body,
        "CH_Visitor_Jeans_V2",
        pants_mask,
        mats["pants"],
        height * 0.009,
    )
    shoes = v1.create_surface_shell(
        body,
        "CH_Visitor_Shoes_V2",
        lambda p: zf(p) <= 0.060,
        mats["shoes"],
        height * 0.008,
    )
    hair = v1.create_surface_shell(
        body,
        "CH_Visitor_ShortHair_V2",
        lambda p: zf(p) >= 0.872 and abs(p.x - center_x) <= height * 0.130,
        mats["hair"],
        height * 0.010,
    )
    return [shirt, pants, shoes, hair]


v1.build_visual_layers = build_visual_layers_v2


if __name__ == "__main__":
    v1.main()
