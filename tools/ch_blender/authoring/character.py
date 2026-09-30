"""High-level character authoring API for stylized City Horizon actors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import bpy
from mathutils import Vector

from .materials import stylized_material
from .shapes import (
    AuthoringObject,
    create_root,
    curve_tube,
    rounded_box,
    soft_form,
    tapered_segment,
    torus_form,
)


@dataclass
class CharacterAuthoring:
    """Build one physical character under one root and rotate that root for views.

    Recipes should describe semantic parts rather than raw bpy operations. This
    keeps proportion changes centralized and makes turntables genuinely share the
    same physical model.
    """

    name: str
    root: bpy.types.Object = field(init=False)
    parts: dict[str, bpy.types.Object] = field(default_factory=dict, init=False)
    materials: dict[str, bpy.types.Material] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.root = create_root(self.name + "_ROOT")

    def material(self, key: str, color: str, **kwargs) -> bpy.types.Material:
        if key not in self.materials:
            self.materials[key] = stylized_material(f"{self.name}_{key}", color, **kwargs)
        return self.materials[key]

    def register(self, key: str, authored: AuthoringObject) -> bpy.types.Object:
        self.parts[key] = authored.object
        return authored.object

    def soft(self, key: str, location, scale, material, **kwargs) -> bpy.types.Object:
        return self.register(
            key,
            soft_form(f"{self.name}_{key}", location, scale, material, root=self.root, **kwargs),
        )

    def segment(
        self,
        key: str,
        start,
        end,
        radius_start: float,
        radius_end: float,
        material,
        **kwargs,
    ) -> bpy.types.Object:
        return self.register(
            key,
            tapered_segment(
                f"{self.name}_{key}",
                start,
                end,
                radius_start,
                radius_end,
                material,
                root=self.root,
                **kwargs,
            ),
        )

    def box(self, key: str, location, size, material, **kwargs) -> bpy.types.Object:
        return self.register(
            key,
            rounded_box(f"{self.name}_{key}", location, size, material, root=self.root, **kwargs),
        )

    def tube(self, key: str, points, radius: float, material, **kwargs) -> bpy.types.Object:
        return self.register(
            key,
            curve_tube(f"{self.name}_{key}", points, radius, material, root=self.root, **kwargs),
        )

    def ring(self, key: str, location, major_radius: float, minor_radius: float, material, **kwargs) -> bpy.types.Object:
        return self.register(
            key,
            torus_form(
                f"{self.name}_{key}",
                location,
                major_radius,
                minor_radius,
                material,
                root=self.root,
                **kwargs,
            ),
        )

    def hair_lobes(
        self,
        prefix: str,
        lobes: Sequence[dict],
        material,
    ) -> list[bpy.types.Object]:
        """Create a semantic hairstyle from compact soft volumes.

        Each lobe accepts location, scale and optional rotation. Keeping the list
        in one recipe makes it easy to reshape a hairstyle without editing four
        directional copies.
        """
        result = []
        for index, lobe in enumerate(lobes):
            result.append(
                self.soft(
                    f"{prefix}_{index:02d}",
                    lobe["location"],
                    lobe["scale"],
                    material,
                    rotation=lobe.get("rotation", (0.0, 0.0, 0.0)),
                    segments=lobe.get("segments", 24),
                    rings=lobe.get("rings", 16),
                )
            )
        return result

    def set_yaw(self, radians: float) -> None:
        self.root.rotation_euler[2] = float(radians)

    def set_location(self, value) -> None:
        self.root.location = Vector(value)
