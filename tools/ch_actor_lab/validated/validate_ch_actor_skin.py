#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "tools/ch_actor_lab/validated/ch_actor_validated_v1.json"
MOTION = ROOT / "tools/ch_actor_lab/motion/ch_actor_walk_v1.json"
SPEC = ROOT / "tools/ch_character_studio/specs/clown_01.character.json"
SKIN = ROOT / "tools/ch_actor_lab/skins/clown_01_v1.js"
CORE = ROOT / "tools/ch_actor_lab/validated/ch_actor_validated_v1.js"


def fail(msg: str) -> None:
    raise SystemExit(f"CH_ACTOR_VALIDATED_GATE_FAIL: {msg}")


def main() -> int:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    motion = json.loads(MOTION.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    skin = SKIN.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")

    expected = {
        "frame": {"width": 48, "height": 64, "groundAnchor": [24, 60]},
        "camera": {"yawDeg": 45, "pitchDeg": 30},
        "animation": {"frameCount": 8, "legSwingRad": 0.32, "armSwingRad": 0.18, "verticalBounce": 0.004},
    }
    if base.get("contract") != "CH_ACTOR_VALIDATED_V1": fail("baseline contract changed")
    if [base["frame"]["width"], base["frame"]["height"]] != [48, 64]: fail("frame size changed")
    if base["frame"]["groundAnchor"] != [24, 60]: fail("ground anchor changed")
    if [base["camera"]["yawDeg"], base["camera"]["pitchDeg"]] != [45, 30]: fail("camera changed")
    if base["animation"]["frameCount"] != 8: fail("walk frame count changed")
    for key, value in (("legSwingRad", .32), ("armSwingRad", .18), ("verticalBounce", .004)):
        if float(base["animation"][key]) != value: fail(f"{key} changed")
    dirs = [(d["logical"], round(float(d["angleRad"]), 12)) for d in base["directions"]]
    wanted = [("S", round(1.5707963267948966,12)), ("E",0.0), ("W",round(3.141592653589793,12)), ("N",round(-1.5707963267948966,12))]
    if dirs != wanted: fail(f"direction mapping changed: {dirs}")

    if motion.get("contract") != "CH_ACTOR_WALK_MOTION_V1": fail("approved motion contract missing")
    if motion["frame"] != {"width":48,"height":64,"groundAnchor":[24,60]}: fail("production motion frame/anchor drift")
    if motion["walk"]["frameCount"] != 8: fail("production motion frame count drift")

    m = spec.get("motion", {})
    if m.get("authority") != "CH_ACTOR_VALIDATED_V1": fail("clown motion authority is not validated actor")
    if m.get("allowArtToModifyPose") is not False: fail("art may modify pose")
    if m.get("headIndependentYawAllowed") is not False: fail("independent head yaw enabled")
    if spec.get("underlayAuthority", {}).get("blenderMayReplaceActor") is not False: fail("Blender may replace validated actor")
    if spec.get("underlayAuthority", {}).get("headIsChildOfTorso") is not True: fail("head/torso parenting not locked")

    forbidden_skin = ["actor.root.rotation", "actor.head.rotation", "actor.torso.position.y=", "CORE.pose("]
    for token in forbidden_skin:
        if token in skin: fail(f"skin contains forbidden motion edit: {token}")
    required_core = ["head_LOCKED_CHILD_OF_TORSO", "-.30*Math.max(0,-s)-.08*Math.max(0,c)", "arm*s", "bounce*Math.abs(Math.sin(4*Math.PI*phase))"]
    for token in required_core:
        if token not in core: fail(f"validated core formula marker missing: {token}")

    print(json.dumps({
        "contract": "CH_ACTOR_VALIDATED_GATE_V1",
        "status": "ok",
        "actor": "CH_ACTOR_VALIDATED_V1",
        "skin": "clown_01",
        "motion": "CH_ACTOR_WALK_MOTION_V1",
        "frame": [48,64],
        "anchor": [24,60],
        "directions": ["S","E","W","N"],
        "walkFrames": 8,
        "headParent": "torso",
        "blenderAuthority": False
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
