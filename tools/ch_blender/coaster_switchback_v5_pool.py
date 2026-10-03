#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO/'C++/MapForge2/projects/coaster_flame_switchback_02.mapforge.json'
BASE = REPO/'C++/MapForge2/src/coaster_project_video_main.cpp'
PROOF = REPO/'C++/MapForge2/src/coaster_video_proof_main.cpp'
GOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v5.01.geometry'
SOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v5.02.structure'
MOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v5.03.motion'
BINS = (-46.,-30.,-14.,0.,14.,30.,46.)

def args():
    av = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument('--task', required=True, choices=('geometry','structure','motion','video'))
    p.add_argument('--project', default=str(PROJECT.relative_to(REPO)))
    p.add_argument('--output', required=True)
    return p.parse_args(av)

def rp(v):
    p = Path(v)
    p = (p if p.is_absolute() else REPO/p).resolve()
    p.relative_to(REPO)
    return p

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, indent=2, sort_keys=True)+'\n', encoding='utf-8')
def run(cmd):
    print('+', ' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), cwd=REPO, check=True)
def st(i, l, r, **kw):
    x = {'id': i, 'type': 'straight', 'length': l, 'rise': r}
    x.update(kw)
    return x

def geometry(src, out):
    p = load(src)
    p['projectId'] = 'coaster.flame.switchback.04'
    p['assetId'] = 'ride.coaster_flame_switchback_04'
    p['name'] = 'Flame Switchback V5'
    p['captureRequest'] = 'switchback-v5-worker-pool-2026-10-03'
    p['workerPoolRevision'] = {
        'contract': 'CH_COASTER_WORKER_POOL_REVISION_V2',
        'revision': 5,
        'preservesClosedPlan': True,
        'poseAtlasContract': 'CH_COASTER_CAR_ATLAS_RUNTIME_V2',
    }
    repl = {
        'lift_hill': [
            st('lift_entry', 4, 1, driveMode='lift', targetSpeedMps=4.8),
            st('lift_transition', 6, 3, driveMode='lift', targetSpeedMps=5.2),
            st('lift_main', 10, 6, driveMode='lift', targetSpeedMps=5.6),
        ],
        'first_drop': [
            st('first_drop_entry', 4, -1),
            st('first_drop_main', 10, -7),
            st('first_drop_exit', 6, -2),
        ],
        'airtime_climb': [
            st('airtime_entry', 6, 2),
            st('airtime_crest', 8, 3),
            st('airtime_release', 6, -1),
        ],
        'mid_run': [
            st('mid_drop_entry', 6, -1),
            st('mid_drop_main', 8, -2),
            st('mid_drop_exit', 6, -1),
        ],
        'second_climb': [
            st('second_climb_entry', 6, 1),
            st('second_climb_main', 8, 3),
            st('second_climb_release', 6, 1),
        ],
        'second_drop': [
            st('second_drop_entry', 6, -1),
            st('second_drop_main', 8, -3),
            st('second_drop_exit', 6, -1),
        ],
        'brake_descent': [
            st('brake_entry', 6, 0, driveMode='brake', targetSpeedMps=7.0),
            st('brake_main', 8, 0, driveMode='brake', targetSpeedMps=6.2),
            st('brake_exit', 6, 0, driveMode='brake', targetSpeedMps=5.5),
        ],
    }
    q = []
    for x in p['pieces']:
        q.extend(repl.get(x.get('id'), [x]))
    p['pieces'] = q

    worst = 0.0
    for x in q:
        if x.get('type') != 'straight':
            continue
        pitch = math.degrees(math.atan2(float(x.get('rise', 0)), float(x['length'])))
        err = min(abs(pitch-b) for b in BINS)
        worst = max(worst, err)
        if err > 8.01:
            raise RuntimeError(f"pose coverage {x['id']} error={err:.3f}")

    dst = out/'coaster_flame_switchback_04.mapforge.json'
    write(dst, p)
    write(out/'geometry_report.json', {
        'contract': 'CH_COASTER_GEOMETRY_REFINEMENT_V5',
        'status': 'ok',
        'projectId': p['projectId'],
        'pieceCount': len(q),
        'maxPitchSnapErrorDegrees': worst,
        'changes': [
            'progressive three-stage lift',
            'entry-main-exit first drop',
            'first camelback rises 4m then drops 4m before the second hill',
            'second camelback rises 5m and returns to ground level',
            'flat three-stage brake run for physically plausible energy flow',
        ],
    })
    write(out/'worker_summary.json', {
        'contract': 'CH_COASTER_WORKER_TASK_REPORT_V2',
        'task': 'geometry',
        'status': 'ok',
    })

def structure(out):
    s = BASE.read_text(encoding='utf-8')
    if 'constexpr double kSupportSpacingM = 3.0;' not in s:
        raise RuntimeError('support spacing marker missing')
    s = s.replace('constexpr double kSupportSpacingM = 3.0;',
                  'constexpr double kSupportSpacingM = 5.2;', 1)

    a = s.index('void draw_supports(')
    b = s.index('void draw_track(', a)
    sup = r'''void draw_supports(QPainter& painter, const Projection& projection,
                   const ch::coaster::CenterlineRoute& route) {
    QPainterPath shadow;
    bool shadowFirst = true;
    for (double d = 0.0; d < route.length_m(); d += 0.55) {
        const auto s = route.sample(d);
        if (!s) continue;
        const QPointF p = projection.map(s->x + 0.35, s->y + 0.35, 0.02);
        if (shadowFirst) { shadow.moveTo(p); shadowFirst = false; }
        else shadow.lineTo(p);
    }
    QPen shadowPen(QColor(24, 43, 25, 60));
    shadowPen.setWidthF(7.0);
    shadowPen.setCapStyle(Qt::RoundCap);
    shadowPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(shadowPen);
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(shadow);

    QPen outline(QColor(48, 52, 55)); outline.setWidthF(5.4);
    QPen steel(QColor(115, 124, 129)); steel.setWidthF(3.1);
    QPen brace(QColor(82, 91, 96)); brace.setWidthF(2.2);

    for (double d = 0.0; d < route.length_m(); d += kSupportSpacingM) {
        const auto s = route.sample(d);
        if (!s || s->z < 0.85) continue;
        const double l = std::hypot(s->tangent_x, s->tangent_y);
        const double nx = l > 1.0e-6 ? -s->tangent_y / l : -1.0;
        const double ny = l > 1.0e-6 ?  s->tangent_x / l :  0.0;
        const double footSpread = 0.95 + std::min(1.55, s->z * 0.09);
        const double topSpread = 0.48;

        const QPointF ta = projection.map(s->x + nx*topSpread, s->y + ny*topSpread, s->z - 0.12);
        const QPointF tb = projection.map(s->x - nx*topSpread, s->y - ny*topSpread, s->z - 0.12);
        const QPointF fa = projection.map(s->x + nx*footSpread, s->y + ny*footSpread, 0.02);
        const QPointF fb = projection.map(s->x - nx*footSpread, s->y - ny*footSpread, 0.02);

        painter.setPen(outline);
        painter.drawLine(ta, fa); painter.drawLine(tb, fb); painter.drawLine(ta, tb);
        painter.setPen(steel);
        painter.drawLine(ta, fa); painter.drawLine(tb, fb); painter.drawLine(ta, tb);

        if (s->z > 2.2) {
            painter.setPen(brace);
            painter.drawLine(fa, tb);
            painter.drawLine(fb, ta);
        }

        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(58, 61, 63));
        painter.drawEllipse(fa, 3.1, 1.8);
        painter.drawEllipse(fb, 3.1, 1.8);
    }
}

'''
    s = s[:a] + sup + s[b:]

    a = s.index('void draw_track(')
    b = s.index('void draw_station(', a)
    track = r'''void draw_track(QPainter& painter, const Projection& projection,
                const std::vector<ch::coaster::CenterlineSample>& samples) {
    if (samples.size() < 2) return;
    RailProfile profile{};
    const double gauge = profile.gauge * 0.80;
    QPainterPath underSpine, spine, railA, railB;
    bool first = true;

    for (const auto& s : samples) {
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1.0e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1.0e-6 ?  s.tangent_x / len :  0.0;
        const QPointF u = projection.map(s.x, s.y, s.z - 0.18);
        const QPointF c = projection.map(s.x, s.y, s.z);
        const QPointF ra = projection.map(s.x + nx*gauge, s.y + ny*gauge, s.z + profile.rail_height);
        const QPointF rb = projection.map(s.x - nx*gauge, s.y - ny*gauge, s.z + profile.rail_height);
        if (first) {
            underSpine.moveTo(u); spine.moveTo(c); railA.moveTo(ra); railB.moveTo(rb); first = false;
        } else {
            underSpine.lineTo(u); spine.lineTo(c); railA.lineTo(ra); railB.lineTo(rb);
        }
    }

    painter.setBrush(Qt::NoBrush);
    QPen under(QColor(70, 25, 23)); under.setWidthF(8.2); under.setJoinStyle(Qt::RoundJoin);
    painter.setPen(under); painter.drawPath(underSpine);

    QPen beam(QColor(171, 53, 42)); beam.setWidthF(5.2); beam.setJoinStyle(Qt::RoundJoin);
    painter.setPen(beam); painter.drawPath(spine);

    const int sleeperStep = std::max(1, static_cast<int>(std::round(0.82 / kTrackSampleStepM)));
    QPen sleeper(QColor(57, 58, 60)); sleeper.setWidthF(2.6); sleeper.setCapStyle(Qt::RoundCap);
    painter.setPen(sleeper);
    for (std::size_t i = 0; i < samples.size(); i += static_cast<std::size_t>(sleeperStep)) {
        const auto& s = samples[i];
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1.0e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1.0e-6 ?  s.tangent_x / len :  0.0;
        painter.drawLine(projection.map(s.x + nx*0.78, s.y + ny*0.78, s.z + 0.05),
                         projection.map(s.x - nx*0.78, s.y - ny*0.78, s.z + 0.05));
    }

    QPen railShadow(QColor(91, 96, 99)); railShadow.setWidthF(4.3); railShadow.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railShadow); painter.drawPath(railA); painter.drawPath(railB);
    QPen rail(QColor(225, 229, 231)); rail.setWidthF(2.5); rail.setJoinStyle(Qt::RoundJoin);
    painter.setPen(rail); painter.drawPath(railA); painter.drawPath(railB);

    QPen chain(QColor(232, 176, 56)); chain.setWidthF(2.0);
    QPen brake(QColor(46, 47, 49)); brake.setWidthF(3.0);
    for (std::size_t i = 0; i < samples.size(); i += 5U) {
        const auto& s = samples[i];
        const QPointF c = projection.map(s.x, s.y, s.z + 0.10);
        if (s.drive_mode == ch::coaster::DriveMode::Lift) {
            painter.setPen(chain);
            painter.drawEllipse(c, 1.7, 1.7);
        } else if (s.drive_mode == ch::coaster::DriveMode::Brake) {
            painter.setPen(brake);
            painter.drawLine(c + QPointF(-2.4, -1.3), c + QPointF(2.4, 1.3));
        }
    }
}

'''
    s = s[:a] + track + s[b:]

    a = s.index('void draw_station(')
    b = s.index('void draw_train(', a)
    station = r'''void draw_station(QPainter& painter, const Projection& p) {
    QPolygonF base;
    base << p.map(8.8,-3.1,0.03) << p.map(26.2,-3.1,0.03)
         << p.map(26.2,3.1,0.03) << p.map(8.8,3.1,0.03);
    painter.setPen(QPen(QColor(72,57,45),2.0));
    painter.setBrush(QColor(194,161,116));
    painter.drawPolygon(base);

    QPen edge(QColor(226,176,58)); edge.setWidthF(3.0);
    painter.setPen(edge);
    painter.drawLine(p.map(9.1,-2.35,0.08), p.map(25.9,-2.35,0.08));
    painter.drawLine(p.map(9.1, 2.35,0.08), p.map(25.9, 2.35,0.08));

    QPen postOutline(QColor(54,39,34)); postOutline.setWidthF(5.0);
    QPen post(QColor(101,68,50)); post.setWidthF(3.0);
    for (double x : {10.0, 17.5, 25.0}) {
        for (double y : {-2.55, 2.55}) {
            const QPointF a = p.map(x,y,0.05), b = p.map(x,y,2.35);
            painter.setPen(postOutline); painter.drawLine(a,b);
            painter.setPen(post); painter.drawLine(a,b);
        }
    }

    QPolygonF roofLeft;
    roofLeft << p.map(9.4,-3.0,2.30) << p.map(25.6,-3.0,2.30)
             << p.map(25.6,0.0,3.05) << p.map(9.4,0.0,3.05);
    QPolygonF roofRight;
    roofRight << p.map(9.4,0.0,3.05) << p.map(25.6,0.0,3.05)
              << p.map(25.6,3.0,2.30) << p.map(9.4,3.0,2.30);

    painter.setPen(QPen(QColor(66,22,20),2.3));
    painter.setBrush(QColor(150,42,35)); painter.drawPolygon(roofLeft);
    painter.setBrush(QColor(122,31,28)); painter.drawPolygon(roofRight);

    QPen ridge(QColor(236,181,57)); ridge.setWidthF(3.2);
    painter.setPen(ridge);
    painter.drawLine(p.map(9.4,0.0,3.08), p.map(25.6,0.0,3.08));

    painter.setBrush(QColor(82,30,26));
    painter.setPen(QPen(QColor(237,181,57),1.8));
    const QPointF sign = p.map(10.0,-3.15,2.0);
    painter.drawRoundedRect(QRectF(sign.x()-20.0, sign.y()-8.0, 40.0, 16.0), 3.0, 3.0);
}

'''
    s = s[:a] + station + s[b:]
    dst = out/'coaster_project_video_main_v5.cpp'
    dst.write_text(s, encoding='utf-8')
    write(out/'structure_report.json', {
        'contract': 'CH_COASTER_STRUCTURE_REFINEMENT_V5',
        'status': 'ok',
        'changes': [
            'reduced support density with wider A-frames',
            'cross-braced tall supports and visible foot plates',
            'ground track shadow for depth',
            'separate under-spine, beam, sleepers and steel rails',
            'visible lift chain and brake fins',
            'pitched two-slope station roof with platform safety edges',
        ],
    })
    write(out/'worker_summary.json', {
        'contract': 'CH_COASTER_WORKER_TASK_REPORT_V2',
        'task': 'structure',
        'status': 'ok',
    })

def motion(out):
    s = PROOF.read_text(encoding='utf-8')
    if '#include <stdexcept>' not in s:
        s = s.replace('#include <QFileInfo>\n', '#include <QFileInfo>\n#include <stdexcept>\n', 1)
    old = 'constexpr double kSpriteScaleCoefficient = 0.035976898743442;'
    if old not in s:
        raise RuntimeError('sprite scale marker missing')
    s = s.replace(old, 'constexpr double kSpriteScaleCoefficient = 0.0425;', 1)

    old_sig = '''    const ch::coaster::CenterlineRoute& route,
    const double leadDistance,
    std::array<ch::coaster::CarPoseSelection, ch::coaster::kCoasterTrainCarCount>& previousPoses,'''
    new_sig = '''    const ch::coaster::CenterlineRoute& route,
    const double leadDistance,
    const double trainSpeedMps,
    std::array<ch::coaster::CarPoseSelection, ch::coaster::kCoasterTrainCarCount>& previousPoses,'''
    if old_sig not in s:
        raise RuntimeError('draw train signature marker missing')
    s = s.replace(old_sig, new_sig, 1)

    old_pose = '''        auto pose = ch::coaster::make_car_runtime_pose(
            i, *sample, kTrainSpeedMps, 0, cfg.physics, previous);'''
    new_pose = r'''        auto visualSample = *sample;
        if (std::abs(visualSample.tangent_z) < 0.08 &&
            std::abs(visualSample.horizontal_curvature_per_m) > 1.0e-4) {
            const double bank = std::clamp(
                std::atan2(trainSpeedMps * trainSpeedMps *
                           visualSample.horizontal_curvature_per_m,
                           cfg.physics.gravity_mps2) * 180.0 / kPi,
                -24.0, 24.0);
            const double r = bank * kPi / 180.0;
            const double c = std::cos(r), sn = std::sin(r);
            const double ux = visualSample.up_x, uy = visualSample.up_y, uz = visualSample.up_z;
            const double rx = visualSample.right_x, ry = visualSample.right_y, rz = visualSample.right_z;
            visualSample.up_x = ux*c + rx*sn;
            visualSample.up_y = uy*c + ry*sn;
            visualSample.up_z = uz*c + rz*sn;
            visualSample.right_x = rx*c - ux*sn;
            visualSample.right_y = ry*c - uy*sn;
            visualSample.right_z = rz*c - uz*sn;
        }
        auto pose = ch::coaster::make_car_runtime_pose(
            i, visualSample, trainSpeedMps, 0, cfg.physics, previous);'''
    if old_pose not in s:
        raise RuntimeError('make pose marker missing')
    s = s.replace(old_pose, new_pose, 1)

    shadow_marker = '''        const double spriteScale = projection.scale * kSpriteScaleCoefficient;
        const QSizeF size(r.w * spriteScale, r.h * spriteScale);'''
    shadow_repl = r'''        const double spriteScale = projection.scale * kSpriteScaleCoefficient;
        const QPointF ground = projection.map(car.pose.world_x, car.pose.world_y, 0.03);
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(18, 28, 18, 70));
        painter.drawEllipse(QRectF(ground.x() - 34.0*spriteScale,
                                   ground.y() - 8.0*spriteScale,
                                   68.0*spriteScale,
                                   16.0*spriteScale));
        const QSizeF size(r.w * spriteScale, r.h * spriteScale);'''
    if shadow_marker not in s:
        raise RuntimeError('shadow insertion marker missing')
    s = s.replace(shadow_marker, shadow_repl, 1)

    helper_mark = 'void draw_train_continuous('
    helper = r'''struct RideFrame {
    double lead = 0.0;
    double speed = 0.0;
};

std::vector<RideFrame> build_physics_timeline(
    const ch::coaster::CenterlineRoute& route) {
    ch::coaster::TrainRuntimeConfig cfg;
    cfg.route_length_m = route.length_m();
    cfg.closed_route = true;
    cfg.car_spacing_m = ch::coaster::kFlameCarCenterSpacingM;
    cfg.physics.maximum_speed_mps = 22.0;
    cfg.physics.lift_target_speed_mps = 5.2;
    cfg.physics.brake_target_speed_mps = 5.5;

    ch::coaster::TrainRuntimeState state;
    state.lead.distance_m = 0.0;
    state.lead.speed_mps = 4.5;
    if (const auto start = route.sample(0.0)) state.lead.height_m = start->z;

    std::vector<RideFrame> frames;
    frames.push_back({0.0, state.lead.speed_mps});
    double traveled = 0.0;

    for (int guard = 0; guard < kFps * 90 && traveled < route.length_m(); ++guard) {
        const auto step = ch::coaster::step_train(
            state, cfg,
            [&route](double d) {
                return route.sample(d).value_or(ch::coaster::CenterlineSample{});
            },
            1.0 / static_cast<double>(kFps), 0);
        if (!step.valid) throw std::runtime_error("coaster physics timeline invalid");
        if (step.physics.distance_delta_m <= 1.0e-6 && step.state.lead.stalled)
            throw std::runtime_error("coaster physics timeline stalled");
        traveled += step.physics.distance_delta_m;
        state = step.state;
        if (traveled >= route.length_m() - 1.0e-6) {
            frames.push_back({0.0, state.lead.speed_mps});
            break;
        }
        frames.push_back({state.lead.distance_m, state.lead.speed_mps});
    }
    if (traveled < route.length_m() - 1.0e-3)
        throw std::runtime_error("coaster physics timeline did not finish full lap");
    return frames;
}

'''
    if helper_mark not in s:
        raise RuntimeError('helper insertion marker missing')
    s = s.replace(helper_mark, helper + helper_mark, 1)

    old_meta = '    meta.insert(QStringLiteral("trainSpeedMps"), kTrainSpeedMps);'
    new_meta = '''    meta.insert(QStringLiteral("trainSpeedMps"),
                route.length_m() / std::max(0.001, lapSeconds));
    meta.insert(QStringLiteral("motionModel"), QStringLiteral("CH_COASTER_PHYSICS_V1"));'''
    if old_meta not in s:
        raise RuntimeError('capture metadata marker missing')
    s = s.replace(old_meta, new_meta, 1)

    old_timing = '''    const double lapSeconds = route.length_m() / kTrainSpeedMps;
    const int frameCount = std::max(2, static_cast<int>(std::ceil(lapSeconds * kFps)) + 1);
    if (!write_capture_metadata(outputDir, route, frameCount, lapSeconds)) return 7;'''
    new_timing = '''    const auto rideTimeline = build_physics_timeline(route);
    const int frameCount = static_cast<int>(rideTimeline.size());
    const double lapSeconds = static_cast<double>(frameCount - 1) / kFps;
    if (!write_capture_metadata(outputDir, route, frameCount, lapSeconds)) return 7;'''
    if old_timing not in s:
        raise RuntimeError('timing marker missing')
    s = s.replace(old_timing, new_timing, 1)

    old_lead = '''        const double lapProgress = static_cast<double>(frame) /
                                   static_cast<double>(frameCount - 1);
        const double lead = ch::coaster::normalize_route_distance(
            lapProgress * route.length_m(), route.length_m(), true);
        draw_train_continuous(
            painter, projection, atlas, route, lead, previousPoses, hasPreviousPose);'''
    new_lead = '''        const auto rideFrame = rideTimeline[static_cast<std::size_t>(frame)];
        draw_train_continuous(
            painter, projection, atlas, route, rideFrame.lead, rideFrame.speed,
            previousPoses, hasPreviousPose);'''
    if old_lead not in s:
        raise RuntimeError('lead timeline marker missing')
    s = s.replace(old_lead, new_lead, 1)

    dst = out/'coaster_video_proof_main_v5.cpp'
    dst.write_text(s, encoding='utf-8')
    write(out/'motion_report.json', {
        'contract': 'CH_COASTER_MOTION_REFINEMENT_V5',
        'status': 'ok',
        'motionModel': 'CH_COASTER_PHYSICS_V1',
        'spriteScaleCoefficient': 0.0425,
        'bankLimitDegrees': 24.0,
        'changes': [
            'runtime longitudinal physics timeline',
            'drive-mode lift/brake targets honored',
            'speed-aware car force samples',
            'level-curve car banking within V2 atlas coverage',
            'car ground shadows',
            'slightly larger train readability',
        ],
    })
    write(out/'worker_summary.json', {
        'contract': 'CH_COASTER_WORKER_TASK_REPORT_V2',
        'task': 'motion',
        'status': 'ok',
    })

def wait(paths):
    end = time.time() + 300
    while time.time() < end:
        miss = [p for p in paths if not p.is_file()]
        if not miss:
            return
        print('Worker 4 waiting:', ','.join(str(p.relative_to(REPO)) for p in miss), flush=True)
        time.sleep(2)
    raise FileNotFoundError('worker dependencies missing')

def video(out):
    proj = GOUT/'coaster_flame_switchback_04.mapforge.json'
    ps = SOUT/'coaster_project_video_main_v5.cpp'
    pv = MOUT/'coaster_video_proof_main_v5.cpp'
    wait([proj, ps, pv])

    tmp = REPO/'out/ch_blender_agent/.coaster_switchback_v5_video_tmp'
    frames = tmp/'frames'
    build = REPO/'build/ch-coaster-switchback-v5-worker4'
    if tmp.exists():
        shutil.rmtree(tmp)
    frames.mkdir(parents=True)
    out.mkdir(parents=True, exist_ok=True)

    ob = tmp/'base.cpp'
    op = tmp/'proof.cpp'
    shutil.copy2(BASE, ob)
    shutil.copy2(PROOF, op)
    try:
        shutil.copy2(ps, BASE)
        shutil.copy2(pv, PROOF)
        run(['cmake','-S','tools/animation_preview/coaster_video_proof','-B',build,'-G','Ninja'])
        run(['cmake','--build',build,'--target','MapForge2CoasterVideoProof','--parallel'])
        renderer = build/'MapForge2CoasterVideoProof'
        atlas = REPO/'assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png'
        run([renderer, frames, atlas, proj])

        cap = load(frames/'capture_meta.json')
        n = int(cap['frameCount'])
        mp4 = out/'coaster_flame_switchback_v5_worker4.mp4'
        sheet = out/'contact_sheet_switchback_v5.png'
        run(['ffmpeg','-y','-framerate','30','-i',frames/'frame_%04d.png',
             '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
        iv = max(1, n//12)
        vf = f"select='not(mod(n\\,{iv}))',scale=640:-1,tile=4x3"
        run(['ffmpeg','-y','-i',mp4,'-vf',vf,'-frames:v','1','-update','1',sheet])

        shutil.copy2(frames/'capture_meta.json', out/'capture_meta.json')
        shutil.copy2(proj, out/'coaster_flame_switchback_04.mapforge.json')
        write(out/'video_report.json', {
            'contract': 'CH_COASTER_WORKER4_VIDEO_REPORT_V2',
            'status': 'ok',
            'projectId': 'coaster.flame.switchback.04',
            'frameCount': n,
            'fps': 30,
            'routeLengthM': cap.get('routeMeters'),
            'lapSeconds': cap.get('lapSeconds'),
            'motionModel': cap.get('motionModel'),
            'video': mp4.name,
            'integratedWorkers': ['geometry','structure','motion'],
        })
    finally:
        shutil.copy2(ob, BASE)
        shutil.copy2(op, PROOF)

def main():
    a = args()
    out = rp(a.output)
    out.mkdir(parents=True, exist_ok=True)
    if a.task == 'geometry':
        geometry(rp(a.project), out)
    elif a.task == 'structure':
        structure(out)
    elif a.task == 'motion':
        motion(out)
    else:
        video(out)

if __name__ == '__main__':
    main()
