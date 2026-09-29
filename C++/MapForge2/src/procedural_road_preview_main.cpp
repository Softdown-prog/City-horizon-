#include <QColor>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPointF>
#include <QPolygonF>
#include <QString>

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <vector>

#include "src/ch_core/projection.h"
#include "src/road_system.h"

namespace {

constexpr int kPreviewWidth = 1280;
constexpr int kPreviewHeight = 720;

QPointF to_qpoint(const ch::ScreenPoint point) {
    return {static_cast<qreal>(point.x), static_cast<qreal>(point.y)};
}

void draw_ground(QPainter& painter, const ch::CameraState& camera) {
    const QColor grass_a(101, 137, 92);
    const QColor grass_b(96, 131, 88);
    QPen edge_pen(QColor(76, 105, 72, 150));
    edge_pen.setWidthF(0.8);
    painter.setPen(edge_pen);

    for (int y = -7; y <= 7; ++y) {
        for (int x = -6; x <= 15; ++x) {
            QPolygonF diamond;
            diamond << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera,
                                                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera,
                                                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera,
                                                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera,
                                                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
            painter.setBrush(((x + y) & 1) == 0 ? grass_a : grass_b);
            painter.drawPolygon(diamond);
        }
    }
}

void draw_support(QPainter& painter, const RoadWorldPoint3& point, const ch::CameraState& camera) {
    if (point.z <= 0.05F) return;
    const ch::ScreenPoint top = ch::world_to_screen_point(point.x, point.y, point.z, camera,
                                                          static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight));
    const ch::ScreenPoint bottom = ch::world_to_screen_point(point.x, point.y, 0.0F, camera,
                                                             static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight));
    QPen shadow(QColor(45, 49, 52, 115));
    shadow.setWidthF(12.0);
    shadow.setCapStyle(Qt::FlatCap);
    painter.setPen(shadow);
    painter.drawLine(to_qpoint(top), to_qpoint(bottom));

    QPen pillar(QColor(122, 126, 126));
    pillar.setWidthF(7.0);
    pillar.setCapStyle(Qt::FlatCap);
    painter.setPen(pillar);
    painter.drawLine(to_qpoint(top), to_qpoint(bottom));
}

void draw_mesh(QPainter& painter, const RoadMesh& mesh, const ch::CameraState& camera,
               const QColor& fill, const QColor& edge) {
    if (mesh.empty()) return;
    painter.setBrush(fill);
    QPen edge_pen(edge);
    edge_pen.setWidthF(0.8);
    painter.setPen(edge_pen);

    for (std::size_t index = 0; index + 2 < mesh.indices.size(); index += 3) {
        QPolygonF triangle;
        for (int corner = 0; corner < 3; ++corner) {
            const RoadMeshVertex& vertex = mesh.vertices[mesh.indices[index + static_cast<std::size_t>(corner)]];
            triangle << to_qpoint(ch::world_to_screen_point(
                vertex.position.x, vertex.position.y, vertex.position.z,
                camera, static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
        }
        painter.drawPolygon(triangle);
    }
}

void draw_centerline(QPainter& painter, const RoadSplineSegment& segment, const ch::CameraState& camera) {
    QPainterPath path;
    constexpr int kSamples = 64;
    for (int index = 0; index <= kSamples; ++index) {
        const float t = static_cast<float>(index) / static_cast<float>(kSamples);
        const RoadWorldPoint3 point = RoadMeshBuilder::sample_cubic(segment, t);
        const QPointF screen = to_qpoint(ch::world_to_screen_point(
            point.x, point.y, point.z + 0.012F,
            camera, static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
        if (index == 0) path.moveTo(screen);
        else path.lineTo(screen);
    }
    QPen lane_pen(QColor(235, 220, 157, 220));
    lane_pen.setWidthF(2.0);
    lane_pen.setStyle(Qt::DashLine);
    painter.setPen(lane_pen);
    painter.setBrush(Qt::NoBrush);
    painter.drawPath(path);
}

} // namespace

int main(int argc, char** argv) {
    const std::filesystem::path output = argc > 1
        ? std::filesystem::path(argv[1])
        : std::filesystem::path("procedural_road_preview.png");

    QImage image(kPreviewWidth, kPreviewHeight, QImage::Format_ARGB32_Premultiplied);
    image.fill(QColor(71, 96, 76));

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    ch::CameraState camera;
    camera.zoom = 0.72F;
    camera.pan_x = -90.0F;
    camera.pan_y = -35.0F;

    draw_ground(painter, camera);

    std::vector<RoadSplineSegment> segments;
    segments.push_back({
        {-4.0F, 0.0F, 0.0F},
        {-2.7F, 0.0F, 0.0F},
        {-1.3F, 0.0F, 0.0F},
        {0.0F, 0.0F, 0.0F},
        0.78F, 1.0F, 18,
    });
    segments.push_back({
        {0.0F, 0.0F, 0.0F},
        {1.7F, 2.4F, 0.0F},
        {4.3F, -2.4F, 0.0F},
        {6.0F, 0.0F, 0.0F},
        0.78F, 1.0F, 42,
    });
    segments.push_back({
        {6.0F, 0.0F, 0.0F},
        {7.4F, 0.0F, 0.10F},
        {8.6F, 0.0F, 1.15F},
        {10.0F, 0.0F, 1.20F},
        0.78F, 1.0F, 26,
    });
    segments.push_back({
        {10.0F, 0.0F, 1.20F},
        {11.0F, 0.0F, 1.20F},
        {12.0F, 0.0F, 1.20F},
        {13.0F, 0.0F, 1.20F},
        0.78F, 1.0F, 20,
    });

    for (const float t : {0.20F, 0.48F, 0.76F}) {
        draw_support(painter, RoadMeshBuilder::sample_cubic(segments[2], t), camera);
    }
    for (const float t : {0.18F, 0.50F, 0.82F}) {
        draw_support(painter, RoadMeshBuilder::sample_cubic(segments[3], t), camera);
    }

    const QColor asphalt(52, 57, 60);
    const QColor asphalt_edge(34, 38, 40);
    for (const RoadSplineSegment& segment : segments) {
        const RoadMesh mesh = RoadMeshBuilder::build_cubic(segment);
        draw_mesh(painter, mesh, camera, asphalt, asphalt_edge);
        draw_centerline(painter, segment, camera);
    }

    painter.end();

    const std::filesystem::path parent = output.parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    if (!image.save(QString::fromStdString(output.string()), "PNG")) {
        std::cerr << "Failed to write procedural road preview: " << output.string() << '\n';
        return 1;
    }

    std::cout << "Wrote procedural road preview: " << output.string() << '\n';
    return 0;
}
