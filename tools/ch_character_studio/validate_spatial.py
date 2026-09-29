#!/usr/bin/env python3
"""Validate CH Character Studio anchors, foot contacts, sockets and footprint."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

FRAME = (48, 64)
GROUND = (24.0, 60.0)
EXPECTED_STATES = 36
MAX_SUPPORT_DISTANCE = 10.0


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def point_ok(value: object) -> bool:
    return (
        isinstance(value, list) and len(value) == 2
        and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in value)
    )


def inside_frame(point: list[float], margin: float = 0.5) -> bool:
    return -margin <= point[0] <= FRAME[0] - 1 + margin and -margin <= point[1] <= FRAME[1] - 1 + margin


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("contract") != "CH_CHARACTER_LANDMARKS_V0":
        errors.append("contract must be CH_CHARACTER_LANDMARKS_V0")
    if data.get("spatialContract") != "CH_CHARACTER_SPATIAL_V0":
        errors.append("spatialContract must be CH_CHARACTER_SPATIAL_V0")
    if data.get("frameSize") != list(FRAME):
        errors.append("frameSize must be [48,64]")
    if data.get("groundAnchor") != list(map(int, GROUND)):
        errors.append("groundAnchor must be [24,60]")
    frames = data.get("frames") or {}
    if len(frames) != EXPECTED_STATES:
        errors.append(f"expected {EXPECTED_STATES} frame states, got {len(frames)}")

    for key, frame in sorted(frames.items()):
        points = frame.get("points") or {}
        anchors = frame.get("anchors") or {}
        sockets = frame.get("sockets") or {}
        for name in ("foot_L", "foot_R", "ankle_L", "ankle_R", "hand_L", "hand_R"):
            point = points.get(name)
            if not point_ok(point):
                errors.append(f"{key}: missing/invalid point {name}")
                continue
            if name.startswith(("foot_", "ankle_")) and not inside_frame(point):
                errors.append(f"{key}: {name} outside frame: {point}")
        if anchors.get("ground") != [24, 60]:
            errors.append(f"{key}: canonical ground anchor changed: {anchors.get('ground')}")
        support = anchors.get("supportFoot")
        if not point_ok(support):
            errors.append(f"{key}: invalid supportFoot")
        else:
            distance = math.hypot(float(support[0]) - GROUND[0], float(support[1]) - GROUND[1])
            if distance > MAX_SUPPORT_DISTANCE:
                errors.append(f"{key}: support foot is {distance:.2f}px from ground anchor (max {MAX_SUPPORT_DISTANCE})")
        if anchors.get("supportFootName") not in {"foot_L", "foot_R"}:
            errors.append(f"{key}: supportFootName must be foot_L or foot_R")
        footprint = (anchors.get("footprint") or {}).get("polygonPx")
        if not isinstance(footprint, list) or len(footprint) < 8 or not all(point_ok(p) for p in footprint):
            errors.append(f"{key}: invalid projected footprint polygon")
        for socket, landmark in (("left_hand", "hand_L"), ("right_hand", "hand_R")):
            if sockets.get(socket) != points.get(landmark):
                errors.append(f"{key}: {socket} socket must match {landmark}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        data = load(args.landmarks)
        errors = validate(data)
        payload = {
            "contract": "CH_CHARACTER_SPATIAL_REPORT_V0",
            "status": "error" if errors else "ok",
            "states": len(data.get("frames") or {}),
            "groundAnchor": data.get("groundAnchor"),
            "maxSupportDistancePx": MAX_SUPPORT_DISTANCE,
            "errors": errors,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 2 if errors else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stdout.write(json.dumps({"contract":"CH_CHARACTER_SPATIAL_REPORT_V0","status":"error","errors":[str(exc)]}, indent=2) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
