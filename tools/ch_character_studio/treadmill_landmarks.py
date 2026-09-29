#!/usr/bin/env python3
"""Generate CH_CHARACTER_LANDMARKS_V0 from the approved CH Actor walk.

The sprite walk is intentionally treadmill/in-place: the canonical ground anchor
never moves. Runtime/world translation is a separate engine concern.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAME = (48, 64)
ANCHOR = (24, 60)
YAW = math.radians(45)
ELEVATION = math.radians(30)
SCALE = 52
DIRECTIONS = (("S", 0.0), ("E", math.pi / 2), ("W", -math.pi / 2), ("N", math.pi))
FRAMES = ("idle",) + tuple(f"walk_{i:02d}" for i in range(8))


def project(direction: float, point: tuple[float, float, float]) -> list[float]:
    x, y, z = point
    c, s = math.cos(direction), math.sin(direction)
    x, z = c * x + s * z, -s * x + c * z
    right = math.cos(YAW) * x - math.sin(YAW) * z
    up = math.cos(ELEVATION) * y - math.sin(ELEVATION) * (
        math.sin(YAW) * x + math.cos(YAW) * z
    )
    return [round(ANCHOR[0] + SCALE * right, 4), round(ANCHOR[1] - SCALE * up, 4)]


def pose_points(direction: float, phase: float, *, idle: bool = False) -> dict[str, list[float]]:
    sine = 0.0 if idle else math.sin(2 * math.pi * phase)
    cosine = 0.0 if idle else math.cos(2 * math.pi * phase)
    bob = 0.0 if idle else .004 * abs(math.sin(4 * math.pi * phase))

    world: dict[str, tuple[float, float, float]] = {
        "head": (0, .875 + bob, 0),
        "head_top": (0, .995 + bob, 0),
        "neck": (0, .735 + bob, .005),
        "chest": (0, .58 + bob, .015),
        "pelvis": (0, .405, 0),
    }

    for sign, suffix in ((-1, "L"), (1, "R")):
        opposite = -sign * sine
        shoulder = (sign * .175, .685 + bob, -.005)
        elbow = (sign * .205, .565 + bob, .055 * opposite)
        hand = (sign * .19, .445 + bob, .115 * opposite + .01)
        world[f"shoulder_{suffix}"] = shoulder
        world[f"elbow_{suffix}"] = elbow
        world[f"hand_{suffix}"] = hand

        swing = sign * sine
        hip = (sign * .078, .405, 0)
        z = .145 * swing + .025 * sign * cosine
        lifted = max(0.0, swing) * .032 + max(0.0, sign * cosine) * .012
        foot_base = (sign * (.082 + .008 * abs(sine)), .035 + lifted, z)
        knee = (sign * .08, .225 + lifted * .33, z * .42 - .028 * max(0.0, swing))
        ankle = (foot_base[0], foot_base[1] + .055, foot_base[2] - .016)
        toe = (foot_base[0], foot_base[1], foot_base[2] + .085)
        world[f"hip_{suffix}"] = hip
        world[f"knee_{suffix}"] = knee
        world[f"ankle_{suffix}"] = ankle
        world[f"foot_{suffix}"] = toe

    return {name: project(direction, point) for name, point in world.items()}


def frame_record(direction: float, phase: float, *, idle: bool = False) -> dict:
    points = pose_points(direction, phase, idle=idle)
    left = points["foot_L"]
    right = points["foot_R"]
    # Screen-space lower foot is the support/contact candidate. This is only a
    # debug label; it never changes the fixed runtime ground anchor.
    support_name = "left" if left[1] >= right[1] else "right"
    support = left if support_name == "left" else right
    footprint = [[20, 58], [24, 56], [28, 58], [24, 61]]
    return {
        "points": points,
        "anchors": {
            "ground": list(ANCHOR),
            "leftFoot": left,
            "rightFoot": right,
            "supportFootName": support_name,
            "supportFoot": support,
            "footprint": {"shape": "diamond_2to1", "polygonPx": footprint},
        },
        "sockets": {"left_hand": points["hand_L"], "right_hand": points["hand_R"]},
        "rootTranslationPx": [0, 0],
    }


def build() -> dict:
    frames: dict[str, dict] = {}
    for logical, angle in DIRECTIONS:
        frames[f"{logical}:idle"] = frame_record(angle, 0.0, idle=True)
        for i in range(8):
            frames[f"{logical}:walk_{i:02d}"] = frame_record(angle, i / 8.0)
    return {
        "contract": "CH_CHARACTER_LANDMARKS_V0",
        "source": "tools/ch_actor_lab/software_render.py approved 8-frame locomotion",
        "motionMode": "treadmill_in_place",
        "worldTranslation": "runtime_only_separate_from_sprite_cycle",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "rootTranslationLockedPx": [0, 0],
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "contract": payload["contract"],
        "motionMode": payload["motionMode"],
        "frames": len(payload["frames"]),
        "groundAnchor": payload["groundAnchor"],
        "rootTranslationLockedPx": payload["rootTranslationLockedPx"],
        "output": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
