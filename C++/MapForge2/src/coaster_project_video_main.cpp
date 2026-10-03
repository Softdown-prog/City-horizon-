#include "../../../src/coaster_centerline_route.h"
#include "../../../src/coaster_train_runtime.h"
#include "../../../src/rail_system.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
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
constexpr double kTrackSampleStepM = 0.24;
constexpr double kSupportSpacingM = 3.0;
constexpr double kPi = 3.14159265358979323846;

struct ProjectCursor {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double heading = 0.0;
};

struct Projection {
    double scale = 1.0;
    double offsetX = 0.0;
    double offsetY = 0.0;
    // CH_CAMERA_V1: orthographic, yaw 45 degrees, elevation 30 degrees.
    // With the 2:1 ground diamond normalized to u=x+y, the world-Z screen
    // coefficient is sqrt(3/2). Keep this identical to fit_projection().
    double zFactor = 1.224744871391589;

    [[nodiscard]] QPointF map(double x, double y, double z) const {
        const double u = x + y;
        const double v = 0.5 * (x - y) - z * zFactor;
        return {offsetX + u * scale, offsetY + v * scale};
    }
};

ch::coaster::DriveMode drive_mode(const QString& name) {
    if (name == QStringLiteral("station")) return ch::coaster::DriveMode::Station;
    if (name == QStringLiteral("lift")) return ch::coaster::DriveMode::Lift;
    if (name == QStringLiteral("brake")) return ch::coaster::DriveMode::Brake;
    return ch::coaster::DriveMode::Free;
}

void push_unique(std::vector<ch::coaster::RoutePoint>& points,
                 double x, double y, double z,
                 ch::coaster::DriveMode mode,
                 double speed) {
    if (!points.empty()) {
        const auto& p = points.back();
        const double dx = x - p.x;
        const double dy = y - p.y;
        const double dz = z - p.z;
        if (dx * dx + dy * dy + dz * dz < 1.0e-10) return;
    }
    points.push_back({x, y, z, mode, speed});
}

bool append_straight(std::vector<ch::coaster::RoutePoint>& points,
                     ProjectCursor& cursor,
                     const QJsonObject& piece) {
    const double length = piece.value(QStringLiteral("length")).toDouble(-1.0);
    const double rise = piece.value(QStringLiteral("rise")).toDouble(0.0);
    if (!(length > 0.0) || !std::isfinite(length) || !std::isfinite(rise)) return false;
    const auto mode = drive_mode(piece.value(QStringLiteral("driveMode")).toString());
    const double speed = piece.value(QStringLiteral("targetSpeedMps")).toDouble(-1.0);
    const int samples = std::max(2, static_cast<int>(std::ceil(length / 0.5)));
    const double sx = cursor.x;
    const double sy = cursor.y;
    const double sz = cursor.z;
    const double fx = std::cos(cursor.heading);
    const double fy = std::sin(cursor.heading);
    for (int i = 1; i <= samples; ++i) {
        const double t = static_cast<double>(i) / samples;
        push_unique(points, sx + fx * length * t, sy + fy * length * t,
                    sz + rise * t, mode, speed);
    }
    cursor.x = sx + fx * length;
    cursor.y = sy + fy * length;
    cursor.z = sz + rise;
    return true;
}

bool append_quarter_curve(std::vector<ch::coaster::RoutePoint>& points,
                          ProjectCursor& cursor,
                          const QJsonObject& piece) {
    const double radius = piece.value(QStringLiteral("radius")).toDouble(-1.0);
    if (!(radius > 0.0) || !std::isfinite(radius)) return false;
    const bool left = piece.value(QStringLiteral("left")).toBool(true);
    const double sign = left ? 1.0 : -1.0;
    const auto mode = drive_mode(piece.value(QStringLiteral("driveMode")).toString());
    const double speed = piece.value(QStringLiteral("targetSpeedMps")).toDouble(-1.0);
    const double lx = -std::sin(cursor.heading);
    const double ly = std::cos(cursor.heading);
    const double cx = cursor.x + lx * radius * sign;
    const double cy = cursor.y + ly * radius * sign;
    const double rx = cursor.x - cx;
    const double ry = cursor.y - cy;
    constexpr int samples = 40;
    for (int i = 1; i <= samples; ++i) {
        const double a = sign * (kPi * 0.5) * (static_cast<double>(i) / samples);
        const double c = std::cos(a);
        const double s = std::sin(a);
        push_unique(points, cx + rx * c - ry * s, cy + rx * s + ry * c,
                    cursor.z, mode, speed);
    }
    const double a = sign * (kPi * 0.5);
    const double c = std::cos(a);
    const double s = std::sin(a);
    cursor.x = cx + rx * c - ry * s;
    cursor.y = cy + rx * s + ry * c;
    cursor.heading += a;
    return true;
}

bool load_project_route(const QString& path,
                        ch::coaster::CenterlineRoute& route,
                        QJsonObject& project) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return false;
    const auto document = QJsonDocument::fromJson(file.readAll());
    if (!document.isObject()) return false;
    project = document.object();
    if (project.value(QStringLiteral("contract")).toString() !=
        QStringLiteral("CH_MAPFORGE_COASTER_PROJECT_V1")) return false;

    const QJsonObject mapForge = project.value(QStringLiteral("mapForge")).toObject();
    const QJsonObject start = mapForge.value(QStringLiteral("start")).toObject();
    ProjectCursor cursor;
    cursor.x = start.value(QStringLiteral("x")).toDouble();
    cursor.y = start.value(QStringLiteral("y")).toDouble();
    cursor.z = start.value(QStringLiteral("z")).toDouble();
    cursor.heading = start.value(QStringLiteral("headingDegrees")).toDouble() * kPi / 180.0;
    const double startX = cursor.x;
    const double startY = cursor.y;
    const double startZ = cursor.z;

    std::vector<ch::coaster::RoutePoint> points;
    points.reserve(800);
    push_unique(points, cursor.x, cursor.y, cursor.z, ch::coaster::DriveMode::Station, 4.5);

    const QJsonArray pieces = project.value(QStringLiteral("pieces")).toArray();
    if (pieces.isEmpty()) return false;
    for (const auto& value : pieces) {
        if (!value.isObject()) return false;
        const QJsonObject piece = value.toObject();
        const QString type = piece.value(QStringLiteral("type")).toString();
        bool ok = false;
        if (type == QStringLiteral("straight")) ok = append_straight(points, cursor, piece);
        else if (type == QStringLiteral("quarter_curve")) ok = append_quarter_curve(points, cursor, piece);
        if (!ok) return false;
    }

    const double closure = std::sqrt(
        (cursor.x - startX) * (cursor.x - startX) +
        (cursor.y - startY) * (cursor.y - startY) +
        (cursor.z - startZ) * (cursor.z - startZ));
    if (closure > 0.02) {
        std::fprintf(stderr, "MapForge coaster project does not close: %.6f m\n", closure);
        return false;
    }

    // A closed authored route may sample its final piece exactly at the start
    // position. CenterlineRoute itself closes last->first, so retaining that
    // duplicate endpoint would create a near-zero closing segment and correctly
    // trip the V2 minimum-segment regression. Remove only a numerically identical
    // endpoint; the closure tolerance above remains strict and unchanged.
    if (points.size() >= 2U) {
        const auto& first = points.front();
        const auto& last = points.back();
        const double dx = last.x - first.x;
        const double dy = last.y - first.y;
        const double dz = last.z - first.z;
        if (dx * dx + dy * dy + dz * dz < 1.0e-12) {
            points.pop_back();
        }
    }
    return route.rebuild(std::move(points), true);
}

std::vector<ch::coaster::CenterlineSample> sample_track(const ch::coaster::CenterlineRoute& route) {
    std::vector<ch::coaster::CenterlineSample> samples;
    const int count = std::max(2, static_cast<int>(std::ceil(route.length_m() / kTrackSampleStepM)));
    samples.reserve(static_cast<std::size_t>(count));
    for (int i = 0; i < count; ++i) {
        const double d = route.length_m() * static_cast<double>(i) / count;
        if (auto s = route.sample(d)) samples.push_back(*s);
    }
    return samples;
}

Projection fit_projection(const std::vector<ch::coaster::CenterlineSample>& samples) {
    double minU = 1.0e30, maxU = -1.0e30, minV = 1.0e30, maxV = -1.0e30;
    // Must match the frozen CH_CAMERA_V1 used by CH Blender. The prior
    // 3.2 coefficient and x-y horizontal basis described a different camera,
    // so correctly selected car sprites could never sit visually on the rail.
    constexpr double zFactor = 1.224744871391589;
    for (const auto& s : samples) {
        const double u = s.x + s.y;
        const double v = 0.5 * (s.x - s.y) - s.z * zFactor;
        minU = std::min(minU, u); maxU = std::max(maxU, u);
        minV = std::min(minV, v); maxV = std::max(maxV, v);
    }
    constexpr double margin = 78.0;
    const double sx = (kWidth - margin * 2.0) / std::max(1.0, maxU - minU);
    const double sy = (kHeight - margin * 2.0) / std::max(1.0, maxV - minV);
    Projection p;
    p.scale = std::min(sx, sy);
    p.zFactor = zFactor;
    p.offsetX = margin - minU * p.scale + ((kWidth - margin * 2.0) - (maxU - minU) * p.scale) * 0.5;
    p.offsetY = margin - minV * p.scale + ((kHeight - margin * 2.0) - (maxV - minV) * p.scale) * 0.5;
    return p;
}

void draw_ground(QPainter& painter, const Projection& projection, const QJsonObject& project) {
    painter.fillRect(QRect(0, 0, kWidth, kHeight), QColor(58, 112, 62));
    const auto footprint = project.value(QStringLiteral("mapForge")).toObject()
                              .value(QStringLiteral("footprintTiles")).toObject();
    const int tilesX = footprint.value(QStringLiteral("width")).toInt(28);
    const int tilesY = footprint.value(QStringLiteral("depth")).toInt(28);
    const double tile = project.value(QStringLiteral("mapForge")).toObject()
                        .value(QStringLiteral("tileMeters")).toDouble(3.0);
    QPen pen(QColor(255,255,255,18));
    pen.setWidthF(1.0);
    painter.setPen(pen);
    for (int x = 0; x <= tilesX; ++x)
        painter.drawLine(projection.map(x * tile, 0.0, 0.0), projection.map(x * tile, tilesY * tile, 0.0));
    for (int y = 0; y <= tilesY; ++y)
        painter.drawLine(projection.map(0.0, y * tile, 0.0), projection.map(tilesX * tile, y * tile, 0.0));
}

void draw_supports(QPainter& painter, const Projection& projection,
                   const ch::coaster::CenterlineRoute& route) {
    QPen pen(QColor(83, 89, 92));
    pen.setWidthF(2.4);
    painter.setPen(pen);
    for (double d = 0.0; d < route.length_m(); d += kSupportSpacingM) {
        const auto s = route.sample(d);
        if (!s || s->z < 0.55) continue;
        const QPointF top = projection.map(s->x, s->y, s->z - 0.08);
        painter.drawLine(top, projection.map(s->x, s->y, 0.0));
    }
}

void draw_track(QPainter& painter, const Projection& projection,
                const std::vector<ch::coaster::CenterlineSample>& samples) {
    if (samples.size() < 2) return;
    RailProfile profile{};
    const double gauge = profile.gauge * 0.72;
    QPainterPath spine, railA, railB;
    bool first = true;
    for (const auto& s : samples) {
        const QPointF c = projection.map(s.x, s.y, s.z);
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1.0e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1.0e-6 ?  s.tangent_x / len :  0.0;
        const QPointF a = projection.map(s.x + nx * gauge, s.y + ny * gauge, s.z + profile.rail_height);
        const QPointF b = projection.map(s.x - nx * gauge, s.y - ny * gauge, s.z + profile.rail_height);
        if (first) { spine.moveTo(c); railA.moveTo(a); railB.moveTo(b); first = false; }
        else { spine.lineTo(c); railA.lineTo(a); railB.lineTo(b); }
    }
    painter.setBrush(Qt::NoBrush);
    QPen spinePen(QColor(69,45,39)); spinePen.setWidthF(7.5); spinePen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spinePen); painter.drawPath(spine);
    QPen railPen(QColor(201,205,207)); railPen.setWidthF(2.7); railPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railPen); painter.drawPath(railA); painter.drawPath(railB);

    QPen sleeper(QColor(92,59,39)); sleeper.setWidthF(2.4); painter.setPen(sleeper);
    const int step = std::max(1, static_cast<int>(std::round(profile.sleeper_spacing / kTrackSampleStepM)));
    for (std::size_t i = 0; i < samples.size(); i += static_cast<std::size_t>(step)) {
        const auto& s = samples[i];
        const double len = std::hypot(s.tangent_x, s.tangent_y);
        const double nx = len > 1.0e-6 ? -s.tangent_y / len : -1.0;
        const double ny = len > 1.0e-6 ?  s.tangent_x / len :  0.0;
        painter.drawLine(projection.map(s.x + nx * 0.60, s.y + ny * 0.60, s.z),
                         projection.map(s.x - nx * 0.60, s.y - ny * 0.60, s.z));
    }
}

void draw_station(QPainter& painter, const Projection& projection) {
    QPolygonF platform;
    platform << projection.map(10.0,-2.2,0.02) << projection.map(25.0,-2.2,0.02)
             << projection.map(25.0,2.2,0.02) << projection.map(10.0,2.2,0.02);
    painter.setPen(QPen(QColor(86,69,51),1.7));
    painter.setBrush(QColor(187,154,111));
    painter.drawPolygon(platform);
    QPolygonF roof;
    roof << projection.map(11.0,-2.5,2.1) << projection.map(24.0,-2.5,2.1)
         << projection.map(24.0,2.5,2.1) << projection.map(11.0,2.5,2.1);
    painter.setPen(QPen(QColor(77,27,24),1.6));
    painter.setBrush(QColor(128,36,32));
    painter.drawPolygon(roof);
}

void draw_train(QPainter& painter, const Projection& projection, const QImage& atlas,
                const ch::coaster::CenterlineRoute& route, double leadDistance) {
    ch::coaster::TrainRuntimeConfig cfg;
    cfg.route_length_m = route.length_m();
    cfg.closed_route = true;
    cfg.car_spacing_m = ch::coaster::kFlameCarCenterSpacingM;
    struct DrawCar { ch::coaster::CarRuntimePose pose; double depth; };
    std::vector<DrawCar> cars;
    for (int i = 0; i < ch::coaster::kCoasterTrainCarCount; ++i) {
        const double d = ch::coaster::car_route_distance(leadDistance, i, cfg);
        const auto sample = route.sample(d);
        if (!sample) continue;
        auto pose = ch::coaster::make_car_runtime_pose(i, *sample, kTrainSpeedMps, 0, cfg.physics);
        // Camera is at +X/-Y and 30 degrees elevation. Draw farther cars
        // first using the same view basis as CH_CAMERA_V1. sqrt(2/3) is the
        // world-Z depth coefficient after normalizing the X/Y terms to +/-1.
        cars.push_back({pose, pose.world_x - pose.world_y + pose.world_z * 0.816496580927726});
    }
    std::sort(cars.begin(), cars.end(), [](const DrawCar& a, const DrawCar& b){ return a.depth < b.depth; });
    for (const auto& car : cars) {
        const auto& r = car.pose.sprite_pose.source_rect;
        const QRect src(r.x,r.y,r.w,r.h);
        // The route sample itself is the rail centerline. Never add a screen-space
        // or world-Z fudge here: all occupied V2 frames were baked around the same
        // physical local rail anchor (0,0,0.48 m).
        const QPointF anchor = projection.map(car.pose.world_x, car.pose.world_y, car.pose.world_z);

        // Preserve CH Blender world scale exactly. For CH_CAMERA_V1, the source
        // horizontal coordinate is (x+y)/sqrt(2), so source pixels per normalized
        // MapForge u unit are 256/(orthoScale*sqrt(2)).
        constexpr double kBakedOrthoScale = 6.512514321292677;
        constexpr double kSpriteScaleCoefficient = 0.035976898743442;
        constexpr double kRailAnchorSourceX = 128.0;
        constexpr double kRailAnchorSourceY = 154.212752736043740;
        static_assert(kBakedOrthoScale > 6.5 && kBakedOrthoScale < 6.53);
        const double spriteScale = projection.scale * kSpriteScaleCoefficient;
        const QSizeF size(r.w * spriteScale, r.h * spriteScale);
        const QRectF dst(anchor.x() - kRailAnchorSourceX * spriteScale,
                         anchor.y() - kRailAnchorSourceY * spriteScale,
                         size.width(), size.height());
        painter.drawImage(dst, atlas, src);
    }
}

} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    if (argc < 4) {
        std::fprintf(stderr, "usage: MapForge2CoasterVideoProof <output-dir> <atlas> <mapforge-project>\n");
        return 2;
    }
    const QString outputDir = QString::fromLocal8Bit(argv[1]);
    const QString atlasPath = QString::fromLocal8Bit(argv[2]);
    const QString projectPath = QString::fromLocal8Bit(argv[3]);
    QDir().mkpath(outputDir);

    QImage atlas(atlasPath);
    const QSize expectedAtlasSize(
        ch::coaster::kCarPoseAtlasColumns * ch::coaster::kCarPoseFrameWidth,
        ch::coaster::kCarPoseAtlasRows * ch::coaster::kCarPoseFrameHeight);
    if (atlas.isNull() || atlas.size() != expectedAtlasSize) {
        std::fprintf(stderr, "invalid Flame V2 car pose atlas: got %dx%d expected %dx%d\n",
                     atlas.width(), atlas.height(), expectedAtlasSize.width(), expectedAtlasSize.height());
        return 3;
    }

    ch::coaster::CenterlineRoute route;
    QJsonObject project;
    if (!load_project_route(projectPath, route, project) || !route.valid()) {
        std::fprintf(stderr, "failed to construct CH_MAPFORGE_COASTER_PROJECT_V1\n");
        return 4;
    }
    const auto samples = sample_track(route);
    const Projection projection = fit_projection(samples);

    for (int frame = 0; frame < kFrameCount; ++frame) {
        QImage image(kWidth,kHeight,QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        painter.setRenderHint(QPainter::Antialiasing,true);
        painter.setRenderHint(QPainter::SmoothPixmapTransform,true);
        draw_ground(painter,projection,project);
        draw_station(painter,projection);
        draw_supports(painter,projection,route);
        draw_track(painter,projection,samples);
        const double seconds = static_cast<double>(frame) / kFps;
        const double lead = ch::coaster::normalize_route_distance(seconds*kTrainSpeedMps,route.length_m(),true);
        draw_train(painter,projection,atlas,route,lead);
        painter.end();
        const QString path = QStringLiteral("%1/frame_%2.png").arg(outputDir).arg(frame,4,10,QLatin1Char('0'));
        if (!image.save(path,"PNG")) return 5;
    }

    std::printf("CH_MAPFORGE_COASTER_PROJECT_V1 frames=%d fps=%d cars=%d route_m=%.3f points=%zu\n",
                kFrameCount,kFps,ch::coaster::kCoasterTrainCarCount,route.length_m(),route.point_count());
    return 0;
}
