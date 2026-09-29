#!/usr/bin/env python3
"""Deterministic project-math worker for City Horizon agents and tools.

The worker is deliberately dependency-free and read-only. It derives canonical
camera/grid constants from src/ch_core/contracts.h on every invocation so it
cannot silently become a second source of truth.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_H = REPO_ROOT / "src/ch_core/contracts.h"
JOB_CONTRACT = "CH_MATH_JOB_V1"
REPORT_CONTRACT = "CH_MATH_REPORT_V1"
WORKER_CONTRACT = "CH_MATH_WORKER_V1"


class MathWorkerError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class Canonical:
    tile_width: float
    tile_height: float
    map_min: int
    map_max: int
    camera_yaw_deg: float
    camera_elevation_deg: float
    camera_perspective: bool
    grid_contract: str
    camera_contract: str
    road_contract: str

    @property
    def elevation_pixels_per_world_unit(self) -> float:
        return self.tile_width * math.sqrt(3.0 / 8.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tileWidth": self.tile_width,
            "tileHeight": self.tile_height,
            "mapMin": self.map_min,
            "mapMax": self.map_max,
            "cameraYawDeg": self.camera_yaw_deg,
            "cameraElevationDeg": self.camera_elevation_deg,
            "cameraPerspective": self.camera_perspective,
            "gridContract": self.grid_contract,
            "cameraContract": self.camera_contract,
            "roadContract": self.road_contract,
            "elevationPixelsPerWorldUnit": self.elevation_pixels_per_world_unit,
        }


def _read_contracts() -> Canonical:
    text = CONTRACTS_H.read_text(encoding="utf-8")

    def number(name: str) -> float:
        match = re.search(rf"\b{name}\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", text)
        if not match:
            raise MathWorkerError("CANONICAL_SOURCE_INVALID", f"Cannot read {name} from {CONTRACTS_H}")
        return float(match.group(1))

    def integer(name: str) -> int:
        value = number(name)
        if not value.is_integer():
            raise MathWorkerError("CANONICAL_SOURCE_INVALID", f"{name} must be an integer")
        return int(value)

    def boolean(name: str) -> bool:
        match = re.search(rf"\b{name}\s*=\s*(true|false)", text)
        if not match:
            raise MathWorkerError("CANONICAL_SOURCE_INVALID", f"Cannot read {name} from {CONTRACTS_H}")
        return match.group(1) == "true"

    def string(name: str) -> str:
        match = re.search(rf'\b{name}\s*=\s*"([^"]+)"', text)
        if not match:
            raise MathWorkerError("CANONICAL_SOURCE_INVALID", f"Cannot read {name} from {CONTRACTS_H}")
        return match.group(1)

    canonical = Canonical(
        tile_width=number("kTileWidth"),
        tile_height=number("kTileHeight"),
        map_min=integer("kMapMin"),
        map_max=integer("kMapMax"),
        camera_yaw_deg=number("kCameraWorldYawDeg"),
        camera_elevation_deg=number("kCameraElevationDeg"),
        camera_perspective=boolean("kCameraPerspective"),
        grid_contract=string("kGridContract"),
        camera_contract=string("kCameraContract"),
        road_contract=string("kRoadContract"),
    )
    if canonical.grid_contract != "CH_GRID_V1" or canonical.camera_contract != "CH_CAMERA_V1":
        raise MathWorkerError(
            "CONTRACT_MISMATCH",
            "Worker only supports the current canonical City Horizon grid/camera contracts",
            canonical.as_dict(),
        )
    return canonical


def _finite(value: Any, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise MathWorkerError("JOB_INVALID", f"{label} must be numeric") from exc
    if not math.isfinite(out):
        raise MathWorkerError("JOB_INVALID", f"{label} must be finite")
    return out


def _point3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, dict):
        raise MathWorkerError("JOB_INVALID", f"{label} must be an object")
    return (
        _finite(value.get("x"), f"{label}.x"),
        _finite(value.get("y"), f"{label}.y"),
        _finite(value.get("z", 0.0), f"{label}.z"),
    )


def _point2(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, dict):
        raise MathWorkerError("JOB_INVALID", f"{label} must be an object")
    return (
        _finite(value.get("x"), f"{label}.x"),
        _finite(value.get("y"), f"{label}.y"),
    )


def _camera(job: dict[str, Any]) -> tuple[float, float, float, int]:
    camera = job.get("camera", {})
    if not isinstance(camera, dict):
        raise MathWorkerError("JOB_INVALID", "camera must be an object")
    pan_x = _finite(camera.get("panX", 0.0), "camera.panX")
    pan_y = _finite(camera.get("panY", 0.0), "camera.panY")
    zoom = _finite(camera.get("zoom", 1.0), "camera.zoom")
    if zoom <= 0.0:
        raise MathWorkerError("JOB_INVALID", "camera.zoom must be > 0")
    rotation = int(camera.get("rotation", 0))
    if rotation not in (0, 1, 2, 3):
        raise MathWorkerError("JOB_INVALID", "camera.rotation must be 0, 1, 2 or 3")
    return pan_x, pan_y, zoom, rotation


def _viewport(job: dict[str, Any]) -> tuple[float, float]:
    viewport = job.get("viewport")
    if not isinstance(viewport, dict):
        raise MathWorkerError("JOB_INVALID", "viewport must be an object")
    width = _finite(viewport.get("width"), "viewport.width")
    height = _finite(viewport.get("height"), "viewport.height")
    if width <= 0.0 or height <= 0.0:
        raise MathWorkerError("JOB_INVALID", "viewport dimensions must be > 0")
    return width, height


def _camera_view(x: float, y: float, rotation: int) -> tuple[float, float]:
    if rotation == 0:
        return x, y
    if rotation == 1:
        return y, -x
    if rotation == 2:
        return -x, -y
    return -y, x


def _logical_world(x: float, y: float, rotation: int) -> tuple[float, float]:
    if rotation == 0:
        return x, y
    if rotation == 1:
        return -y, x
    if rotation == 2:
        return -x, -y
    return y, -x


def _world_to_screen(
    p: tuple[float, float, float],
    canonical: Canonical,
    camera: tuple[float, float, float, int],
    viewport: tuple[float, float],
) -> dict[str, float]:
    x, y, z = p
    pan_x, pan_y, zoom, rotation = camera
    width, height = viewport
    vx, vy = _camera_view(x, y, rotation)
    return {
        "x": width * 0.5 + pan_x + (vx - vy) * (canonical.tile_width * 0.5) * zoom,
        "y": height * 0.5 + pan_y + (vx + vy) * (canonical.tile_height * 0.5) * zoom
        - z * canonical.elevation_pixels_per_world_unit * zoom,
    }


def _screen_to_tile(
    p: tuple[float, float],
    canonical: Canonical,
    camera: tuple[float, float, float, int],
    viewport: tuple[float, float],
) -> dict[str, Any]:
    sx, sy = p
    pan_x, pan_y, zoom, rotation = camera
    width, height = viewport
    axis_x = (sx - width * 0.5 - pan_x) / (canonical.tile_width * 0.5 * zoom)
    axis_y = (sy - height * 0.5 - pan_y) / (canonical.tile_height * 0.5 * zoom)
    lx, ly = _logical_world((axis_y + axis_x) * 0.5, (axis_y - axis_x) * 0.5, rotation)
    return {
        "tileX": math.floor(lx),
        "tileY": math.floor(ly),
        "worldX": lx,
        "worldY": ly,
    }


def _bezier_point(
    start: tuple[float, float, float],
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    end: tuple[float, float, float],
    t: float,
) -> tuple[float, float, float]:
    t = min(1.0, max(0.0, t))
    omt = 1.0 - t
    b0 = omt * omt * omt
    b1 = 3.0 * omt * omt * t
    b2 = 3.0 * omt * t * t
    b3 = t * t * t
    return tuple(start[i] * b0 + a[i] * b1 + b[i] * b2 + end[i] * b3 for i in range(3))


def _bezier_tangent(
    start: tuple[float, float, float],
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    end: tuple[float, float, float],
    t: float,
) -> tuple[float, float, float]:
    t = min(1.0, max(0.0, t))
    omt = 1.0 - t
    k0 = 3.0 * omt * omt
    k1 = 6.0 * omt * t
    k2 = 3.0 * t * t
    return tuple(
        k0 * (a[i] - start[i]) + k1 * (b[i] - a[i]) + k2 * (end[i] - b[i])
        for i in range(3)
    )


def _segment(job: dict[str, Any]) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    segment = job.get("segment")
    if not isinstance(segment, dict):
        raise MathWorkerError("JOB_INVALID", "segment must be an object")
    return (
        _point3(segment.get("start"), "segment.start"),
        _point3(segment.get("controlA"), "segment.controlA"),
        _point3(segment.get("controlB"), "segment.controlB"),
        _point3(segment.get("end"), "segment.end"),
    )


def _samples(job: dict[str, Any]) -> list[float]:
    if "t" in job:
        raw = job["t"]
        if not isinstance(raw, list) or not raw:
            raise MathWorkerError("JOB_INVALID", "t must be a non-empty array")
        return [min(1.0, max(0.0, _finite(value, "t[]"))) for value in raw]
    count = int(job.get("samples", 17))
    if count < 2 or count > 4097:
        raise MathWorkerError("JOB_INVALID", "samples must be between 2 and 4097")
    return [index / (count - 1) for index in range(count)]


def _length(points: Iterable[tuple[float, float, float]]) -> float:
    iterator = iter(points)
    try:
        previous = next(iterator)
    except StopIteration:
        return 0.0
    total = 0.0
    for current in iterator:
        total += math.dist(previous, current)
        previous = current
    return total


def _operate(job: dict[str, Any], canonical: Canonical) -> dict[str, Any]:
    operation = job.get("operation")

    if operation == "canonical":
        return {"canonical": canonical.as_dict(), "source": str(CONTRACTS_H.relative_to(REPO_ROOT))}

    if operation == "project_world":
        camera = _camera(job)
        viewport = _viewport(job)
        points = job.get("points")
        if not isinstance(points, list) or not points:
            raise MathWorkerError("JOB_INVALID", "points must be a non-empty array")
        return {
            "points": [
                _world_to_screen(_point3(point, f"points[{index}]"), canonical, camera, viewport)
                for index, point in enumerate(points)
            ]
        }

    if operation == "screen_to_tile":
        camera = _camera(job)
        viewport = _viewport(job)
        points = job.get("points")
        if not isinstance(points, list) or not points:
            raise MathWorkerError("JOB_INVALID", "points must be a non-empty array")
        return {
            "points": [
                _screen_to_tile(_point2(point, f"points[{index}]"), canonical, camera, viewport)
                for index, point in enumerate(points)
            ]
        }

    if operation == "bezier_cubic":
        start, a, b, end = _segment(job)
        ts = _samples(job)
        points = [_bezier_point(start, a, b, end, t) for t in ts]
        tangents = [_bezier_tangent(start, a, b, end, t) for t in ts]
        return {
            "samples": [
                {
                    "t": t,
                    "position": {"x": p[0], "y": p[1], "z": p[2]},
                    "tangent": {"x": d[0], "y": d[1], "z": d[2]},
                }
                for t, p, d in zip(ts, points, tangents)
            ],
            "polylineLength": _length(points),
        }

    if operation == "road_ribbon":
        start, a, b, end = _segment(job)
        width = _finite(job.get("width", 0.78), "width")
        if width <= 0.0:
            raise MathWorkerError("JOB_INVALID", "width must be > 0")
        subdivisions = int(job.get("subdivisions", 32))
        if subdivisions < 2 or subdivisions > 256:
            raise MathWorkerError("JOB_INVALID", "subdivisions must be between 2 and 256")
        repeat = _finite(job.get("textureRepeatWorldUnits", 1.0), "textureRepeatWorldUnits")
        if repeat <= 0.0:
            raise MathWorkerError("JOB_INVALID", "textureRepeatWorldUnits must be > 0")

        vertices: list[dict[str, Any]] = []
        indices: list[int] = []
        previous_center = _bezier_point(start, a, b, end, 0.0)
        accumulated = 0.0
        half = width * 0.5

        for step in range(subdivisions + 1):
            t = step / subdivisions
            center = _bezier_point(start, a, b, end, t)
            tangent = _bezier_tangent(start, a, b, end, t)
            if step:
                accumulated += math.dist(previous_center, center)
            planar = math.hypot(tangent[0], tangent[1])
            if planar <= 1e-7:
                delta = (center[0] - previous_center[0], center[1] - previous_center[1])
                planar = math.hypot(*delta)
                tangent_xy = delta
            else:
                tangent_xy = (tangent[0], tangent[1])
            if planar <= 1e-7:
                tangent_xy = (1.0, 0.0)
                planar = 1.0
            nx = -tangent_xy[1] / planar
            ny = tangent_xy[0] / planar
            u = accumulated / repeat
            left = (center[0] + nx * half, center[1] + ny * half, center[2])
            right = (center[0] - nx * half, center[1] - ny * half, center[2])
            vertices.extend([
                {"x": left[0], "y": left[1], "z": left[2], "u": u, "v": 0.0},
                {"x": right[0], "y": right[1], "z": right[2], "u": u, "v": 1.0},
            ])
            if step:
                base = step * 2
                indices.extend([base - 2, base - 1, base, base, base - 1, base + 1])
            previous_center = center

        return {
            "vertices": vertices,
            "indices": indices,
            "vertexCount": len(vertices),
            "triangleCount": len(indices) // 3,
            "centerlineLength": accumulated,
            "width": width,
        }

    if operation == "terrain_bilinear":
        corners = job.get("corners")
        if not isinstance(corners, dict):
            raise MathWorkerError("JOB_INVALID", "corners must be an object")
        h00 = _finite(corners.get("h00"), "corners.h00")
        h10 = _finite(corners.get("h10"), "corners.h10")
        h11 = _finite(corners.get("h11"), "corners.h11")
        h01 = _finite(corners.get("h01"), "corners.h01")
        u = min(1.0, max(0.0, _finite(job.get("u"), "u")))
        v = min(1.0, max(0.0, _finite(job.get("v"), "v")))
        top = h00 * (1.0 - u) + h10 * u
        bottom = h01 * (1.0 - u) + h11 * u
        return {"height": top * (1.0 - v) + bottom * v, "u": u, "v": v}

    raise MathWorkerError(
        "JOB_INVALID",
        "Unsupported operation",
        {"operation": operation, "supported": [
            "canonical",
            "project_world",
            "screen_to_tile",
            "bezier_cubic",
            "road_ribbon",
            "terrain_bilinear",
        ]},
    )


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise MathWorkerError("JOB_INVALID", "job root must be an object")
    if job.get("contract") != JOB_CONTRACT:
        raise MathWorkerError(
            "CONTRACT_MISMATCH",
            "Unsupported math job contract",
            {"expected": JOB_CONTRACT, "actual": job.get("contract")},
        )
    canonical = _read_contracts()
    result = _operate(job, canonical)
    return {
        "contract": REPORT_CONTRACT,
        "workerContract": WORKER_CONTRACT,
        "jobId": job.get("jobId"),
        "operation": job.get("operation"),
        "canonicalContracts": {
            "grid": canonical.grid_contract,
            "camera": canonical.camera_contract,
            "road": canonical.road_contract,
        },
        "result": result,
    }


def _self_test() -> None:
    canonical = _read_contracts()
    camera = (0.0, 0.0, 1.0, 0)
    viewport = (1280.0, 720.0)
    origin = _world_to_screen((0.0, 0.0, 0.0), canonical, camera, viewport)
    assert origin == {"x": 640.0, "y": 360.0}
    lifted = _world_to_screen((0.0, 0.0, 1.0), canonical, camera, viewport)
    assert lifted["y"] < origin["y"]

    start = (0.0, 0.0, 0.0)
    a = (1.0, 2.0, 0.0)
    b = (3.0, -2.0, 1.0)
    end = (4.0, 0.0, 1.0)
    assert _bezier_point(start, a, b, end, 0.0) == start
    assert _bezier_point(start, a, b, end, 1.0) == end

    report = run_job({
        "contract": JOB_CONTRACT,
        "jobId": "self-test",
        "operation": "road_ribbon",
        "segment": {
            "start": {"x": 0, "y": 0, "z": 0},
            "controlA": {"x": 1, "y": 2, "z": 0},
            "controlB": {"x": 3, "y": -2, "z": 1},
            "end": {"x": 4, "y": 0, "z": 1},
        },
        "subdivisions": 8,
        "width": 0.78,
    })
    assert report["result"]["vertexCount"] == 18
    assert report["result"]["triangleCount"] == 16
    print("PASS CH_MATH_WORKER_V1 self-test")


def _load_job(path: str) -> dict[str, Any]:
    if path == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise MathWorkerError("JOB_INVALID", "job root must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="City Horizon deterministic math worker")
    parser.add_argument("job", nargs="?", help="JSON job path, or '-' for stdin")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    parser.add_argument("--self-test", action="store_true", help="Run dependency-free worker checks")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if not args.job:
        parser.error("job is required unless --self-test is used")

    try:
        report = run_job(_load_job(args.job))
        text = json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=None if args.compact else 2,
            separators=(",", ":") if args.compact else None,
        ) + "\n"
        if args.output:
            output = args.output.resolve()
            try:
                output.relative_to(REPO_ROOT)
            except ValueError as exc:
                raise MathWorkerError("JOB_INVALID", "output must stay inside repository workspace") from exc
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0
    except MathWorkerError as exc:
        error = {
            "contract": REPORT_CONTRACT,
            "workerContract": WORKER_CONTRACT,
            "status": "ERROR",
            "error": {"code": exc.code, "message": str(exc), "details": exc.details},
        }
        sys.stderr.write(json.dumps(error, ensure_ascii=False, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
