#include "../../../src/coaster_centerline_route.h"
#include "../../../src/coaster_train_runtime.h"
#include "../../../src/rail_system.h"

#include <QCoreApplication>
#include <QDir>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPointF>
#include <QPolygonF>
#include <QRectF>
#include <QString>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <vector>

namespace {

constexpr int kWidth = 1280;
constexpr int kHeight = 720;
constexpr int kFps = 30;
constexpr int kFrameCount = 360;
constexpr double kTrainSpeedMps = 11.0;
constexpr double kTrackSampleStepM = 0.28;
constexpr double kWorldScale = 10.6;
constexpr double kHeightScale = 38.0;
constexpr double kSupportSpacingM = 2.5;

QPointF project(const double x, const double y, const double z) {
    return {
        kWidth * 0.5 + (x - y) * kWorldScale,
        kHeight * 0.64 + (x + y) * (kWorldScale * 0.5) - z * kHeightScale,
    };
}

ch::coaster::CenterlineRoute build_route() {
    using ch::coaster::DriveMode;
    using ch::coaster::RoutePoint;

    std::vector<RoutePoint> points = {
        {-31.0, -13.0, 0.0, DriveMode::Station, 4.5},
        {-24.0, -13.0, 0.0, DriveMode::Lift,    6.0},
        {-16.0, -13.0, 1.2, DriveMode::Lift,    6.0},
        { -8.0, -13.0, 2.6, DriveMode::Lift,    6.0},
        {  0.0, -13.0, 4.0, DriveMode::Lift,    6.0},
        {  8.0, -13.0, 5.4, DriveMode::Lift,    6.0},
        { 16.0, -13.0, 6.8, DriveMode::Lift,    6.0},
        { 23.0, -13.0, 7.8, DriveMode::Free,   -1.0},
        { 28.0, -11.0, 7.8, DriveMode::Free,   -1.0},
        { 31.0,  -7.0, 6.9, DriveMode::Free,   -1.0},
        { 32.0,  -2.0, 5.6, DriveMode::Free,   -1.0},
        { 31.0,   3.0, 4.0, DriveMode::Free,   -1.0},
        { 28.0,   7.0, 2.2, DriveMode::Free,   -1.0},
        { 23.0,   9.0, 0.7, DriveMode::Free,   -1.0},
        { 16.0,  10.0, 0.4, DriveMode::Free,   -1.0},
        {  9.0,  10.0, 1.5, DriveMode::Free,   -1.0},
        {  2.0,  10.0, 2.7, DriveMode::Free,   -1.0},
        { -5.0,  10.0, 1.5, DriveMode::Free,   -1.0},
        {-12.0,  10.0, 0.4, DriveMode::Free,   -1.0},
        {-18.0,   9.0, 0.7, DriveMode::Free,   -1.0},
        {-24.0,   7.0, 1.5, DriveMode::Free,   -1.0},
        {-28.0,   3.0, 2.2, DriveMode::Free,   -1.0},
        {-29.0,  -2.0, 1.5, DriveMode::Free,   -1.0},
        {-27.0,  -7.0, 0.5, DriveMode::Free,   -1.0},
        {-22.0,  -9.0, 0.0, DriveMode::Free,   -1.0},
        {-16.0,  -7.0, 0.0, DriveMode::Free,   -1.0},
        {-13.0,  -3.0, 0.0, DriveMode::Free,   -1.0},
        {-15.0,   1.0, 0.0, DriveMode::Free,   -1.0},
        {-20.0,   2.0, 0.0, DriveMode::Free,   -1.0},
        {-25.0,   0.0, 0.0, DriveMode::Brake,   7.0},
        {-29.0,  -4.0, 0.0, DriveMode::Brake,   5.5},
        {-31.0,  -9.0, 0.0, DriveMode::Station, 4.5},
    };

    ch::coaster::CenterlineRoute route;
    const bool rebuilt = route.rebuild(std::move(points), true);
    if (!rebuilt) route.clear();
    return route;
}

void draw_grid(QPainter& painter) {
    painter.fillRect(QRect(0, 0, kWidth, kHeight), QColor(59, 111, 61));
    QPen grid(QColor(255, 255, 255, 18));
    grid.setWidthF(1.0);
    painter.setPen(grid);
    for (int i = -40; i <= 40; ++i) {
        painter.drawLine(project(i, -28, 0), project(i, 28, 0));
        painter.drawLine(project(-40, i, 0), project(40, i, 0));
    }
}

std::vector<ch::coaster::CenterlineSample> sample_track(const ch::coaster::CenterlineRoute& route) {
    std::vector<ch::coaster::CenterlineSample> samples;
    const int count = std::max(2, static_cast<int>(std::ceil(route.length_m() / kTrackSampleStepM)));
    samples.reserve(static_cast<std::size_t>(count + 1));
    for (int i = 0; i <= count; ++i) {
        const double d = route.length_m() * static_cast<double>(i) / static_cast<double>(count);
        const auto s = route.sample(d >= route.length_m() ? 0.0 : d);
        if (s) samples.push_back(*s);
    }
    return samples;
}

void draw_supports(QPainter& painter, const ch::coaster::CenterlineRoute& route) {
    QPen supportPen(QColor(82, 87, 90));
    supportPen.setWidthF(3.0);
    painter.setPen(supportPen);

    for (double d = 0.0; d < route.length_m(); d += kSupportSpacingM) {
        const auto s = route.sample(d);
        if (!s || s->z < 0.45) continue;

        const QPointF top = project(s->x, s->y, s->z - 0.08);
        const QPointF base = project(s->x, s->y, 0.0);
        painter.drawLine(top, base);

        const double tangentLen = std::hypot(s->tangent_x, s->tangent_y);
        const double nx = tangentLen > 1e-6 ? -s->tangent_y / tangentLen : -1.0;
        const double ny = tangentLen > 1e-6 ?  s->tangent_x / tangentLen :  0.0;
        painter.drawLine(top, project(s->x + nx * 0.65, s->y + ny * 0.65, 0.0));
        painter.drawLine(top, project(s->x - nx * 0.65, s->y - ny * 0.65, 0.0));
    }
}

void draw_station(QPainter& painter) {
    QPolygonF platform;
    platform << project(-34.0, -15.4, 0.02)
             << project(-20.5, -15.4, 0.02)
             << project(-20.5, -10.7, 0.02)
             << project(-34.0, -10.7, 0.02);
    painter.setPen(QPen(QColor(88, 71, 52), 2.0));
    painter.setBrush(QColor(184, 153, 111));
    painter.drawPolygon(platform);

    QPen post(QColor(90, 54, 37));
    post.setWidthF(3.0);
    painter.setPen(post);
    for (double x : {-32.5, -28.5, -24.5, -21.5}) {
        painter.drawLine(project(x, -15.0, 0.0), project(x, -15.0, 1.8));
        painter.drawLine(project(x, -11.0, 0.0), project(x, -11.0, 1.8));
    }
    QPolygonF roof;
    roof << project(-33.0, -15.5, 1.8)
         << project(-21.0, -15.5, 1.8)
         << project(-21.0, -10.5, 1.8)
         << project(-33.0, -10.5, 1.8);
    painter.setBrush(QColor(126, 37, 34));
    painter.setPen(QPen(QColor(78, 28, 25), 2.0));
    painter.drawPolygon(roof);
}

void draw_track(QPainter& painter,
                const ch::coaster::CenterlineRoute& route,
                const std::vector<ch::coaster::CenterlineSample>& samples) {
    if (samples.size() < 2) return;

    RailProfile profile{};
    const double gauge = profile.gauge * 0.72;
    painter.setBrush(Qt::NoBrush);

    QPainterPath bed;
    bed.moveTo(project(samples.front().x, samples.front().y, samples.front().z));
    for (std::size_t i = 1; i < samples.size(); ++i)
        bed.lineTo(project(samples[i].x, samples[i].y, samples[i].z));
    bed.closeSubpath();

    QPen spinePen(QColor(67, 44, 39));
    spinePen.setWidthF(10.0);
    spinePen.setCapStyle(Qt::RoundCap);
    spinePen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spinePen);
    painter.drawPath(bed);

    QPainterPath railA, railB;
    bool first = true;
    for (const auto& s : samples) {
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1e-6 ?  s.tangent_x / len :  0.0;
        const QPointF a = project(s.x + nx * gauge, s.y + ny * gauge, s.z + profile.rail_height);
        const QPointF b = project(s.x - nx * gauge, s.y - ny * gauge, s.z + profile.rail_height);
        if (first) { railA.moveTo(a); railB.moveTo(b); first = false; }
        else { railA.lineTo(a); railB.lineTo(b); }
    }
    QPen railPen(QColor(193, 199, 201));
    railPen.setWidthF(3.0);
    railPen.setCapStyle(Qt::RoundCap);
    railPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railPen);
    painter.drawPath(railA);
    painter.drawPath(railB);

    const int sleeperStep = std::max(1, static_cast<int>(std::round(profile.sleeper_spacing / kTrackSampleStepM)));
    QPen sleeperPen(QColor(91, 58, 38));
    sleeperPen.setWidthF(3.2);
    painter.setPen(sleeperPen);
    for (std::size_t i = 0; i < samples.size(); i += static_cast<std::size_t>(sleeperStep)) {
        const auto& s = samples[i];
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1e-6 ?  s.tangent_x / len :  0.0;
        painter.drawLine(project(s.x + nx * 0.62, s.y + ny * 0.62, s.z + 0.02),
                         project(s.x - nx * 0.62, s.y - ny * 0.62, s.z + 0.02));
    }

    QPen liftPen(QColor(226, 179, 63));
    liftPen.setWidthF(2.0);
    liftPen.setStyle(Qt::DashLine);
    painter.setPen(liftPen);
    QPainterPath lift;
    bool liftStarted = false;
    for (double d = 7.0; d <= 54.0; d += 0.35) {
        const auto s = route.sample(d);
        if (!s) continue;
        const QPointF p = project(s->x, s->y, s->z + 0.13);
        if (!liftStarted) { lift.moveTo(p); liftStarted = true; }
        else lift.lineTo(p);
    }
    painter.drawPath(lift);
}

void draw_train(QPainter& painter,
                const QImage& atlas,
                const ch::coaster::CenterlineRoute& route,
                const double leadDistance) {
    ch::coaster::TrainRuntimeConfig cfg;
    cfg.route_length_m = route.length_m();
    cfg.closed_route = true;
    cfg.car_spacing_m = ch::coaster::kFlameCarCenterSpacingM;

    struct DrawCar { ch::coaster::CarRuntimePose pose; double depth = 0.0; };
    std::vector<DrawCar> cars;
    cars.reserve(ch::coaster::kCoasterTrainCarCount);

    for (int i = 0; i < ch::coaster::kCoasterTrainCarCount; ++i) {
        const double d = ch::coaster::car_route_distance(leadDistance, i, cfg);
        const auto sample = route.sample(d);
        if (!sample) continue;
        auto pose = ch::coaster::make_car_runtime_pose(i, *sample, kTrainSpeedMps, 0, cfg.physics);
        cars.push_back({pose, pose.world_x + pose.world_y + pose.world_z * 0.2});
    }
    std::sort(cars.begin(), cars.end(), [](const DrawCar& a, const DrawCar& b) {
        return a.depth < b.depth;
    });

    for (const DrawCar& car : cars) {
        const auto& r = car.pose.sprite_pose.source_rect;
        const QRect src(r.x, r.y, r.w, r.h);
        const QPointF anchor = project(car.pose.world_x, car.pose.world_y, car.pose.world_z + 0.15);
        constexpr double spriteScale = 0.58;
        const QSizeF size(r.w * spriteScale, r.h * spriteScale);
        const QRectF dst(anchor.x() - size.width() * 0.5,
                         anchor.y() - size.height() * 0.62,
                         size.width(), size.height());
        painter.drawImage(dst, atlas, src);
    }
}

} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    if (argc < 2) {
        std::fprintf(stderr, "usage: MapForge2CoasterVideoProof <output-dir> [atlas]\n");
        return 2;
    }

    const QString outputDir = QString::fromLocal8Bit(argv[1]);
    const QString atlasPath = argc >= 3
        ? QString::fromLocal8Bit(argv[2])
        : QString::fromUtf8(ch::coaster::kFlameCarPoseAtlasPath);

    QDir().mkpath(outputDir);
    QImage atlas(atlasPath);
    if (atlas.isNull() || atlas.width() != 2048 || atlas.height() != 1280) {
        std::fprintf(stderr, "invalid Flame car pose atlas: %s\n", atlasPath.toUtf8().constData());
        return 3;
    }

    const auto route = build_route();
    if (!route.valid()) {
        std::fprintf(stderr, "failed to construct CH_COASTER_CENTERLINE_ROUTE_V1 proof route\n");
        return 4;
    }
    const auto trackSamples = sample_track(route);

    for (int frame = 0; frame < kFrameCount; ++frame) {
        QImage image(kWidth, kHeight, QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        painter.setRenderHint(QPainter::Antialiasing, true);
        painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
        draw_grid(painter);
        draw_station(painter);
        draw_supports(painter, route);
        draw_track(painter, route, trackSamples);

        const double seconds = static_cast<double>(frame) / kFps;
        const double leadDistance = ch::coaster::normalize_route_distance(
            seconds * kTrainSpeedMps, route.length_m(), true);
        draw_train(painter, atlas, route, leadDistance);
        painter.end();

        const QString path = QStringLiteral("%1/frame_%2.png")
            .arg(outputDir)
            .arg(frame, 4, 10, QLatin1Char('0'));
        if (!image.save(path, "PNG")) {
            std::fprintf(stderr, "failed to save frame %d\n", frame);
            return 5;
        }
    }

    std::printf("CH_COASTER_VIDEO_PROOF_V2 frames=%d fps=%d cars=%d route_m=%.3f\n",
                kFrameCount, kFps, ch::coaster::kCoasterTrainCarCount, route.length_m());
    return 0;
}
