"""City Horizon lightweight greeting poses for the raspadinha vendor.

This module intentionally overrides only GREET frames 5-8. It does not touch
IDLE, SERVE, cart geometry, materials, camera or studio settings.

The pose grammar is deliberately simple for the 2D pre-rendered runtime:
  frame 5: raise the right arm
  frame 6: peak greeting, hand above shoulder/head line
  frame 7: small return/wave variation
  frame 8: canonical idle return
"""

from __future__ import annotations

import bpy

import build_raspadinha_vendor_blender as rv


def apply() -> None:
    required = {
        "head": "HeadPivot",
        "shoulder": "Arm_R_Shoulder",
        "elbow": "Arm_R_Elbow",
    }
    objects = {}
    for role, name in required.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"CH_GREET_AUTHORING_ERROR: missing {name}")
        objects[role] = obj

    head = objects["head"]
    shoulder = objects["shoulder"]
    elbow = objects["elbow"]

    # Raised-arm greeting. The arm chains are authored along local -Z, so a
    # large negative local-Y shoulder rotation brings the upper arm outward,
    # while the elbow bend turns the forearm upward. Keep the movement compact.
    rv.set_rot(head, 5, (0, 0, -5))
    rv.set_rot(shoulder, 5, (0, -85, 5))
    rv.set_rot(elbow, 5, (0, -75, -5))

    rv.set_rot(head, 6, (0, 0, -7))
    rv.set_rot(shoulder, 6, (0, -100, 5))
    rv.set_rot(elbow, 6, (0, -80, 8))

    rv.set_rot(head, 7, (0, 0, -5))
    rv.set_rot(shoulder, 7, (0, -95, 5))
    rv.set_rot(elbow, 7, (0, -68, -8))

    # Explicit clean return to the canonical resting pose.
    rv.set_rot(head, 8, (0, 0, 0))
    rv.set_rot(shoulder, 8, (0, 12, 16))
    rv.set_rot(elbow, 8, (0, 0, 0))

    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
