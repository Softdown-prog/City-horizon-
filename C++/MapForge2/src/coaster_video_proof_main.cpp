#include "../../../src/coaster_centerline_route.h"
#include "../../../src/coaster_train_runtime.h"

#include <QCoreApplication>
#include <QDir>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPointF>
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
constexpr int kFrameCount = 240; // 8 seconds
constexpr double kTrainSpeedMps = 7.5;
constexpr double kTrackSampleStepM = 0.35;
constexpr double kWorldScale = 13.0;
constexpr double kHeightScale = 18.0;

QPointF project(const double x, const double y, const double z) {
    // CH_CAMERA_V1-compatible 2:1 ground projection for this deterministic proof.
    return {
        kWidth * 0.5 + (x - y) * kWorldScale,
        kHeight * 0.56 + (x + y) * (kWorldScale * 0.5) - z * kHeightScale,
    };
}

ch::coaster::CenterlineRoute build_route() {
    using ch::coaster::DriveMode;
    using ch::coaster::RoutePoint;

    // A compact closed demonstration circuit: station straight -> lift -> crest ->
    // descending back straight -> broad ground curves.  Extra points make the
    // centerline tangent interpolation smooth while keeping the vertical sections
    // predominantly cardinal, matching CH_COASTER_TRACK_V1's current contract.
    std::vector<RoutePoint> points = {
        {-15.0, -9.0, 0.0, DriveMode::Station, 5.0},
        {-8.0,  -9.0, 0.0, DriveMode::Lift,    7.5},
        {-2.0,  -9.0, 1.4, DriveMode::Lift,    7.5},
        { 4.0,  -9.0, 3.8, DriveMode::Lift,    7.5},
        {10.0,  -9.0, 6.0, DriveMode::Free,   -1.0},
        {15.0,  -7.0, 6.0, DriveMode::Free,   -1.0},
        {18.0,  -3.0, 5.2, DriveMode::Free,   -1.0},
        {19.0,   2.0, 3.4, DriveMode::Free,   -1.0},
        {18.0,   7.0, 1.2, DriveMode::Free,   -1.0},
        {15.0,  10.0, 0.0, DriveMode::Free,   -1.0},
        { 9.0,  11.0, 0.0, DriveMode::Free,   -1.0},
        { 2.0,  11.0, 0.0, DriveMode::Free,   -1.0},
        {-5.0,  11.0, 0.0, DriveMode::Free,   -1.0},
        {-11.0, 10.0, 0.0, DriveMode::Free,   -1.0},
        {-16.0,  7.0, 0.0, DriveMode::Brake,   7.0},
        {-19.0,  2.0, 0.0, DriveMode::Brake,   6.0},
        {-19.0, -3.0, 0.0, DriveMode::Free,   -1.0},
        {-18.0, -7.0, 0.0, DriveMode::Free,   -1.0},
    };

    ch::coaster::CenterlineRoute route;
    route.rebuild(std::move(points), true);
    return route;
}

void draw_grid(QPainter& painter) {
    painter.fillRect(QRect(0, 0, kWidth, kHeight), QColor(56, 104, 55));
    QPen grid(QColor(255, 255, 255, 24));
    grid.setWidthF(1.0);
    painter.setPen(grid);
    for (int i = -26; i <= 26; ++i) {
        painter.drawLine(project(i, -20, 0), project(i, 20, 0));
        painter.drawLine(project(-26, i, 0), project(26, i, 0));
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

void draw_track(QPainter& painter, const std::vector<ch::coaster::CenterlineSample>& samples) {
    if (samples.size() < 2) return;

    // Thick dark bed, then twin steel rails and sleepers. This stays intentionally
    // readable at tycoon scale instead of trying to mimic a live 3D mesh.
    QPainterPath bed;
    bed.moveTo(project(samples.front().x, samples.front().y, samples.front().z));
    for (std::size_t i = 1; i < samples.size(); ++i)
        bed.lineTo(project(samples[i].x, samples[i].y, samples[i].z));
    bed.closeSubpath();

    QPen bedPen(QColor(49, 45, 42));
    bedPen.setWidthF(13.0);
    bedPen.setCapStyle(Qt::RoundCap);
    bedPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(bedPen);
    painter.drawPath(bed);

    // Build two rail polylines by offsetting perpendicular to the horizontal tangent.
    QPainterPath railA, railB;
    bool first = true;
    for (const auto& s : samples) {
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1e-6 ?  s.tangent_x / len :  0.0;
        constexpr double gauge = 0.38;
        const QPointF a = project(s.x + nx * gauge, s.y + ny * gauge, s.z + 0.08);
        const QPointF b = project(s.x - nx * gauge, s.y - ny * gauge, s.z + 0.08);
        if (first) { railA.moveTo(a); railB.moveTo(b); first = false; }
        else { railA.lineTo(a); railB.lineTo(b); }
    }
    QPen railPen(QColor(178, 184, 189));
    railPen.setWidthF(3.2);
    railPen.setCapStyle(Qt::RoundCap);
    railPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railPen);
    painter.drawPath(railA);
    painter.drawPath(railB);

    QPen sleeperPen(QColor(75, 61, 47));
    sleeperPen.setWidthF(3.0);
    painter.setPen(sleeperPen);
    for (std::size_t i = 0; i < samples.size(); i += 5) {
        const auto& s = samples[i];
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1e-6 ?  s.tangent_x / len :  0.0;
        painter.drawLine(project(s.x + nx * 0.65, s.y + ny * 0.65, s.z + 0.03),
                         project(s.x - nx * 0.65, s.y - ny * 0.65, s.z + 0.03));
    }
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
        // Isometric painter order: farther north/west first, plus height contribution.
        cars.push_back({pose, pose.world_x + pose.world_y + pose.world_z * 0.2});
    }
    std::sort(cars.begin(), cars.end(), [](const DrawCar& a, const DrawCar& b) {
        return a.depth < b.depth;
    });

    for (const DrawCar& car : cars) {
        const auto& r = car.pose.sprite_pose.source_rect;
        const QRect src(r.x, r.y, r.w, r.h);
        const QPointF anchor = project(car.pose.world_x, car.pose.world_y, car.pose.world_z + 0.12);
        constexpr double spriteScale = 0.62;
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
        draw_track(painter, trackSamples);

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

    std::printf("CH_COASTER_VIDEO_PROOF_V1 frames=%d fps=%d cars=%d route_m=%.3f\n",
                kFrameCount, kFps, ch::coaster::kCoasterTrainCarCount, route.length_m());
    return 0;
}
