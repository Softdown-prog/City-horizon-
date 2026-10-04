#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "C++/MapForge2/projects/coaster_flame_switchback_02.mapforge.json"
BASE = REPO / "C++/MapForge2/src/coaster_project_video_main.cpp"
PROOF = REPO / "C++/MapForge2/src/coaster_video_proof_main.cpp"
ATLAS = REPO / "assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png"
V5 = REPO / "tools/ch_blender/coaster_switchback_v5_pool.py"
TRACK_WORKER = REPO / "tools/ch_blender/coaster_track_geometry_video_worker4.py"
TRACK_OUT = REPO / "out/ch_blender_agent/coaster.flame.switchback.v5.08.01.track"
STATION_OUT = REPO / "out/ch_blender_agent/coaster.flame.switchback.v5.08.02.station"
TRAIN_OUT = REPO / "out/ch_blender_agent/coaster.flame.switchback.v5.08.03.train"
TRACK_FILE = TRACK_OUT / "track_function_v508.cpp"
STATION_FILE = STATION_OUT / "station_function_v508.cpp"
TRAIN_FILE = TRAIN_OUT / "coaster_video_proof_main_v508.cpp"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("track", "station", "train", "video"))
    p.add_argument("--project", default=str(PROJECT.relative_to(REPO)))
    p.add_argument("--output", required=True)
    return p.parse_args(argv)


def repo_path(value):
    path = Path(value)
    path = (path if path.is_absolute() else REPO / path).resolve()
    path.relative_to(REPO)
    return path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=REPO, check=True)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.relative_to(REPO)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_function(source, start_marker, end_marker, replacement):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


TRACK_FUNCTION = r'''void draw_track(QPainter& painter, const Projection& projection,
                const ch::coaster::CenterlineRoute& route) {
    ch::coaster::CoasterTrackStyle style{};
    const auto geometry = ch::coaster::build_coaster_track_geometry(route, style);
    if (!geometry.valid()) return;

    QPainterPath groundShadow, underside, spine, railLeft, railRight;
    bool first = true;
    for (const auto& frame : geometry.frames) {
        const QPointF shadow = projection.map(frame.center.x + 0.32, frame.center.y + 0.32, 0.02);
        const QPointF under = projection.map(frame.spine.x, frame.spine.y, frame.spine.z - 0.10);
        const QPointF center = projection.map(frame.spine.x, frame.spine.y, frame.spine.z);
        const QPointF left = projection.map(frame.left_rail.x, frame.left_rail.y, frame.left_rail.z);
        const QPointF right = projection.map(frame.right_rail.x, frame.right_rail.y, frame.right_rail.z);
        if (first) {
            groundShadow.moveTo(shadow); underside.moveTo(under); spine.moveTo(center);
            railLeft.moveTo(left); railRight.moveTo(right); first = false;
        } else {
            groundShadow.lineTo(shadow); underside.lineTo(under); spine.lineTo(center);
            railLeft.lineTo(left); railRight.lineTo(right);
        }
    }

    painter.setBrush(Qt::NoBrush);
    QPen groundPen(QColor(22, 35, 24, 50)); groundPen.setWidthF(8.0);
    groundPen.setCapStyle(Qt::RoundCap); groundPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(groundPen); painter.drawPath(groundShadow);

    QPen underOutline(QColor(55, 24, 23)); underOutline.setWidthF(10.0);
    underOutline.setCapStyle(Qt::RoundCap); underOutline.setJoinStyle(Qt::RoundJoin);
    painter.setPen(underOutline); painter.drawPath(underside);
    QPen underBody(QColor(92, 31, 28)); underBody.setWidthF(7.2);
    underBody.setCapStyle(Qt::RoundCap); underBody.setJoinStyle(Qt::RoundJoin);
    painter.setPen(underBody); painter.drawPath(underside);

    QPen spineOutline(QColor(76, 25, 22)); spineOutline.setWidthF(9.0);
    spineOutline.setCapStyle(Qt::RoundCap); spineOutline.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spineOutline); painter.drawPath(spine);
    QPen spineBody(QColor(181, 55, 43)); spineBody.setWidthF(6.2);
    spineBody.setCapStyle(Qt::RoundCap); spineBody.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spineBody); painter.drawPath(spine);
    QPen spineHighlight(QColor(210, 79, 57, 190)); spineHighlight.setWidthF(1.4);
    spineHighlight.setCapStyle(Qt::RoundCap); spineHighlight.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spineHighlight); painter.drawPath(spine);

    QPen tieOutline(QColor(38, 42, 45)); tieOutline.setWidthF(4.8); tieOutline.setCapStyle(Qt::RoundCap);
    QPen tieBody(QColor(99, 105, 109)); tieBody.setWidthF(2.9); tieBody.setCapStyle(Qt::RoundCap);
    for (const auto& tie : geometry.ties) {
        const QPointF a = projection.map(tie.left.x, tie.left.y, tie.left.z);
        const QPointF b = projection.map(tie.right.x, tie.right.y, tie.right.z);
        painter.setPen(tieOutline); painter.drawLine(a, b);
        painter.setPen(tieBody); painter.drawLine(a, b);
    }

    QPen railShadow(QColor(67, 74, 79)); railShadow.setWidthF(5.2);
    railShadow.setCapStyle(Qt::RoundCap); railShadow.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railShadow); painter.drawPath(railLeft); painter.drawPath(railRight);
    QPen railBody(QColor(225, 230, 233)); railBody.setWidthF(3.2);
    railBody.setCapStyle(Qt::RoundCap); railBody.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railBody); painter.drawPath(railLeft); painter.drawPath(railRight);
    QPen railHighlight(QColor(248, 250, 251, 205)); railHighlight.setWidthF(1.0);
    railHighlight.setCapStyle(Qt::RoundCap); railHighlight.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railHighlight); painter.drawPath(railLeft); painter.drawPath(railRight);

    QPen liftPen(QColor(238, 181, 56)); liftPen.setWidthF(2.2);
    QPen brakePen(QColor(39, 42, 44)); brakePen.setWidthF(3.2);
    for (std::size_t i = 0; i < geometry.ties.size(); i += 4U) {
        const auto& tie = geometry.ties[i];
        const auto sample = route.sample(tie.distance_m);
        if (!sample) continue;
        const auto marker = ch::coaster::track_point(*sample, 0.0, 0.16);
        const QPointF p = projection.map(marker.x, marker.y, marker.z);
        if (sample->drive_mode == ch::coaster::DriveMode::Lift) {
            painter.setPen(liftPen); painter.drawEllipse(p, 1.8, 1.8);
        } else if (sample->drive_mode == ch::coaster::DriveMode::Brake) {
            painter.setPen(brakePen);
            painter.drawLine(p + QPointF(-2.6, -1.4), p + QPointF(2.6, 1.4));
        }
    }
}'''

STATION_FUNCTION = r'''void draw_station(QPainter& painter, const Projection& p) {
    QPolygonF platform;
    platform << p.map(8.6,-3.45,0.03) << p.map(26.4,-3.45,0.03)
             << p.map(26.4,3.45,0.03) << p.map(8.6,3.45,0.03);
    painter.setPen(QPen(QColor(70, 53, 43), 2.2)); painter.setBrush(QColor(190, 154, 108));
    painter.drawPolygon(platform);
    QPolygonF inset;
    inset << p.map(9.15,-2.85,0.07) << p.map(25.85,-2.85,0.07)
          << p.map(25.85,2.85,0.07) << p.map(9.15,2.85,0.07);
    painter.setPen(QPen(QColor(92, 68, 52), 1.3)); painter.setBrush(QColor(213, 181, 132));
    painter.drawPolygon(inset);

    QPen safetyEdge(QColor(233, 178, 54)); safetyEdge.setWidthF(3.2); safetyEdge.setCapStyle(Qt::RoundCap);
    painter.setPen(safetyEdge);
    painter.drawLine(p.map(9.0,-2.45,0.10), p.map(26.0,-2.45,0.10));
    painter.drawLine(p.map(9.0, 2.45,0.10), p.map(26.0, 2.45,0.10));

    QPen postOutline(QColor(49, 36, 32)); postOutline.setWidthF(5.2);
    QPen postBody(QColor(104, 70, 51)); postBody.setWidthF(3.1);
    for (double x : {9.8, 15.1, 20.4, 25.7}) {
        for (double y : {-2.75, 2.75}) {
            const QPointF a = p.map(x, y, 0.08), b = p.map(x, y, 2.55);
            painter.setPen(postOutline); painter.drawLine(a, b);
            painter.setPen(postBody); painter.drawLine(a, b);
        }
    }

    QPolygonF roofNear;
    roofNear << p.map(9.15,-3.25,2.48) << p.map(26.15,-3.25,2.48)
             << p.map(26.15,0.0,3.42) << p.map(9.15,0.0,3.42);
    QPolygonF roofFar;
    roofFar << p.map(9.15,0.0,3.42) << p.map(26.15,0.0,3.42)
            << p.map(26.15,3.25,2.48) << p.map(9.15,3.25,2.48);
    painter.setPen(QPen(QColor(65, 22, 20), 2.5));
    painter.setBrush(QColor(159, 44, 35)); painter.drawPolygon(roofNear);
    painter.setBrush(QColor(126, 32, 29)); painter.drawPolygon(roofFar);
    QPen ridge(QColor(238, 183, 58)); ridge.setWidthF(3.4); ridge.setCapStyle(Qt::RoundCap);
    painter.setPen(ridge); painter.drawLine(p.map(9.15,0.0,3.45), p.map(26.15,0.0,3.45));
    QPen eave(QColor(94, 29, 25)); eave.setWidthF(3.0); painter.setPen(eave);
    painter.drawLine(p.map(9.15,-3.25,2.50), p.map(26.15,-3.25,2.50));
    painter.drawLine(p.map(9.15, 3.25,2.50), p.map(26.15, 3.25,2.50));

    QPen rail(QColor(77, 80, 82)); rail.setWidthF(2.2); painter.setPen(rail);
    for (double y : {-3.05, 3.05}) {
        painter.drawLine(p.map(9.15,y,0.78), p.map(12.3,y,0.78));
        painter.drawLine(p.map(13.6,y,0.78), p.map(21.4,y,0.78));
        painter.drawLine(p.map(22.7,y,0.78), p.map(25.85,y,0.78));
        for (double x : {9.15,12.3,13.6,17.5,21.4,22.7,25.85})
            painter.drawLine(p.map(x,y,0.10), p.map(x,y,0.85));
    }

    const QPointF sign = p.map(10.0,-3.35,1.95);
    painter.setPen(QPen(QColor(239, 184, 57), 2.0)); painter.setBrush(QColor(91, 29, 26));
    painter.drawRoundedRect(QRectF(sign.x()-22.0, sign.y()-8.5, 44.0, 17.0), 3.0, 3.0);
}'''


def task_track(out):
    out.mkdir(parents=True, exist_ok=True)
    (out / TRACK_FILE.name).write_text(TRACK_FUNCTION + "\n", encoding="utf-8")
    write_json(out / "track_report.json", {
        "contract": "CH_COASTER_PRESENTATION_TRACK_V508", "status": "ok",
        "usesRuntimeTrackGeometry": True, "preservesCenterline": True,
        "preservesSupportGeometry": True,
        "changes": ["layered underside and central box-spine silhouette", "stronger cross-tie outline/body separation", "three-pass steel rail rendering with highlight", "clearer lift-chain and brake markers"]})
    write_json(out / "worker_summary.json", {"contract": "CH_COASTER_WORKER_TASK_REPORT_V2", "task": "track_presentation", "status": "ok"})


def task_station(out):
    out.mkdir(parents=True, exist_ok=True)
    (out / STATION_FILE.name).write_text(STATION_FUNCTION + "\n", encoding="utf-8")
    write_json(out / "station_report.json", {
        "contract": "CH_COASTER_PRESENTATION_STATION_V508", "status": "ok",
        "changes": ["larger raised platform with inset floor", "four post pairs and pitched two-slope roof", "eaves and gold roof ridge", "platform safety edges", "queue railings with deliberate entry and exit gaps", "framed entrance sign without baked text"]})
    write_json(out / "worker_summary.json", {"contract": "CH_COASTER_WORKER_TASK_REPORT_V2", "task": "station_presentation", "status": "ok"})


def patch_train_source(source):
    old_scale = "constexpr double kSpriteScaleCoefficient = 0.0425;"
    if old_scale not in source:
        raise RuntimeError("V5 train scale marker missing")
    source = source.replace(old_scale, "constexpr double kSpriteScaleCoefficient = 0.0440;", 1)
    old_draw = "        painter.drawImage(dst, atlas, src);"
    new_draw = r'''        const int atlasColumn = r.x / ch::coaster::kCarPoseFrameWidth;
        const int atlasRow = r.y / ch::coaster::kCarPoseFrameHeight;
        const int atlasIndex = atlasRow * ch::coaster::kCarPoseAtlasColumns + atlasColumn;
        static std::array<QImage, ch::coaster::kCarPoseFrameCount> silhouetteCache{};
        static std::array<bool, ch::coaster::kCarPoseFrameCount> silhouetteReady{};
        if (atlasIndex >= 0 && atlasIndex < ch::coaster::kCarPoseFrameCount) {
            const auto cacheIndex = static_cast<std::size_t>(atlasIndex);
            if (!silhouetteReady[cacheIndex]) {
                QImage silhouette = atlas.copy(src).convertToFormat(QImage::Format_ARGB32_Premultiplied);
                QPainter silhouettePainter(&silhouette);
                silhouettePainter.setCompositionMode(QPainter::CompositionMode_SourceIn);
                silhouettePainter.fillRect(silhouette.rect(), QColor(18, 22, 24, 175));
                silhouettePainter.end();
                silhouetteCache[cacheIndex] = silhouette;
                silhouetteReady[cacheIndex] = true;
            }
            painter.drawImage(dst.translated(1.5, 1.8), silhouetteCache[cacheIndex], QRectF(silhouetteCache[cacheIndex].rect()));
        }
        painter.drawImage(dst, atlas, src);'''
    if old_draw not in source:
        raise RuntimeError("V5 train draw marker missing")
    return source.replace(old_draw, new_draw, 1)


def task_train(out):
    out.mkdir(parents=True, exist_ok=True)
    v5 = load_module(V5, "ch_switchback_v5_for_v508_train")
    tmp = out / ".motion_tmp"
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    v5.motion(tmp)
    generated = tmp / "coaster_video_proof_main_v5.cpp"
    if not generated.is_file(): raise RuntimeError("V5 motion source was not regenerated")
    (out / TRAIN_FILE.name).write_text(patch_train_source(generated.read_text(encoding="utf-8")), encoding="utf-8")
    write_json(out / "train_report.json", {
        "contract": "CH_COASTER_PRESENTATION_TRAIN_V508", "status": "ok",
        "motionModel": "CH_COASTER_PHYSICS_V1", "preservesPhysics": True,
        "preservesRailAnchor": True, "spriteScaleCoefficient": 0.0440,
        "changes": ["slightly larger train for isometric readability", "cached alpha-silhouette drop shadow behind occupied atlas poses", "no change to longitudinal physics, pose contract or rail anchor"]})
    write_json(out / "worker_summary.json", {"contract": "CH_COASTER_WORKER_TASK_REPORT_V2", "task": "train_presentation", "status": "ok"})
    shutil.rmtree(tmp)


def wait_for(paths):
    deadline = time.time() + 300.0
    while time.time() < deadline:
        missing = [path for path in paths if not path.is_file()]
        if not missing: return
        print("Worker 4 waiting:", ",".join(str(path.relative_to(REPO)) for path in missing), flush=True)
        time.sleep(2.0)
    raise FileNotFoundError("V5.08 worker dependencies missing")


def task_video(source_project, out):
    wait_for([TRACK_FILE, STATION_FILE, TRAIN_FILE])
    out.mkdir(parents=True, exist_ok=True)
    v5 = load_module(V5, "ch_switchback_v5_for_v508_video")
    track_worker = load_module(TRACK_WORKER, "ch_track_geometry_for_v508")
    tmp = REPO / "out/ch_blender_agent/.coaster_switchback_v508_video_tmp"
    build = REPO / "build/ch-coaster-switchback-v508-worker4"
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    geometry_dir, structure_dir, frames = tmp / "geometry", tmp / "structure", tmp / "frames"
    frames.mkdir(parents=True)
    v5.geometry(source_project, geometry_dir)
    v5.structure(structure_dir)
    project = geometry_dir / "coaster_flame_switchback_04.mapforge.json"
    structure = structure_dir / "coaster_project_video_main_v5.cpp"
    if not project.is_file() or not structure.is_file(): raise RuntimeError("V5.08 integration inputs were not regenerated")

    base_source = track_worker.patch_track_source(structure.read_text(encoding="utf-8"))
    base_source = replace_function(base_source, "void draw_track(", "void draw_station(", TRACK_FILE.read_text(encoding="utf-8"))
    base_source = replace_function(base_source, "void draw_station(", "void draw_train(", STATION_FILE.read_text(encoding="utf-8"))
    proof_source = track_worker.patch_proof_source(TRAIN_FILE.read_text(encoding="utf-8"))
    integrated_base, integrated_proof = tmp / "coaster_project_video_main_v508.cpp", tmp / "coaster_video_proof_main_v508.cpp"
    integrated_base.write_text(base_source, encoding="utf-8")
    integrated_proof.write_text(proof_source, encoding="utf-8")
    original_base, original_proof = tmp / "original_base.cpp", tmp / "original_proof.cpp"
    shutil.copy2(BASE, original_base); shutil.copy2(PROOF, original_proof)
    try:
        shutil.copy2(integrated_base, BASE); shutil.copy2(integrated_proof, PROOF)
        run(["cmake", "-S", "tools/animation_preview/coaster_video_proof", "-B", build, "-G", "Ninja"])
        run(["cmake", "--build", build, "--target", "MapForge2CoasterVideoProof", "--parallel"])
        renderer = build / "MapForge2CoasterVideoProof"
        run([renderer, frames, ATLAS, project])
        capture = load_json(frames / "capture_meta.json"); frame_count = int(capture["frameCount"])
        mp4 = out / "coaster_flame_switchback_v5_08_worker4.mp4"
        sheet = out / "contact_sheet_switchback_v5_08.png"
        run(["ffmpeg", "-y", "-framerate", "30", "-i", frames / "frame_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4])
        interval = max(1, frame_count // 12); vf = f"select='not(mod(n\\,{interval}))',scale=640:-1,tile=4x3"
        run(["ffmpeg", "-y", "-i", mp4, "-vf", vf, "-frames:v", "1", "-update", "1", sheet])
        shutil.copy2(frames / "capture_meta.json", out / "capture_meta.json")
        shutil.copy2(project, out / "coaster_flame_switchback_04.mapforge.json")
        write_json(out / "presentation_report.json", {
            "contract": "CH_COASTER_PRESENTATION_VIDEO_V508", "status": "ok", "projectId": "coaster.flame.switchback.04",
            "sourceRevision": "Flame Switchback V5.08", "frameCount": frame_count, "fps": 30,
            "routeLengthM": capture.get("routeMeters"), "lapSeconds": capture.get("lapSeconds"), "motionModel": capture.get("motionModel"),
            "usesRuntimeTrackGeometry": True, "preservesV507Supports": True,
            "integratedWorkers": ["track_presentation", "station_presentation", "train_presentation"],
            "video": mp4.name, "contactSheet": sheet.name})
        write_json(out / "worker_summary.json", {"contract": "CH_COASTER_WORKER_TASK_REPORT_V2", "task": "presentation_video", "status": "ok"})
    finally:
        shutil.copy2(original_base, BASE); shutil.copy2(original_proof, PROOF)


def main():
    args = parse_args(); out = repo_path(args.output)
    if args.task == "track": task_track(out)
    elif args.task == "station": task_station(out)
    elif args.task == "train": task_train(out)
    else: task_video(repo_path(args.project), out)


if __name__ == "__main__":
    main()
