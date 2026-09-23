"""Guarded V5 visitor builder using CH_VISITOR_BASE_MESH_V2.

V5 is the first pass where the canonical body itself uses continuous multi-ring
limb meshes. Rig, walk policy and SOUTH-only approval gate remain unchanged.
"""
from __future__ import annotations

import bpy

import build_scene as bs
import build_visitor_guarded as v1
import visitor_base_mesh_v2 as base_mesh

BASE_MESH_PROFILE = "tools/tycoon_photo_studio/assets/visitor_male_base_mesh_v2.json"


def build_canonical_visitor(asset):
    return base_mesh.build_visitor(asset, BASE_MESH_PROFILE)


v1.build_visitor = build_canonical_visitor
_original_build_for_gate = v1.build_for_gate


def build_for_gate_close_review(args):
    result = _original_build_for_gate(args)
    asset, studio, scene, ground, authored, rig, out = result
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.22)
    rig["root"]["reviewProxyFraming"] = "continuous_base_mesh_v2_close_review"
    rig["root"]["baseMeshProfile"] = BASE_MESH_PROFILE
    bpy.context.view_layer.update()
    return result


v1.build_for_gate = build_for_gate_close_review


if __name__ == "__main__":
    v1.main()
