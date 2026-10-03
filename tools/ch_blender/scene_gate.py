"""Fast structural gates for City Horizon Blender authoring.

Runs inside Blender and intentionally checks cheap, objective conditions before
agents spend time on expensive final renders.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tycoon_photo_studio"))
from render_geometry import proxy_resolution_for, scene_studio_state

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
    "proxy": {"resolution": 256, "engine": "CYCLES", "samples": 8},
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
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]


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


def run_preflight(*, scene=None, authored=None, footprint=None, profile=None, asset_id=None, report_path=None, requirements=None) -> dict:
    scene = scene or bpy.context.scene
    profile = profile or dict(DEFAULT_PROFILE)
    objects = [obj for obj in _mesh_objects(authored) if not obj.hide_render]
    footprint = footprint or {"widthTiles": 1, "depthTiles": 1}
    requirements = requirements or json.loads(os.environ.get("CH_ASSET_REQUIREMENTS", "{}"))
    violations = []

    root = bpy.data.objects.get("AssetRoot")
    if root is None:
        violations.append(_violation("CH_PREFLIGHT_ASSET_ROOT", "AssetRoot is required as the canonical rotation/pivot root."))
    else:
        for obj in objects:
            parent = obj.parent
            while parent is not None and parent != root:
                parent = parent.parent
            if parent != root:
                violations.append(_violation("CH_PREFLIGHT_UNPARENTED", "Authored geometry must rotate with AssetRoot.", obj=obj))

    if scene.camera is None or scene.camera.data.type != "ORTHO":
        violations.append(_violation("CH_PREFLIGHT_CAMERA", "Canonical authoring requires an orthographic scene camera."))
    elif scene.camera is not None:
        forward = scene.camera.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        elevation = math.degrees(math.asin(max(-1.0, min(1.0, -forward.z))))
        # Studio yaw is measured clockwise: camera location is (+cos, -sin).
        yaw = math.degrees(math.atan2(forward.y, -forward.x)) % 360.0
        if abs(elevation - 30.0) > 0.1 or abs(yaw - 45.0) > 0.1:
            violations.append(_violation("CH_PREFLIGHT_CAMERA", "Actual camera must obey CH_CAMERA_V1, not just name it.",
                                         metrics={"yawDegrees": yaw, "elevationDegrees": elevation}))
        if abs(scene.render.pixel_aspect_x - scene.render.pixel_aspect_y) > 0.0001:
            violations.append(_violation("CH_PREFLIGHT_CAMERA", "Game sprites require square pixels."))

    baseline = scene.get("ch.studioLightingState")
    if baseline:
        actual = json.dumps([
            {"name": obj.name, "matrix": [list(row) for row in obj.matrix_world],
             "energy": obj.data.energy, "color": list(obj.data.color), "type": obj.data.type}
            for obj in scene.objects if obj.type == "LIGHT"], sort_keys=True)
        if actual != baseline:
            violations.append(_violation("CH_PREFLIGHT_STUDIO_DRIFT", "Builder changed the configured studio lights."))
    if scene.get("ch.studioState") and scene_studio_state(scene) != scene["ch.studioState"]:
        violations.append(_violation("CH_PREFLIGHT_STUDIO_DRIFT", "Builder changed the configured camera/world/color management."))

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
    if requirements.get("assetId") and requirements["assetId"] != asset_id:
        violations.append(_violation("CH_PREFLIGHT_REQUIREMENTS", "Asset identity differs from the job request."))
    if requirements.get("footprint") and any(
        footprint.get(key) != value for key, value in requirements["footprint"].items()
    ):
        violations.append(_violation("CH_PREFLIGHT_REQUIREMENTS", "Footprint differs from the job request."))
    for role in requirements.get("requiredRoles", []):
        if role not in semantics:
            violations.append(_violation("CH_PREFLIGHT_REQUIREMENTS", f"Requested semantic role is missing: {role}."))
    if bounds:
        dimensions = [bounds["max"][i] - bounds["min"][i] for i in range(3)]
        for field, compare in (("minDimensions", lambda actual, limit: actual < limit),
                               ("maxDimensions", lambda actual, limit: actual > limit)):
            for axis, limit in enumerate(requirements.get(field, [])):
                if limit is not None and compare(dimensions[axis], float(limit)):
                    violations.append(_violation("CH_PREFLIGHT_REQUIREMENTS", f"Authored dimension violates {field}.",
                                                 metrics={"axis": axis, "actual": dimensions[axis], "limit": limit}))
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

    projected_views = {}
    if scene.camera is not None and objects:
        margin = float(profile.get("cameraMargin", 0.015))
        original_rotation = root.rotation_euler[2] if root is not None else None
        try:
            for direction, degrees in (("south", 0), ("east", 90), ("west", 270), ("north", 180)):
                if root is not None:
                    root.rotation_euler[2] = math.radians(degrees)
                    bpy.context.view_layer.update()
                projected = [world_to_camera_view(scene, scene.camera, pt)
                             for obj in objects for pt in _world_bbox(obj)]
                values = {"minX": min(p.x for p in projected), "maxX": max(p.x for p in projected),
                          "minY": min(p.y for p in projected), "maxY": max(p.y for p in projected)}
                projected_views[direction] = values
                if (values["minX"] < -margin or values["maxX"] > 1.0 + margin or
                        values["minY"] < -margin or values["maxY"] > 1.0 + margin or min(p.z for p in projected) <= 0):
                    violations.append(_violation("CH_PREFLIGHT_CAMERA_CROP",
                        f"Evaluated geometry is cropped in {direction.upper()}.", metrics={**values, "margin": margin}))
        finally:
            if root is not None:
                root.rotation_euler[2] = original_rotation
                bpy.context.view_layer.update()

    report = {
        "contract": PREFLIGHT_CONTRACT,
        "status": "pass" if not violations else "fail",
        "assetId": asset_id,
        "profile": profile.get("id", "inline"),
        "meshCount": len(objects),
        "semanticRoles": sorted(semantics.keys()),
        "footprint": footprint,
        "bounds": bounds,
        "projectedViews": projected_views,
        "studioFingerprint": scene.get("ch.studioFingerprint"),
        "sourceFingerprint": os.environ.get("CH_SOURCE_FINGERPRINT"),
        "requirements": requirements,
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
    old_visibility = [(obj, obj.hide_render) for obj in authored]
    ground_visibility = ground.hide_render if ground is not None else None
    old = {
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "path": scene.render.filepath,
        "transparent": scene.render.film_transparent,
        "color_mode": scene.render.image_settings.color_mode,
        "file_format": scene.render.image_settings.file_format,
        "cycles_samples": getattr(scene.cycles, "samples", None),
    }

    proxy_cfg = profile.get("proxy", {})
    resolution = proxy_resolution_for((old["x"], old["y"]), int(proxy_cfg.get("resolution", 256)))
    requested_engine = str(proxy_cfg.get("engine", "BLENDER_EEVEE_NEXT"))
    engine_used = requested_engine

    try:
        if ground is not None:
            ground.hide_render = True
        try:
            scene.render.engine = requested_engine
        except Exception:
            engine_used = old["engine"]
            scene.render.engine = old["engine"]
            if old["cycles_samples"] is not None:
                scene.cycles.samples = 1

        if engine_used == "CYCLES" and old["cycles_samples"] is not None:
            scene.cycles.samples = max(1, int(proxy_cfg.get("samples", min(old["cycles_samples"], 8))))

        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = True
        scene.render.filepath = str(output)
        # Respect intentionally hidden authoring/alternate geometry.
        bpy.ops.render.render(write_still=True)
        origin = world_to_camera_view(scene, scene.camera, Vector((0.0, 0.0, 0.0)))
        tile_points = [world_to_camera_view(scene, scene.camera, Vector(pt)) for pt in
                       ((0, 0, 0), (3, 0, 0), (3, 3, 0), (0, 3, 0))]
        tile_width = (max(p.x for p in tile_points) - min(p.x for p in tile_points)) * resolution[0]
    finally:
        scene.render.engine = old["engine"]
        scene.render.resolution_x = old["x"]
        scene.render.resolution_y = old["y"]
        scene.render.resolution_percentage = old["pct"]
        scene.render.filepath = old["path"]
        scene.render.film_transparent = old["transparent"]
        scene.render.image_settings.color_mode = old["color_mode"]
        scene.render.image_settings.file_format = old["file_format"]
        if old["cycles_samples"] is not None:
            scene.cycles.samples = old["cycles_samples"]
        for obj, hidden in old_visibility:
            obj.hide_render = hidden
        if ground is not None:
            ground.hide_render = ground_visibility

    return {
        "contract": PROXY_CONTRACT,
        "status": "ok",
        "assetId": asset_id,
        "direction": direction,
        "engine": engine_used,
        "resolution": list(resolution),
        "groundOriginPx": {"x": origin.x * resolution[0], "y": (1.0 - origin.y) * resolution[1]},
        "projectedTileWidthPx": tile_width,
        "studioFingerprint": scene.get("ch.studioFingerprint"),
        "sourceFingerprint": os.environ.get("CH_SOURCE_FINGERPRINT"),
        "path": str(output),
        "bytes": output.stat().st_size,
        "sha256": _sha256(output),
    }
