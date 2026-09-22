"""Canonical guarded IDLE+GREET baker for raspadinha vendor animation v2.

This wrapper binds the visually reviewed lightweight GREET pose grammar to the
full fail-fast quality flow so the expensive final bake cannot accidentally use
the superseded downward-arm keyframes from the original authoring prototype.

Stages:
  preflight -> 4 directions x 5 review poses, no expensive render
  proxy     -> SOUTH 5-frame Eevee review sheet
  final     -> reviewed proxy SHA required, then full source color/shadow bake

SERVE remains intentionally out of production until real customer/NPC gameplay
exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import bpy

import build_raspadinha_vendor_animated_guarded as base
import build_raspadinha_vendor_animation_review_guarded as review
import raspadinha_vendor_greet_v1 as greet
import scene_gate

ASSET_ID = base.ASSET_ID


def main() -> None:
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out = base.build_scene_for_gate(args)

    # Production GREET authority. IDLE, cart geometry and the dormant SERVE
    # prototype are untouched.
    greet.apply()

    preflight = review.run_animation_preflight(scene, root, authored, profile, out)
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        if args.save_blend:
            Path(args.save_blend).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
        print(f"[CH_GATE] animation v2 preflight PASS: {preflight['samplesChecked']} samples")
        return

    if args.stage == "proxy":
        proxy = review.render_proxy_sheet(scene, root, authored, profile, out)
        if args.save_blend:
            Path(args.save_blend).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
        print(f"[CH_GATE] animation v2 SOUTH proxy ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: pass the reviewed SOUTH animation sheet SHA-256"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "animationContract": base.ANIMATION_CONTRACT,
        "animationStates": list(base.ANIM_STATES.keys()),
        "proxyReviewType": "animation_pose_sheet",
        "proxySha256": approval,
        "reviewed": True,
        "greetPoseAuthority": "tools/tycoon_photo_studio/raspadinha_vendor_greet_v1.py",
    }
    (out / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )

    # run_final_bake reads the currently authored scene/keyframes. At this point
    # the reviewed GREET v1 override is already applied to frames 5-8.
    base.run_final_bake(studio, scene, root, ground, authored, out)
    print("[CH_GATE] animation v2 final bake completed after explicit sheet approval")


if __name__ == "__main__":
    main()
