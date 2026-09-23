"""Guarded V4 visitor builder using CH_VISITOR_BASE_MESH_V1.

This is the first visitor pass where the body is treated as a reusable canonical
mesh profile rather than being rediscovered by each procedural iteration.
"""
from __future__ import annotations

import bpy

import build_scene as bs
import build_visitor_guarded as v1
import visitor_base_mesh_v1 as base_mesh

BASE_MESH_PROFILE = "tools/tycoon_photo_studio/assets/visitor_male_base_mesh_v1.json"


def build_canonical_visitor(asset):
    return base_mesh.build_visitor(asset, BASE_MESH_PROFILE)


v1.build_visitor = build_canonical_visitor
_original_build_for_gate = v1.build_for_gate


def build_for_gate_close_review(args):
    result = _original_build_for_gate(args)
    asset, studio, scene, ground, authored, rig, out = result
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.22)
    rig["root"]["reviewProxyFraming"] = "canonical_base_mesh_close_review"
    rig["root"]["baseMeshProfile"] = BASE_MESH_PROFILE
    bpy.context.view_layer.update()
    return result


v1.build_for_gate = build_for_gate_close_review


if __name__ == "__main__":
    v1.main()
