#include <QColor>
#include <QGuiApplication>
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
#include "src/procedural_road_ground_render_plan.h"
#include "src/procedural_road_placement_bridge.h"

namespace {

constexpr int kPreviewWidth = 1280;
constexpr int kPreviewHeight = 720;

QPointF to_qpoint(const ch::ScreenPoint point) {
    return {static_cast<qreal>(point.x), static_cast<qreal>(point.y)};
}

ch::CameraState proof_camera() {
    ch::CameraState camera;
    camera.zoom = 0.82F;
    camera.pan_x = 0.0F;
    camera.pan_y = 15.0F;
    camera.rotation = ch::CameraRotation::r0;
    return camera;
}

void draw_ground(QPainter& painter, const ch::CameraState& camera) {
    const QColor grass_a(105, 139, 94);
    const QColor grass_b(99, 133, 90);
    QPen edge(QColor(72, 102, 70, 125));
    edge.setWidthF(0.75);
    painter.setPen(edge);

    for (int y = -8; y <= 8; ++y) {
        for (int x = -11; x <= 11; ++x) {
            QPolygonF diamond;
            diamond << to_qpoint(ch::world_to_screen_point(
                           static_cast<float>(x), static_cast<float>(y), camera,
                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(
                           static_cast<float>(x + 1), static_cast<float>(y), camera,
                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(
                           static_cast<float>(x + 1), static_cast<float>(y + 1), camera,
                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)))
                    << to_qpoint(ch::world_to_screen_point(
                           static_cast<float>(x), static_cast<float>(y + 1), camera,
                           static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
            painter.setBrush(((x + y) & 1) == 0 ? grass_a : grass_b);
            painter.drawPolygon(diamond);
        }
    }
}

// Append every triangle to one painter path instead of rasterizing triangles one
// at a time. QPainter antialiasing on individually filled triangles exposes the
// shared edges as dark hairlines, which made a perfectly continuous ribbon look
// like a ladder. Filling the whole road network as one winding path preserves
// the same mesh geometry while antialiasing only the actual outer silhouette.
void append_2d_mesh_path(QPainterPath& path, const ProceduralRoad2DMesh& mesh,
                         const ch::CameraState& camera) {
    if (mesh.empty()) return;

    for (std::size_t index = 0; index + 2U < mesh.indices.size(); index += 3U) {
        QPolygonF triangle;
        for (std::size_t corner = 0; corner < 3U; ++corner) {
            const ProceduralRoad2DVertex& vertex =
                mesh.vertices.at(mesh.indices[index + corner]);
            triangle << to_qpoint(ch::world_to_screen_point(
                vertex.position.x, vertex.position.y, camera,
                static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
        }
        path.addPolygon(triangle);
        path.closeSubpath();
    }
}

void draw_centerlines(QPainter& painter, const ProceduralRoadGraph& graph,
                      const ch::CameraState& camera) {
    QPen centerline(QColor(236, 221, 159, 220));
    centerline.setWidthF(1.7);
    centerline.setStyle(Qt::DashLine);
    centerline.setCapStyle(Qt::FlatCap);
    painter.setPen(centerline);
    painter.setBrush(Qt::NoBrush);

    for (const ProceduralRoadGraphSegment& graph_segment : graph.segments()) {
        const auto spline = procedural_road_visual_spline_2d(graph, graph_segment.id);
        if (!spline || !procedural_road_spline_is_ground_only(*spline)) continue;

        // Center markings stop before real conflict areas. Degree-2 curves keep
        // their continuous marking; tees and crosses get a clean central box.
        constexpr float kJunctionGapT = 0.34F;
        float begin_t = 0.0F;
        float end_t = 1.0F;
        if (graph.degree(graph_segment.start_node) >= 3U) begin_t = kJunctionGapT;
        if (graph.degree(graph_segment.end_node) >= 3U) end_t = 1.0F - kJunctionGapT;
        if (begin_t >= end_t) continue;

        QPainterPath path;
        constexpr int kSamples = 36;
        for (int sample = 0; sample <= kSamples; ++sample) {
            const float alpha = static_cast<float>(sample) / static_cast<float>(kSamples);
            const float t = begin_t + (end_t - begin_t) * alpha;
            const ProceduralRoad2DPoint point = procedural_road_sample_cubic_2d(*spline, t);
            const QPointF screen = to_qpoint(ch::world_to_screen_point(
                point.x, point.y, camera,
                static_cast<float>(kPreviewWidth), static_cast<float>(kPreviewHeight)));
            if (sample == 0) path.moveTo(screen);
            else path.lineTo(screen);
        }
        painter.drawPath(path);
    }
}

ProceduralRoadPlacementBridge build_proof_network() {
    ProceduralRoadPlacementBridge bridge;

    std::vector<TileCoordinate> east_west;
    for (int x = -7; x <= 7; ++x) east_west.push_back({x, 0});
    (void)bridge.mirror_tile_segment(east_west, ProceduralRoadClass::local, 0.0F);

    std::vector<TileCoordinate> north_south;
    for (int y = -5; y <= 5; ++y) north_south.push_back({0, y});
    (void)bridge.mirror_tile_segment(north_south, ProceduralRoadClass::local, 0.0F);

    // This branch deliberately proves both a T-junction at {4,0} and two
    // degree-2 90-degree corners. The visual layer should round the corners
    // while RoadManager-compatible tile topology remains unchanged.
    const std::vector<TileCoordinate> branch = {
        {4, 0}, {4, 1}, {4, 2}, {5, 2}, {6, 2}, {6, 3}, {6, 4},
    };
    (void)bridge.mirror_tile_segment(branch, ProceduralRoadClass::local, 0.0F);

    return bridge;
}

void draw_overlay(QPainter& painter, const ProceduralRoadGroundRenderPlan& plan,
                  const ProceduralRoadGraph& graph) {
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(24, 30, 33, 220));
    painter.drawRoundedRect(QRectF(18.0, 18.0, 690.0, 116.0), 8.0, 8.0);

    painter.setPen(QColor(237, 243, 244));
    painter.drawText(QPointF(34.0, 46.0),
                     QStringLiteral("City Horizon — CH_PROCEDURAL_ROAD_2D_RENDER_V1"));
    painter.drawText(QPointF(34.0, 72.0),
                     QStringLiteral("Smooth XY corners + seam-free surface; no road Z, pillars or viaduct mesh"));
    painter.drawText(QPointF(34.0, 98.0),
                     QString("Segments: %1  |  2D ribbons: %2  |  needed junction patches: %3")
                         .arg(graph.segments().size())
                         .arg(plan.segment_meshes.size())
                         .arg(plan.junction_meshes.size()));
    painter.drawText(QPointF(34.0, 122.0),
                     QStringLiteral("Center markings clear conflict zones; RoadManager topology remains authoritative"));
}

bool render_png(const std::filesystem::path& output) {
    const ch::CameraState camera = proof_camera();
    ProceduralRoadPlacementBridge bridge = build_proof_network();
    const ProceduralRoadGroundRenderPlan plan =
        build_procedural_road_ground_render_plan(bridge);
    if (plan.empty() || plan.skipped_elevated_segments != 0U ||
        plan.skipped_mixed_junctions != 0U) {
        std::cerr << "Procedural 2D road plan did not pass the flat-ground contract.\n";
        return false;
    }

    QImage image(kPreviewWidth, kPreviewHeight, QImage::Format_ARGB32_Premultiplied);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.fillRect(image.rect(), QColor(72, 97, 77));

    draw_ground(painter, camera);

    // One fill for the complete road surface prevents antialiased shared edges
    // from becoming visible as transverse "ladder" lines in the proof image.
    QPainterPath road_surface;
    road_surface.setFillRule(Qt::WindingFill);
    for (const ProceduralRoad2DMesh& mesh : plan.segment_meshes) {
        append_2d_mesh_path(road_surface, mesh, camera);
    }
    for (const ProceduralRoad2DMesh& patch : plan.junction_meshes) {
        append_2d_mesh_path(road_surface, patch, camera);
    }
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(52, 57, 60));
    painter.drawPath(road_surface);

    draw_centerlines(painter, bridge.graph(), camera);
    draw_overlay(painter, plan, bridge.graph());
    painter.end();

    const std::filesystem::path parent = output.parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent);
    return image.save(QString::fromStdString(output.string()), "PNG");
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc < 2) {
        std::cerr << "Usage: MapForge2ProceduralRoadPngProof <output.png>\n";
        return 2;
    }

    const std::filesystem::path output = argv[1];
    if (!render_png(output)) {
        std::cerr << "Failed to write procedural 2D road proof: " << output.string() << '\n';
        return 1;
    }

    std::cout << "Wrote procedural 2D road proof: " << output.string() << '\n';
    return 0;
}
