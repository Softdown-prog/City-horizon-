#!/usr/bin/env python3
"""Deterministic visual proof for the articulated City Horizon steam train.

This is a review render, not a gameplay capture. It consumes the promoted runtime
unit sprites, places one locomotive plus seven coaches on one sampled closed route,
and exports both MP4 and GIF so articulation, spacing, direction changes and station
dwell can be reviewed before replacing the procedural fallback in the live renderer.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import bpy

REPO_ROOT = Path(__file__).resolve().parents[2]
FPS = 12
FRAME_COUNT = 96
LOCOMOTIVE_LENGTH_M = 5.2
COACH_LENGTH_M = 3.9
COUPLING_GAP_M = 0.42
COACH_COUNT = 7


def args_after_separator() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    return parser.parse_args(args_after_separator())


def load_manifest(relative: str) -> dict:
    path = REPO_ROOT / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "CH_RUNTIME_VEHICLE_TRAIN_UNIT_V1" or data.get("approvedForRuntime") is not True:
        raise RuntimeError(f"Unapproved articulated train manifest: {path}")
    return data


def runtime_views(manifest: dict, root: Path) -> dict[str, Path]:
    views: dict[str, Path] = {}
    for direction, record in manifest["views"].items():
        source = (root / record["file"]).resolve()
        if not source.is_file():
            raise RuntimeError(f"Missing runtime sprite: {source}")
        views[direction] = source
    return views


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)


def material_color(name: str, rgba: tuple[float, float, float, float]):
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    return material


def add_flat_box(name: str, x: float, y: float, sx: float, sy: float, z: float, material) -> None:
    bpy.ops.mesh.primitive_cube_add(location=(x, y, z), scale=(sx / 2.0, sy / 2.0, 0.03))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)


def route_point(theta: float) -> tuple[float, float]:
    return 11.0 * math.cos(theta), 6.1 * math.sin(theta)


def build_route(samples: int = 1400):
    points = [route_point((i / samples) * math.tau) for i in range(samples + 1)]
    cumulative = [0.0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return points, cumulative


def sample_route(points, cumulative, distance: float):
    total = cumulative[-1]
    d = distance % total
    lo, hi = 0, len(cumulative) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if cumulative[mid] <= d:
            lo = mid
        else:
            hi = mid
    span = max(1e-9, cumulative[lo + 1] - cumulative[lo])
    f = (d - cumulative[lo]) / span
    a, b = points[lo], points[lo + 1]
    x = a[0] + (b[0] - a[0]) * f
    y = a[1] + (b[1] - a[1]) * f
    tx, ty = b[0] - a[0], b[1] - a[1]
    length = max(1e-9, math.hypot(tx, ty))
    return x, y, tx / length, ty / length


def direction_for(tx: float, ty: float) -> str:
    if abs(tx) >= abs(ty):
        return "east" if tx >= 0 else "west"
    return "north" if ty >= 0 else "south"


def make_sprite_material(name: str, image_path: Path):
    image = bpy.data.images.load(str(image_path), check_existing=False)
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    texture = nodes.new("ShaderNodeTexImage")
    mix = nodes.new("ShaderNodeMixShader")
    texture.image = image
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(texture.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    return material


def add_sprite_plane(name: str, image_path: Path, length_world: float, z: float):
    material = make_sprite_material(name + "_mat", image_path)
    width = max(1.7, length_world)
    height = max(1.5, length_world * 0.72)
    mesh = bpy.data.meshes.new(name + "_mesh")
    verts = [(-width/2, -height/2, 0), (width/2, -height/2, 0), (width/2, height/2, 0), (-width/2, height/2, 0)]
    mesh.from_pydata(verts, [], [(0,1,2,3)])
    uv = mesh.uv_layers.new(name="UVMap")
    coords = [(0,0), (1,0), (1,1), (0,1)]
    for loop, coord in zip(uv.data, coords):
        loop.uv = coord
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location.z = z
    obj.data.materials.append(material)
    return obj


def create_unit(index: int, role: str, views: dict[str, Path], length_world: float):
    variants = {}
    for direction in ("south", "east", "west", "north"):
        obj = add_sprite_plane(f"unit_{index:02d}_{direction}", views[direction], length_world, 0.5 + index * 0.002)
        variants[direction] = obj
    return {"role": role, "variants": variants}


def key_bool(obj, attr: str, value: bool, frame: int) -> None:
    setattr(obj, attr, value)
    obj.keyframe_insert(data_path=attr, frame=frame, options={"INSERTKEY_NEEDED"})


def movement_distance(frame: int, total: float) -> float:
    u = (frame - 1) / max(1, FRAME_COUNT - 1)
    if u < 0.38:
        progress = (u / 0.38) * 0.48
    elif u < 0.52:
        progress = 0.48
    else:
        progress = 0.48 + ((u - 0.52) / 0.48) * 0.52
    return progress * total


def encode_video(frames_dir: Path, output: Path) -> tuple[Path, Path]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for MP4/GIF proof encoding")
    source = str(frames_dir / "frame_%04d.png")
    mp4_path = output / "steam_train_articulated.mp4"
    gif_path = output / "steam_train_articulated.gif"
    subprocess.run([
        ffmpeg, "-y", "-framerate", str(FPS), "-i", source,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(mp4_path),
    ], check=True)
    subprocess.run([
        ffmpeg, "-y", "-framerate", str(FPS), "-i", source,
        "-vf", "fps=12,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
        "-loop", "0", str(gif_path),
    ], check=True)
    return mp4_path, gif_path


def main() -> None:
    args = parse_args()
    output = (REPO_ROOT / args.output).resolve()
    if not output.is_relative_to(REPO_ROOT):
        raise RuntimeError("Output must stay inside the repository workspace")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    loco_manifest = load_manifest("assets/vehicles/steam_train_locomotive_01/steam_train_unit_runtime.json")
    coach_manifest = load_manifest("assets/vehicles/steam_train_coach_01/steam_train_unit_runtime.json")
    loco_views = runtime_views(loco_manifest, REPO_ROOT / "assets/vehicles/steam_train_locomotive_01")
    coach_views = runtime_views(coach_manifest, REPO_ROOT / "assets/vehicles/steam_train_coach_01")

    clear_scene()
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = FRAME_COUNT
    scene.render.fps = FPS
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.world.color = (0.11, 0.16, 0.11)

    bpy.ops.object.camera_add(location=(0, 0, 28))
    camera = bpy.context.object
    camera.rotation_euler = (0, 0, 0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 28.0
    scene.camera = camera

    grass = material_color("grass", (0.31, 0.43, 0.24, 1.0))
    ballast = material_color("ballast", (0.19, 0.17, 0.15, 1.0))
    sleeper = material_color("sleeper", (0.25, 0.16, 0.10, 1.0))
    rail = material_color("rail", (0.60, 0.62, 0.61, 1.0))
    platform = material_color("platform", (0.54, 0.49, 0.40, 1.0))
    add_flat_box("ground", 0, 0, 32, 20, -0.25, grass)

    points, cumulative = build_route()
    total = cumulative[-1]
    for i in range(96):
        d = total * i / 96.0
        x, y, tx, ty = sample_route(points, cumulative, d)
        nx, ny = -ty, tx
        add_flat_box(f"ballast_{i:03d}", x, y, 0.78, 0.38, 0.0, ballast)
        angle = math.atan2(ty, tx)
        bpy.context.object.rotation_euler.z = angle
        if i % 2 == 0:
            add_flat_box(f"sleeper_{i:03d}", x, y, 0.18, 1.05, 0.05, sleeper)
            bpy.context.object.rotation_euler.z = angle
        for side in (-0.29, 0.29):
            rx, ry = x + nx * side, y + ny * side
            add_flat_box(f"rail_{i:03d}_{side:+.0f}", rx, ry, 0.34, 0.07, 0.09, rail)
            bpy.context.object.rotation_euler.z = angle

    station_d = total * 0.48
    sx, sy, stx, sty = sample_route(points, cumulative, station_d)
    snx, sny = -sty, stx
    add_flat_box("station_platform", sx + snx * 1.3, sy + sny * 1.3, 5.6, 1.3, 0.08, platform)
    bpy.context.object.rotation_euler.z = math.atan2(sty, stx)

    units = [create_unit(0, "locomotive", loco_views, 3.7)]
    for i in range(COACH_COUNT):
        units.append(create_unit(i + 1, "coach", coach_views, 3.0))

    offsets = [0.0]
    offsets.append(LOCOMOTIVE_LENGTH_M / 2.0 + COUPLING_GAP_M + COACH_LENGTH_M / 2.0)
    for _ in range(1, COACH_COUNT):
        offsets.append(offsets[-1] + COACH_LENGTH_M + COUPLING_GAP_M)

    for frame in range(1, FRAME_COUNT + 1):
        head = movement_distance(frame, total)
        for unit_index, unit in enumerate(units):
            x, y, tx, ty = sample_route(points, cumulative, head - offsets[unit_index])
            direction = direction_for(tx, ty)
            for key, obj in unit["variants"].items():
                obj.location.x = x
                obj.location.y = y
                obj.keyframe_insert(data_path="location", frame=frame, options={"INSERTKEY_NEEDED"})
                key_bool(obj, "hide_render", key != direction, frame)

    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(frames_dir / "frame_")
    bpy.ops.render.render(animation=True)

    mp4_path, gif_path = encode_video(frames_dir, output)
    report = {
        "contract": "CH_RAIL_ARTICULATED_VISUAL_PROOF_V1",
        "status": "success",
        "captureType": "deterministic_visual_proof_not_gameplay_capture",
        "fps": FPS,
        "frames": FRAME_COUNT,
        "consist": {"locomotives": 1, "coaches": COACH_COUNT, "couplingGapM": COUPLING_GAP_M},
        "stationDwellIncluded": True,
        "outputs": {"mp4": mp4_path.name, "gif": gif_path.name},
    }
    (output / "visual_proof_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
