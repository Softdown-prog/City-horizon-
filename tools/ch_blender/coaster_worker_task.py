#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PITCH_BINS = (-46.0, -30.0, -14.0, 0.0, 14.0, 30.0, 46.0)
CAR_SPACING_M = 2.445
CAR_COUNT = 4


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("positions", "improve", "validate", "video"))
    p.add_argument("--project", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--samples", type=int, default=128)
    return p.parse_args(argv)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def improved_project(project):
    out = json.loads(json.dumps(project))
    out["projectId"] = "coaster.flame.01.v3"
    out["name"] = "Flame Coaster V3"
    out["captureRequest"] = "ch-blender-worker-pool-v3-video"
    out["workerPoolRevision"] = {
        "contract": "CH_COASTER_WORKER_POOL_REVISION_V1",
        "goal": "stronger hill rhythm and broader train-position validation",
        "preservesClosedPlan": True,
        "poseAtlasContract": "CH_COASTER_CAR_ATLAS_RUNTIME_V2",
    }
    rebuilt = []
    for piece in out["pieces"]:
        pid = piece.get("id")
        if pid == "lift_hill":
            rebuilt.extend([
                {"id":"lift_hill_lower","type":"straight","length":18.0,"rise":5.0,
                 "driveMode":"lift","targetSpeedMps":6.0},
                {"id":"lift_hill_upper","type":"straight","length":24.0,"rise":9.0,
                 "driveMode":"lift","targetSpeedMps":6.0},
            ])
        elif pid == "first_drop":
            rebuilt.extend([
                {"id":"first_drop_entry","type":"straight","length":6.0,"rise":-2.0},
                {"id":"first_drop_main","type":"straight","length":18.0,"rise":-12.0},
            ])
        elif pid == "camelback_up":
            rebuilt.extend([
                {"id":"camelback_up_entry","type":"straight","length":4.0,"rise":0.8},
                {"id":"camelback_up_main","type":"straight","length":8.0,"rise":3.2},
            ])
        elif pid == "camelback_down":
            rebuilt.extend([
                {"id":"camelback_down_main","type":"straight","length":8.0,"rise":-3.2},
                {"id":"camelback_down_exit","type":"straight","length":4.0,"rise":-0.8},
            ])
        elif pid == "second_hill_up":
            rebuilt.extend([
                {"id":"second_hill_up_entry","type":"straight","length":4.0,"rise":0.6},
                {"id":"second_hill_up_main","type":"straight","length":8.0,"rise":2.4},
            ])
        elif pid == "second_hill_down":
            rebuilt.extend([
                {"id":"second_hill_down_main","type":"straight","length":8.0,"rise":-2.4},
                {"id":"second_hill_down_exit","type":"straight","length":4.0,"rise":-0.6},
            ])
        else:
            rebuilt.append(piece)
    out["pieces"] = rebuilt
    return out


def build_route(project):
    start = project["mapForge"]["start"]
    x, y, z = float(start["x"]), float(start["y"]), float(start["z"])
    heading = math.radians(float(start.get("headingDegrees", 0.0)))
    start_xyz = (x, y, z)
    points = [(x, y, z)]
    point_piece = ["start"]

    def push(px, py, pz, pid):
        if points:
            q = points[-1]
            if (px-q[0])**2 + (py-q[1])**2 + (pz-q[2])**2 < 1e-10:
                return
        points.append((px, py, pz))
        point_piece.append(pid)

    for piece in project["pieces"]:
        pid = piece["id"]
        typ = piece["type"]
        if typ == "straight":
            length = float(piece["length"])
            rise = float(piece.get("rise", 0.0))
            samples = max(2, math.ceil(length / 0.5))
            sx, sy, sz = x, y, z
            fx, fy = math.cos(heading), math.sin(heading)
            for i in range(1, samples + 1):
                t = i / samples
                push(sx + fx * length * t, sy + fy * length * t, sz + rise * t, pid)
            x, y, z = sx + fx * length, sy + fy * length, sz + rise
        elif typ == "quarter_curve":
            radius = float(piece["radius"])
            left = bool(piece.get("left", True))
            sign = 1.0 if left else -1.0
            lx, ly = -math.sin(heading), math.cos(heading)
            cx, cy = x + lx * radius * sign, y + ly * radius * sign
            rx, ry = x - cx, y - cy
            for i in range(1, 41):
                a = sign * (math.pi * 0.5) * (i / 40.0)
                c, s = math.cos(a), math.sin(a)
                push(cx + rx*c - ry*s, cy + rx*s + ry*c, z, pid)
            a = sign * (math.pi * 0.5)
            c, s = math.cos(a), math.sin(a)
            x, y = cx + rx*c - ry*s, cy + rx*s + ry*c
            heading += a
        else:
            raise ValueError(f"unsupported coaster piece: {typ}")

    closure = math.dist((x, y, z), start_xyz)
    if closure > 0.02:
        raise ValueError(f"project does not close: {closure:.6f}m")
    if len(points) > 1 and math.dist(points[0], points[-1]) < 1e-6:
        points.pop()
        point_piece.pop()

    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + math.dist(points[i-1], points[i]))
    total = cum[-1] + math.dist(points[-1], points[0])
    return points, point_piece, cum, total, closure


def sample_route(route, d):
    points, point_piece, cum, total, _ = route
    d = d % total
    if d >= cum[-1]:
        a, b = points[-1], points[0]
        seg_start, seg_len = cum[-1], total - cum[-1]
        pid = point_piece[-1]
    else:
        lo, hi = 0, len(cum)-1
        while lo + 1 < hi:
            mid = (lo + hi)//2
            if cum[mid] <= d:
                lo = mid
            else:
                hi = mid
        a, b = points[lo], points[lo+1]
        seg_start, seg_len = cum[lo], cum[lo+1] - cum[lo]
        pid = point_piece[lo+1]
    t = 0.0 if seg_len <= 1e-12 else (d - seg_start) / seg_len
    x = a[0] + (b[0]-a[0])*t
    y = a[1] + (b[1]-a[1])*t
    z = a[2] + (b[2]-a[2])*t
    vx, vy, vz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
    horiz = math.hypot(vx, vy)
    heading = (math.degrees(math.atan2(-vx, vy)) % 360.0) if horiz > 1e-9 else 0.0
    pitch = math.degrees(math.atan2(vz, horiz)) if (horiz > 1e-9 or abs(vz) > 1e-9) else 0.0
    return {"distanceM": d, "pieceId": pid, "x": x, "y": y, "z": z,
            "headingDegrees": heading, "pitchDegrees": pitch, "rollDegrees": 0.0}


def position_catalog(project, samples):
    route = build_route(project)
    total = route[3]
    rows = []
    for i in range(samples):
        lead = total * i / samples
        cars = []
        for car in range(CAR_COUNT):
            s = sample_route(route, lead - car * CAR_SPACING_M)
            s["carIndex"] = car
            cars.append(s)
        rows.append({"sampleIndex": i, "leadDistanceM": lead, "cars": cars})
    return {
        "contract": "CH_COASTER_POSITION_CATALOG_V3",
        "projectId": project["projectId"],
        "routeLengthM": total,
        "leadSamples": samples,
        "carCount": CAR_COUNT,
        "placementCount": samples * CAR_COUNT,
        "carSpacingM": CAR_SPACING_M,
        "positions": rows,
    }


def task_positions(project, outdir, samples):
    payload = position_catalog(project, max(samples, 128))
    write_json(outdir / "car_position_catalog_v3.json", payload)
    write_json(outdir / "worker_summary.json", {
        "contract":"CH_COASTER_WORKER_TASK_REPORT_V1", "task":"positions", "status":"ok",
        "leadSamples":payload["leadSamples"], "placementCount":payload["placementCount"],
        "routeLengthM":payload["routeLengthM"],
    })


def task_improve(project, outdir):
    improved = improved_project(project)
    route = build_route(improved)
    write_json(outdir / "coaster_flame_01_v3.mapforge.json", improved)
    max_z = max(p[2] for p in route[0])
    min_z = min(p[2] for p in route[0])
    write_json(outdir / "track_refinement_report.json", {
        "contract":"CH_COASTER_TRACK_REFINEMENT_REPORT_V1", "status":"ok",
        "sourceProjectId":project["projectId"], "projectId":improved["projectId"],
        "pieceCountBefore":len(project["pieces"]), "pieceCountAfter":len(improved["pieces"]),
        "routeLengthM":route[3], "closureErrorM":route[4],
        "minZM":min_z, "maxZM":max_z,
        "changes":[
            "lift hill raised from 12m to 14m with gentler entry/stronger upper climb",
            "first drop deepened to 14m and split into entry/main transitions",
            "camelback and second hill split into entry/main/exit slope bands",
            "plan-view footprint and closed-route endpoint preserved"
        ]
    })


def task_validate(project, outdir, samples):
    improved = improved_project(project)
    catalog = position_catalog(improved, max(samples, 256))
    max_error = 0.0
    extended = []
    histogram = {}
    for row in catalog["positions"]:
        for car in row["cars"]:
            pitch = car["pitchDegrees"]
            snapped = min(PITCH_BINS, key=lambda v: abs(v-pitch))
            error = abs(pitch-snapped)
            max_error = max(max_error, error)
            histogram[str(snapped)] = histogram.get(str(snapped), 0) + 1
            if error > 8.01:
                extended.append({
                    "sampleIndex":row["sampleIndex"], "carIndex":car["carIndex"],
                    "pieceId":car["pieceId"], "pitchDegrees":pitch,
                    "nearestPitchBin":snapped, "errorDegrees":error
                })
    payload = {
        "contract":"CH_COASTER_POSITION_VALIDATION_V3",
        "status":"pass" if not extended else "fail",
        "projectId":improved["projectId"],
        "leadSamples":catalog["leadSamples"],
        "placementCount":catalog["placementCount"],
        "maxPitchSnapErrorDegrees":max_error,
        "pitchBinHistogram":histogram,
        "extendedOrientationCount":len(extended),
        "extendedOrientations":extended[:64],
        "acceptance":{"maxPitchErrorDegrees":8.01,"rollErrorDegrees":0.0}
    }
    write_json(outdir / "position_validation_v3.json", payload)
    if extended:
        raise SystemExit("position validation requires extended orientation coverage")


def run(cmd):
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=REPO, check=True)


def task_video(project_path, outdir):
    refined = REPO / "out/ch_blender_agent/coaster.flame.v3.02.track_refinement/coaster_flame_01_v3.mapforge.json"
    deadline = time.time() + 300
    while not refined.is_file() and time.time() < deadline:
        print("Worker 4 waiting for Worker 2 refined project...", flush=True)
        time.sleep(2)
    if not refined.is_file():
        raise FileNotFoundError(f"Worker 2 refined project missing: {refined}")

    build = REPO / "build/ch-coaster-v3-worker4"
    temp = REPO / "out/ch_blender_agent/.coaster_v3_video_tmp"
    frames = temp / "frames"
    if temp.exists():
        shutil.rmtree(temp)
    frames.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)

    run(["cmake", "-S", "tools/animation_preview/coaster_video_proof", "-B", build, "-G", "Ninja"])
    run(["cmake", "--build", build, "--target", "MapForge2CoasterVideoProof", "--parallel"])
    renderer = build / "MapForge2CoasterVideoProof"
    atlas = REPO / "assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png"
    run([renderer, frames, atlas, refined])

    capture = load_json(frames / "capture_meta.json")
    frame_count = int(capture["frameCount"])
    video = outdir / "coaster_flame_v3_worker4.mp4"
    sheet = outdir / "contact_sheet_v3.png"
    run(["ffmpeg","-y","-framerate","30","-i",str(frames/"frame_%04d.png"),
         "-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",video])
    interval = max(1, frame_count // 12)
    vf = f"select='not(mod(n\\,{interval}))',scale=640:-1,tile=4x3"
    run(["ffmpeg","-y","-i",video,"-vf",vf,"-frames:v","1",sheet])

    shutil.copy2(refined, outdir / "coaster_flame_01_v3.mapforge.json")
    shutil.copy2(frames / "capture_meta.json", outdir / "capture_meta.json")
    write_json(outdir / "video_report.json", {
        "contract":"CH_COASTER_WORKER4_VIDEO_REPORT_V1", "status":"ok",
        "workerSlot":4, "projectId":"coaster.flame.01.v3",
        "frameCount":frame_count, "fps":30,
        "routeLengthM":capture.get("routeMeters"),
        "lapSeconds":capture.get("lapSeconds"),
        "video":video.name, "contactSheet":sheet.name,
        "sourceWorker":2
    })
    shutil.rmtree(temp, ignore_errors=True)


def main():
    args = parse_args()
    project_path = (REPO / args.project).resolve()
    outdir = (REPO / args.output).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    project = load_json(project_path)
    if project.get("contract") != "CH_MAPFORGE_COASTER_PROJECT_V1":
        raise SystemExit("unsupported coaster project contract")
    if args.task == "positions":
        task_positions(project, outdir, args.samples)
    elif args.task == "improve":
        task_improve(project, outdir)
    elif args.task == "validate":
        task_validate(project, outdir, args.samples)
    else:
        task_video(project_path, outdir)


if __name__ == "__main__":
    main()
