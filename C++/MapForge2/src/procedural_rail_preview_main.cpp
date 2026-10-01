#include <QColor>
#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QPen>
#include <QPointF>
#include <QPolygonF>
#include <QString>

#include <array>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#include "src/ch_core/projection.h"
#include "src/rail_path_builder.h"
#include "src/rail_system.h"

namespace {

constexpr int kPreviewWidth = 1280;
constexpr int kPreviewHeight = 720;
constexpr float kHalfPi = 1.57079632679489661923F;

QPointF to_qpoint(const ch::ScreenPoint point) {
    return {static_cast<qreal>(point.x), static_cast<qreal>(point.y)};
}

ch::CameraState preview_camera() {
    ch::CameraState camera;
    camera.zoom = 0.82F;
    camera.pan_x = -105.0F;
    camera.pan_y = 28.0F;
    return camera;
}

void draw_ground(QPainter& painter, const ch::CameraState& camera) {
    const QColor grass_a(105, 142, 94);
    const QColor grass_b(99, 135, 90);
    QPen edge_pen(QColor(72, 102, 69, 145));
    edge_pen.setWidthF(0.8);
    painter.setPen(edge_pen);

    for (int y = -13; y <= 15; ++y) {
        for (int x = -15; x <= 20; ++x) {
            QPolygonF diamond;
            diamond << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera,
                                                           kPreviewWidth, kPreviewHeight))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera,
                                                           kPreviewWidth, kPreviewHeight))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera,
                                                           kPreviewWidth, kPreviewHeight))
                    << to_qpoint(ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera,
                                                           kPreviewWidth, kPreviewHeight));
            painter.setBrush(((x + y) & 1) == 0 ? grass_a : grass_b);
            painter.drawPolygon(diamond);
        }
    }
}

void draw_mesh(QPainter& painter, const RailMesh& mesh, const QColor& color,
               const ch::CameraState& camera, const bool outline = false) {
    painter.setBrush(color);
    painter.setPen(outline ? QPen(color.darker(150), 0.55) : Qt::NoPen);

    for (std::size_t index = 0; index + 2 < mesh.indices.size(); index += 3) {
        QPolygonF triangle;
        for (int corner = 0; corner < 3; ++corner) {
            const std::uint32_t vertex_index = mesh.indices[index + static_cast<std::size_t>(corner)];
            if (vertex_index >= mesh.vertices.size()) return;
            const RailMeshVertex& vertex = mesh.vertices[vertex_index];
            triangle << to_qpoint(ch::world_to_screen_point(
                vertex.position.x, vertex.position.y, vertex.position.z,
                camera, kPreviewWidth, kPreviewHeight));
        }
        painter.drawPolygon(triangle);
    }
}

bool draw_geometry(QPainter& painter, const RailGeometry& geometry,
                   const RailProfile& profile, const ch::CameraState& camera) {
    const std::array<const RailMesh*, 4> meshes{
        &geometry.ballast, &geometry.sleepers, &geometry.left_rail, &geometry.right_rail};
    for (const RailMesh* mesh : meshes) {
        if (!RailMeshBuilder::validate_mesh(*mesh, profile).ok()) return false;
    }

    draw_mesh(painter, geometry.ballast, QColor(96, 82, 68), camera, true);
    draw_mesh(painter, geometry.sleepers, QColor(91, 58, 38), camera, true);
    draw_mesh(painter, geometry.left_rail, QColor(102, 111, 116), camera, true);
    draw_mesh(painter, geometry.right_rail, QColor(102, 111, 116), camera, true);
    return true;
}

bool build_and_draw(QPainter& painter, const RailSplineSegment& segment,
                    const RailProfile& profile, const ch::CameraState& camera) {
    const RailBuildResult built = RailMeshBuilder::build(segment, profile);
    if (!built.ok()) {
        std::cerr << "Rail build rejected: " << built.validation.message << '\n';
        return false;
    }
    return draw_geometry(painter, built.geometry, profile, camera);
}

bool render_rail_scene(QPainter& painter) {
    const RailProfile profile{};
    const ch::CameraState camera = preview_camera();
    draw_ground(painter, camera);

    // Primary connected route: straight -> broad 90-degree curve -> straight.
    const RailPathBuildResult approach = RailPathBuilder::straight(
        {-10.0F, -1.5F, 0.0F}, 0.0F, 7.0F, 32, profile);
    if (!approach.ok()) return false;

    const RailPathBuildResult curve = RailPathBuilder::quarter_curve(
        approach.segment.end, 0.0F, 4.5F, RailTurnDirection::left, 56, profile);
    if (!curve.ok()) return false;
    if (!RailMeshBuilder::validate_connection(approach.segment, curve.segment, profile).ok()) return false;

    const RailPathBuildResult exit = RailPathBuilder::straight(
        curve.segment.end, kHalfPi, 5.5F, 32, profile);
    if (!exit.ok()) return false;
    if (!RailMeshBuilder::validate_connection(curve.segment, exit.segment, profile).ok()) return false;

    if (!build_and_draw(painter, approach.segment, profile, camera)) return false;
    if (!build_and_draw(painter, curve.segment, profile, camera)) return false;
    if (!build_and_draw(painter, exit.segment, profile, camera)) return false;

    // Separate switch proof on the same canonical MapForge ground. Both routes
    // are generated by RailPathBuilder::turnout and validated before drawing.
    constexpr float turnout_angle = 0.3490658503988659F; // 20 degrees
    const RailTurnoutBuildResult turnout = RailPathBuilder::turnout(
        {-8.0F, 6.5F, 0.0F}, 0.0F, 7.0F, turnout_angle,
        RailTurnDirection::right, 48, profile);
    if (!turnout.ok()) return false;

    if (!build_and_draw(painter, turnout.through, profile, camera)) return false;
    if (!build_and_draw(painter, turnout.diverging, profile, camera)) return false;

    const RailPathBuildResult through_extension = RailPathBuilder::straight(
        turnout.through.end, 0.0F, 4.0F, 24, profile);
    if (!through_extension.ok()) return false;
    if (!RailMeshBuilder::validate_connection(turnout.through, through_extension.segment, profile).ok()) return false;
    if (!build_and_draw(painter, through_extension.segment, profile, camera)) return false;

    const RailPathBuildResult branch_extension = RailPathBuilder::straight(
        turnout.diverging.end, turnout.diverging_exit_heading_radians, 4.0F, 24, profile);
    if (!branch_extension.ok()) return false;
    if (!RailMeshBuilder::validate_connection(turnout.diverging, branch_extension.segment, profile).ok()) return false;
    if (!build_and_draw(painter, branch_extension.segment, profile, camera)) return false;

    painter.setPen(QColor(245, 248, 240));
    painter.setBrush(QColor(21, 27, 30, 225));
    painter.drawRoundedRect(QRectF(24.0, 22.0, 430.0, 82.0), 12.0, 12.0);
    painter.drawText(QPointF(42.0, 52.0), QStringLiteral("CITY HORIZON - MAPFORGE PROCEDURAL RAIL"));
    painter.drawText(QPointF(42.0, 77.0), QStringLiteral("CH_CAMERA_V1 | straight + curve + turnout | real XYZ mesh"));

    return true;
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc < 2) {
        std::cerr << "Usage: MapForge2ProceduralRailPngProof <output.png>\n";
        return 2;
    }

    QImage image(kPreviewWidth, kPreviewHeight, QImage::Format_ARGB32_Premultiplied);
    image.fill(QColor(91, 124, 84));
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    if (!render_rail_scene(painter)) {
        painter.end();
        std::cerr << "Procedural rail MapForge proof rejected by structural validation\n";
        return 1;
    }
    painter.end();

    const std::filesystem::path output = argv[1];
    const std::filesystem::path parent = output.parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    if (!image.save(QString::fromStdString(output.string()), "PNG")) {
        std::cerr << "Failed to write procedural rail MapForge proof: " << output.string() << '\n';
        return 1;
    }

    std::cout << "Wrote procedural rail MapForge proof: " << output.string() << '\n';
    return 0;
}
