#include "src/ch_core/map_document.h"
#include "src/ch_core/projection.h"

#include <QColor>
#include <QImage>
#include <QPainter>
#include <QPolygonF>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <limits>
#include <optional>
#include <string>

namespace {

constexpr int kWidth = 1024;
constexpr int kHeight = 768;
constexpr float kGrassOpaqueLeft = 53.0F;
constexpr float kGrassOpaqueTop = 23.0F;
constexpr float kGrassOpaqueWidth = 1175.0F;
constexpr float kTileWidth = 128.0F;

QPolygonF tilePolygon(const int x, const int y, const ch::CameraState& camera) {
    const auto a = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, kWidth, kHeight);
    const auto b = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, kWidth, kHeight);
    const auto c = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, kWidth, kHeight);
    const auto d = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, kWidth, kHeight);
    return QPolygonF{QPointF(a.x, a.y), QPointF(b.x, b.y), QPointF(c.x, c.y), QPointF(d.x, d.y)};
}

std::optional<QPointF> opaqueBottomAnchor(const QImage& source) {
    if (source.isNull()) return std::nullopt;
    const QImage image = source.convertToFormat(QImage::Format_ARGB32);
    int minX = image.width();
    int maxX = -1;
    int maxY = -1;
    for (int y = 0; y < image.height(); ++y) {
        const QRgb* line = reinterpret_cast<const QRgb*>(image.constScanLine(y));
        for (int x = 0; x < image.width(); ++x) {
            if (qAlpha(line[x]) <= 8) continue;
            minX = std::min(minX, x);
            maxX = std::max(maxX, x);
            maxY = std::max(maxY, y);
        }
    }
    if (maxX < minX || maxY < 0) return std::nullopt;
    return QPointF((static_cast<double>(minX) + static_cast<double>(maxX)) * 0.5,
                   static_cast<double>(maxY));
}

void drawAnchoredSprite(QPainter& painter, const QImage& sprite, const int tileX, const int tileY,
                        const ch::CameraState& camera, const float scale = 1.0F) {
    const auto anchor = opaqueBottomAnchor(sprite);
    if (!anchor) return;
    const auto ground = ch::world_to_screen_point(static_cast<float>(tileX) + 0.5F,
                                                  static_cast<float>(tileY) + 0.5F,
                                                  camera, kWidth, kHeight);
    const QSizeF targetSize(sprite.width() * scale, sprite.height() * scale);
    const QPointF targetAnchor(anchor->x() * scale, anchor->y() * scale);
    const QRectF target(QPointF(ground.x - targetAnchor.x(), ground.y - targetAnchor.y()), targetSize);
    painter.drawImage(target, sprite);
}

void drawGrassTile(QPainter& painter, const QImage& grass, const int x, const int y,
                   const ch::CameraState& camera) {
    const ch::WorldPoint visualTop = ch::tile_visual_top_world(x, y, camera.rotation);
    const auto top = ch::world_to_screen_point(visualTop.x, visualTop.y, camera, kWidth, kHeight);
    const float scale = (kTileWidth / kGrassOpaqueWidth) * camera.zoom;
    const QRectF destination(top.x - (kTileWidth * camera.zoom * 0.5F) - (kGrassOpaqueLeft * scale),
                             top.y - (kGrassOpaqueTop * scale),
                             grass.width() * scale,
                             grass.height() * scale);
    painter.drawImage(destination, grass);
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 5) {
        std::cerr << "usage: MapForge2MapCapture <output.png> <tree.png> <repo-root> <map.json>\n";
        return 2;
    }

    const std::filesystem::path outputPath = argv[1];
    const std::filesystem::path treePath = argv[2];
    const std::filesystem::path repoRoot = argv[3];
    const std::filesystem::path mapPath = argv[4];

    const auto document = ch::MapDocument::load_from_file(mapPath.string());
    if (!document) {
        std::cerr << "unable to load map: " << mapPath.string() << "\n";
        return 3;
    }

    const QImage grass(QString::fromStdString((repoRoot / "assets/terrain/grass_isometric_01.png").string()));
    const QImage tree(QString::fromStdString(treePath.string()));
    const QImage bakery(QString::fromStdString((repoRoot / "assets/buildings/bakery_01_lvl1.png").string()));
    if (grass.isNull()) {
        std::cerr << "unable to load canonical grass texture\n";
        return 4;
    }
    if (tree.isNull()) {
        std::cerr << "unable to load tree sprite: " << treePath.string() << "\n";
        return 5;
    }

    QImage frame(kWidth, kHeight, QImage::Format_ARGB32);
    frame.fill(QColor(65, 88, 71));

    ch::CameraState camera{};
    camera.zoom = 0.92F;
    camera.rotation = ch::CameraRotation::r0;
    const auto originScreen = ch::world_to_screen_point(0.5F, 0.5F, camera, kWidth, kHeight);
    camera.pan_x += kWidth * 0.50F - originScreen.x;
    camera.pan_y += kHeight * 0.57F - originScreen.y;

    QPainter painter(&frame);
    painter.setRenderHint(QPainter::Antialiasing, false);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    constexpr int minTile = -7;
    constexpr int maxTile = 7;
    for (int depth = minTile * 2; depth <= maxTile * 2; ++depth) {
        const int firstX = std::max(minTile, depth - maxTile);
        const int lastX = std::min(maxTile, depth - minTile);
        for (int x = firstX; x <= lastX; ++x) {
            const int y = depth - x;
            drawGrassTile(painter, grass, x, y, camera);
        }
    }

    QPen roadEdge(QColor(55, 59, 61, 220));
    roadEdge.setWidthF(1.0);
    painter.setPen(roadEdge);
    painter.setBrush(QColor(78, 82, 84, 232));
    for (const auto& road : document->roads()) {
        painter.drawPolygon(tilePolygon(road.tile_x, road.tile_y, camera));
    }

    // Context building first, then the candidate tree at the canonical review tile.
    if (!bakery.isNull()) {
        drawAnchoredSprite(painter, bakery, 3, -1, camera, 1.0F);
    }
    drawAnchoredSprite(painter, tree, 0, 0, camera, 1.0F);

    // Exact capture marker: one-pixel yellow point at the logical tree tile centre.
    const auto treeGround = ch::world_to_screen_point(0.5F, 0.5F, camera, kWidth, kHeight);
    painter.setPen(QColor(245, 196, 64, 210));
    painter.drawPoint(QPointF(treeGround.x, treeGround.y));
    painter.end();

    std::filesystem::create_directories(outputPath.parent_path());
    if (!frame.save(QString::fromStdString(outputPath.string()), "PNG")) {
        std::cerr << "failed to save capture: " << outputPath.string() << "\n";
        return 6;
    }

    std::cout << "mapForgeDeterministicCapture: PASS\n";
    std::cout << "output=" << outputPath.string() << "\n";
    std::cout << "tree=" << treePath.string() << "\n";
    std::cout << "map=" << mapPath.string() << "\n";
    return 0;
}
