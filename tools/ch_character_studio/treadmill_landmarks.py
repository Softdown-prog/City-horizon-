#!/usr/bin/env python3
"""Generate CH_CHARACTER_LANDMARKS_V0 from the approved CH Actor walk.

The sprite walk is intentionally treadmill/in-place: the canonical ground anchor
never moves. Runtime/world translation is a separate engine concern.

V4 keeps the approved 8-frame timing, horizontal stride and V3 shoe path while
polishing the leg chain itself: the knee follows less of the foot depth excursion,
uses a lower lift, and bends through a smoother arc so the thigh/shin do not read
as a stiff marching leg at extreme poses.
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

# Conservative body polish retained from V2/V3.
LEG_VERTICAL_GAIN = 0.86
BODY_BOB_GAIN = 0.75
ARM_EXTREME_GAIN = 0.92
ARM_ELBOW_GAIN = 0.94

# V3 feet retained exactly: foot stride/depth remains unchanged.
ANKLE_LIFT_GAIN = 0.84
FOOT_LIFT_GAIN = 0.74

# V4 legs: calm the knee without shortening the step.
KNEE_LIFT_GAIN = 0.78
KNEE_DEPTH_FOLLOW = 0.34
KNEE_FORWARD_BEND = 0.020


def smooth_positive(value: float) -> float:
    """C1-smoothed positive half-wave in [0,1]."""
    u = max(0.0, min(1.0, value))
    return u * u * (3.0 - 2.0 * u)


def soften_extreme(wave: float, companion: float) -> float:
    """Keep transition speed but ease the very end of arm swing slightly."""
    gain = ARM_EXTREME_GAIN + (1.0 - ARM_EXTREME_GAIN) * abs(companion)
    return wave * gain


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
    theta = 2 * math.pi * phase
    sine = 0.0 if idle else math.sin(theta)
    cosine = 0.0 if idle else math.cos(theta)
    bob = 0.0 if idle else (.004 * BODY_BOB_GAIN) * abs(math.sin(2 * theta))

    world: dict[str, tuple[float, float, float]] = {
        "head": (0, .875 + bob, 0),
        "head_top": (0, .995 + bob, 0),
        "neck": (0, .735 + bob, .005),
        "chest": (0, .58 + bob, .015),
        "pelvis": (0, .405, 0),
    }

    for sign, suffix in ((-1, "L"), (1, "R")):
        arm_wave = soften_extreme(-sign * sine, cosine)
        shoulder = (sign * .175, .685 + bob, -.005)
        elbow = (sign * .205, .565 + bob, .055 * ARM_ELBOW_GAIN * arm_wave)
        hand = (sign * .19, .445 + bob, .115 * arm_wave + .01)
        world[f"shoulder_{suffix}"] = shoulder
        world[f"elbow_{suffix}"] = elbow
        world[f"hand_{suffix}"] = hand

        swing = sign * sine
        hip = (sign * .078, .405, 0)

        # Authoritative foot depth/stride path. V4 deliberately does not change
        # this value, so the V3 shoe/contact work remains intact.
        z = .145 * swing + .025 * sign * cosine
        swing_lift = smooth_positive(swing)
        transfer_lift = smooth_positive(sign * cosine)
        lifted = LEG_VERTICAL_GAIN * (swing_lift * .032 + transfer_lift * .012)

        # Knee motion is intentionally calmer than the foot. It follows only a
        # portion of the foot depth excursion and uses a smaller forward-bend
        # term. This lets the shin articulate while the thigh remains readable.
        knee = (
            sign * .08,
            .225 + lifted * .33 * KNEE_LIFT_GAIN,
            z * KNEE_DEPTH_FOLLOW - KNEE_FORWARD_BEND * swing_lift,
        )

        # V3 ankle/toe path is kept byte-for-byte in formula/coefficients.
        base_x = sign * (.082 + .008 * abs(sine))
        ankle = (base_x, .035 + lifted * ANKLE_LIFT_GAIN + .055, z - .016)
        toe = (base_x, .035 + lifted * FOOT_LIFT_GAIN, z + .085)

        world[f"hip_{suffix}"] = hip
        world[f"knee_{suffix}"] = knee
        world[f"ankle_{suffix}"] = ankle
        world[f"foot_{suffix}"] = toe

    return {name: project(direction, point) for name, point in world.items()}


def frame_record(direction: float, phase: float, *, idle: bool = False) -> dict:
    points = pose_points(direction, phase, idle=idle)
    left = points["foot_L"]
    right = points["foot_R"]
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
        "walkPolish": {
            "version": "V4_leg_polish",
            "legVerticalGain": LEG_VERTICAL_GAIN,
            "kneeLiftGain": KNEE_LIFT_GAIN,
            "kneeDepthFollow": KNEE_DEPTH_FOLLOW,
            "kneeForwardBend": KNEE_FORWARD_BEND,
            "ankleLiftGain": ANKLE_LIFT_GAIN,
            "footLiftGain": FOOT_LIFT_GAIN,
            "bodyBobGain": BODY_BOB_GAIN,
            "armExtremeGain": ARM_EXTREME_GAIN,
            "armElbowGain": ARM_ELBOW_GAIN,
            "horizontalStridePreserved": True,
            "v3FootPathPreserved": True,
            "footLiftEasing": "smoothstep_positive_half_wave",
        },
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
        "walkPolish": payload["walkPolish"],
        "frames": len(payload["frames"]),
        "groundAnchor": payload["groundAnchor"],
        "rootTranslationLockedPx": payload["rootTranslationLockedPx"],
        "output": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
