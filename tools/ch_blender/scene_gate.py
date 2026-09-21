"""Fast structural gates for City Horizon Blender authoring.

Runs inside Blender and intentionally checks cheap, objective conditions before
agents spend time on expensive final renders.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

PREFLIGHT_CONTRACT = "CH_SCENE_PREFLIGHT_V1"
PROXY_CONTRACT = "CH_PROXY_RENDER_V1"
PROFILE_CONTRACT = "CH_SCENE_PREFLIGHT_PROFILE_V1"

DEFAULT_PROFILE = {
    "contract": PROFILE_CONTRACT,
    "id": "CH_ASSET_PREFLIGHT_DEFAULT_V1",
    "blenderUnitsPerTile": 3.0,
    "footprintMaxScale": 1.55,
    "groundContactTolerance": 0.20,
    "cameraMargin": 0.015,
    "character": {
        "requiredRoles": ["character.torso", "character.head"],
        "maxHeadTorsoDistance": 1.35,
        "maxHandTorsoDistance": 1.90,
        "footRoles": ["character.foot_left", "character.foot_right"],
        "handRoles": ["character.hand_left", "character.hand_right"],
    },
    "proxy": {"resolution": 256, "engine": "BLENDER_EEVEE_NEXT"},
}


def load_profile(path: str | None = None) -> dict:
    if not path:
        return dict(DEFAULT_PROFILE)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contract") != PROFILE_CONTRACT:
        raise RuntimeError(f"Unsupported preflight profile contract: {data.get('contract')!r}")
    return data


def tag(obj, role: str, *, ground_contact: bool = False) -> None:
    obj["ch.semanticRole"] = role
    if ground_contact:
        obj["ch.groundContact"] = True


def _mesh_objects(authored=None):
    objects = authored if authored is not None else bpy.context.scene.objects
    return [obj for obj in objects if obj.type == "MESH" and obj.name != "ShadowReceiverPlane"]


def _world_bbox(obj):
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


def _bounds(objects):
    pts = [pt for obj in objects for pt in _world_bbox(obj)]
    if not pts:
        return None
    return {
        "min": [min(p[i] for p in pts) for i in range(3)],
        "max": [max(p[i] for p in pts) for i in range(3)],
    }


def _center(obj):
    pts = _world_bbox(obj)
    return Vector(tuple(sum(p[i] for p in pts) / len(pts) for i in range(3)))


def _min_z(obj):
    return min(p.z for p in _world_bbox(obj))


def _semantic_map(objects):
    result = {}
    for obj in objects:
        role = obj.get("ch.semanticRole")
        if role:
            result.setdefault(str(role), []).append(obj)
    return result


def _violation(code, message, *, obj=None, metrics=None):
    value = {"code": code, "severity": "error", "message": message}
    if obj is not None:
        value["object"] = obj.name if hasattr(obj, "name") else str(obj)
    if metrics:
        value["metrics"] = metrics
    return value


def run_preflight(*, scene=None, authored=None, footprint=None, profile=None, asset_id=None, report_path=None) -> dict:
    scene = scene or bpy.context.scene
    profile = profile or dict(DEFAULT_PROFILE)
    objects = _mesh_objects(authored)
    footprint = footprint or {"widthTiles": 1, "depthTiles": 1}
    violations = []

    root = bpy.data.objects.get("AssetRoot")
    if root is None:
        violations.append(_violation("CH_PREFLIGHT_ASSET_ROOT", "AssetRoot is required as the canonical rotation/pivot root."))

    if scene.camera is None or scene.camera.data.type != "ORTHO":
        violations.append(_violation("CH_PREFLIGHT_CAMERA", "Canonical authoring requires an orthographic scene camera."))

    if scene.render.image_settings.color_mode != "RGBA" or not scene.render.film_transparent:
        violations.append(_violation(
            "CH_PREFLIGHT_ALPHA",
            "Render output must be RGBA with transparent film enabled.",
            metrics={"colorMode": scene.render.image_settings.color_mode, "filmTransparent": bool(scene.render.film_transparent)},
        ))

    if not objects:
        violations.append(_violation("CH_PREFLIGHT_EMPTY", "No authored mesh objects were found."))

    bounds = _bounds(objects)
    if bounds:
        width = bounds["max"][0] - bounds["min"][0]
        depth = bounds["max"][1] - bounds["min"][1]
        tile = float(profile.get("blenderUnitsPerTile", 3.0))
        max_scale = float(profile.get("footprintMaxScale", 1.55))
        expected_w = float(footprint.get("widthTiles", 1)) * tile
        expected_d = float(footprint.get("depthTiles", 1)) * tile
        if width > expected_w * max_scale:
            violations.append(_violation("CH_PREFLIGHT_FOOTPRINT", "Authored X extent is too large for the declared footprint.", metrics={"actual": width, "allowed": expected_w * max_scale}))
        if depth > expected_d * max_scale:
            violations.append(_violation("CH_PREFLIGHT_FOOTPRINT", "Authored Y extent is too large for the declared footprint.", metrics={"actual": depth, "allowed": expected_d * max_scale}))

    semantics = _semantic_map(objects)
    character_roles = {role for role in semantics if role.startswith("character.")}
    if character_roles:
        char = profile.get("character", {})
        for role in list(char.get("requiredRoles", [])):
            if role not in semantics:
                violations.append(_violation("CH_PREFLIGHT_MISSING_BODY_PART", f"Required semantic role is missing: {role}."))

        head = semantics.get("character.head", [None])[0]
        torso = semantics.get("character.torso", [None])[0]
        if head is not None and torso is not None:
            hc, tc = _center(head), _center(torso)
            distance = (hc - tc).length
            if hc.z <= tc.z:
                violations.append(_violation("CH_PREFLIGHT_BODY_LAYOUT", "Character head must be above the torso.", obj=head, metrics={"headZ": hc.z, "torsoZ": tc.z}))
            max_dist = float(char.get("maxHeadTorsoDistance", 1.35))
            if distance > max_dist:
                violations.append(_violation("CH_PREFLIGHT_DETACHED_BODY_PART", "Character head is too far from the torso.", obj=head, metrics={"distance": distance, "allowed": max_dist}))

            max_hand = float(char.get("maxHandTorsoDistance", 1.90))
            for role in char.get("handRoles", []):
                for hand in semantics.get(role, []):
                    distance = (_center(hand) - tc).length
                    if distance > max_hand:
                        violations.append(_violation("CH_PREFLIGHT_DETACHED_BODY_PART", f"{role} is too far from the torso.", obj=hand, metrics={"distance": distance, "allowed": max_hand}))

        tol = float(profile.get("groundContactTolerance", 0.20))
        for role in char.get("footRoles", []):
            for foot in semantics.get(role, []):
                min_z = _min_z(foot)
                if min_z > tol or min_z < -tol:
                    violations.append(_violation("CH_PREFLIGHT_GROUND_CONTACT", f"{role} does not contact the ground plane.", obj=foot, metrics={"minZ": min_z, "tolerance": tol}))

    contacts = [obj for obj in objects if bool(obj.get("ch.groundContact", False))]
    if contacts:
        tol = float(profile.get("groundContactTolerance", 0.20))
        nearest = min(abs(_min_z(obj)) for obj in contacts)
        if nearest > tol:
            violations.append(_violation("CH_PREFLIGHT_GROUND_CONTACT", "No declared ground-contact object is close enough to Z=0.", metrics={"nearestAbsMinZ": nearest, "tolerance": tol}))

    if scene.camera is not None and objects:
        margin = float(profile.get("cameraMargin", 0.015))
        projected = []
        for obj in objects:
            for pt in _world_bbox(obj):
                projected.append(world_to_camera_view(scene, scene.camera, pt))
        min_x = min(p.x for p in projected)
        max_x = max(p.x for p in projected)
        min_y = min(p.y for p in projected)
        max_y = max(p.y for p in projected)
        if min_x < -margin or max_x > 1.0 + margin or min_y < -margin or max_y > 1.0 + margin:
            violations.append(_violation(
                "CH_PREFLIGHT_CAMERA_CROP",
                "Authored geometry extends outside the camera frame.",
                metrics={"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y, "margin": margin},
            ))

    report = {
        "contract": PREFLIGHT_CONTRACT,
        "status": "pass" if not violations else "fail",
        "assetId": asset_id,
        "profile": profile.get("id", "inline"),
        "meshCount": len(objects),
        "semanticRoles": sorted(semantics.keys()),
        "footprint": footprint,
        "bounds": bounds,
        "violations": violations,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def require_pass(report: dict) -> None:
    if report.get("status") != "pass":
        codes = ",".join(v["code"] for v in report.get("violations", []))
        raise RuntimeError(f"CH_PREFLIGHT_REJECTED:{codes}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def render_proxy(*, scene=None, authored=None, output_path, profile=None, asset_id=None, direction="south") -> dict:
    scene = scene or bpy.context.scene
    profile = profile or dict(DEFAULT_PROFILE)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    authored = _mesh_objects(authored)

    ground = bpy.data.objects.get("ShadowReceiverPlane")
    if ground is not None:
        ground.hide_render = True

    old = {
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "path": scene.render.filepath,
        "transparent": scene.render.film_transparent,
        "color_mode": scene.render.image_settings.color_mode,
        "cycles_samples": getattr(scene.cycles, "samples", None),
    }

    proxy_cfg = profile.get("proxy", {})
    resolution = int(proxy_cfg.get("resolution", 256))
    requested_engine = str(proxy_cfg.get("engine", "BLENDER_EEVEE_NEXT"))
    engine_used = requested_engine

    try:
        try:
            scene.render.engine = requested_engine
        except Exception:
            engine_used = old["engine"]
            scene.render.engine = old["engine"]
            if old["cycles_samples"] is not None:
                scene.cycles.samples = 1

        scene.render.resolution_x = resolution
        scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = True
        scene.render.filepath = str(output)
        for obj in authored:
            obj.hide_render = False
        bpy.ops.render.render(write_still=True)
    finally:
        scene.render.engine = old["engine"]
        scene.render.resolution_x = old["x"]
        scene.render.resolution_y = old["y"]
        scene.render.resolution_percentage = old["pct"]
        scene.render.filepath = old["path"]
        scene.render.film_transparent = old["transparent"]
        scene.render.image_settings.color_mode = old["color_mode"]
        if old["cycles_samples"] is not None:
            scene.cycles.samples = old["cycles_samples"]
        if ground is not None:
            ground.hide_render = False

    return {
        "contract": PROXY_CONTRACT,
        "status": "ok",
        "assetId": asset_id,
        "direction": direction,
        "engine": engine_used,
        "resolution": [resolution, resolution],
        "path": str(output),
        "bytes": output.stat().st_size,
        "sha256": _sha256(output),
    }
