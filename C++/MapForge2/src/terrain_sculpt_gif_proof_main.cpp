#include "src/ch_core/map_document.h"
#include "src/ch_core/procedural_tile_2d.h"
#include "src/ch_core/projection.h"

#include <QColor>
#include <QFont>
#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QPainterPathStroker>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <string>

namespace {

constexpr int kWidth = 960;
constexpr int kHeight = 640;
constexpr int kMinTile = -6;
constexpr int kMaxTile = 5;
constexpr float kHeightPixelsPerUnit = 16.0F; // Matches MapRenderer heightfield deformation.

struct PathCell {
    int x = 0;
    int y = 0;
};

// One connected pilot deliberately contains ends, straights, rounded corners
// and a T junction. It crosses both sculpt zones so the exact same logical 2D
// path automatically becomes flat, ramp or stairs as the heightfield changes.
constexpr std::array<PathCell, 17> kPathCells = {{
    {-5, -2}, {-4, -2}, {-3, -2}, {-2, -2}, {-1, -2}, {0, -2},
    {0, -1}, {0, 0}, {1, 0}, {2, 0}, {3, 0},
    {3, 1}, {3, 2},
    {0, 1}, {0, 2},
    {-2, -1}, {-2, 0},
}};

QPointF projectedPoint(const ch::MapDocument& document, const float worldX, const float worldY,
                       const ch::CameraState& camera) {
    ch::ScreenPoint point = ch::world_to_screen_point(
        worldX, worldY, camera,
        static_cast<float>(kWidth), static_cast<float>(kHeight));
    point.y -= document.terrain_heightfield().sample(worldX, worldY) *
               kHeightPixelsPerUnit * camera.zoom;
    return QPointF(point.x, point.y);
}

QPolygonF tilePolygon(const ch::MapDocument& document, const int x, const int y,
                      const ch::CameraState& camera) {
    return QPolygonF{
        projectedPoint(document, static_cast<float>(x), static_cast<float>(y), camera),
        projectedPoint(document, static_cast<float>(x + 1), static_cast<float>(y), camera),
        projectedPoint(document, static_cast<float>(x + 1), static_cast<float>(y + 1), camera),
        projectedPoint(document, static_cast<float>(x), static_cast<float>(y + 1), camera),
    };
}

float tileAverageHeight(const ch::MapDocument& document, const int x, const int y) {
    return (document.terrain_height_at(x, y) + document.terrain_height_at(x + 1, y) +
            document.terrain_height_at(x + 1, y + 1) + document.terrain_height_at(x, y + 1)) * 0.25F;
}

QColor terrainColor(const float height) {
    const float normalized = std::clamp((height + 3.0F) / 6.0F, 0.0F, 1.0F);
    const int r = static_cast<int>(76.0F + normalized * 38.0F);
    const int g = static_cast<int>(118.0F + normalized * 62.0F);
    const int b = static_cast<int>(70.0F + normalized * 24.0F);
    return QColor(r, g, b);
}

bool insideBrush(const int tileX, const int tileY, const float centerX, const float centerY, const float radius) {
    const float dx = (static_cast<float>(tileX) + 0.5F) - centerX;
    const float dy = (static_cast<float>(tileY) + 0.5F) - centerY;
    return std::sqrt(dx * dx + dy * dy) <= radius;
}

bool isPathCell(const int x, const int y) {
    return std::any_of(kPathCells.begin(), kPathCells.end(), [x, y](const PathCell& cell) {
        return cell.x == x && cell.y == y;
    });
}

TileConnectionMask pathConnectionMask(const int x, const int y) {
    TileConnectionMask mask = 0;
    for (const CardinalDirection direction : kCardinalDirections) {
        const TileOffset offset = direction_offset(direction);
        if (isPathCell(x + offset.x, y + offset.y)) {
            mask = static_cast<TileConnectionMask>(mask | connection_bit(direction));
        }
    }
    return mask;
}

QPointF pathEdgePoint(const ch::MapDocument& document, const int x, const int y,
                      const CardinalDirection direction, const ch::CameraState& camera) {
    switch (direction) {
        case CardinalDirection::north:
            return projectedPoint(document, static_cast<float>(x) + 0.5F, static_cast<float>(y), camera);
        case CardinalDirection::east:
            return projectedPoint(document, static_cast<float>(x + 1), static_cast<float>(y) + 0.5F, camera);
        case CardinalDirection::south:
            return projectedPoint(document, static_cast<float>(x) + 0.5F, static_cast<float>(y + 1), camera);
        case CardinalDirection::west:
            return projectedPoint(document, static_cast<float>(x), static_cast<float>(y) + 0.5F, camera);
    }
    return projectedPoint(document, static_cast<float>(x) + 0.5F, static_cast<float>(y) + 0.5F, camera);
}

QPainterPath pathCenterline(const ch::MapDocument& document, const PathCell& cell,
                            const TileConnectionMask mask, const ch::CameraState& camera) {
    const QPointF center = projectedPoint(document,
                                          static_cast<float>(cell.x) + 0.5F,
                                          static_cast<float>(cell.y) + 0.5F,
                                          camera);
    QPainterPath line;
    if (mask == 0) {
        line.addEllipse(center, 1.0, 1.0);
        return line;
    }

    for (const CardinalDirection direction : kCardinalDirections) {
        if (!has_connection(mask, direction)) continue;
        line.moveTo(center);
        line.lineTo(pathEdgePoint(document, cell.x, cell.y, direction, camera));
    }
    return line;
}

QPainterPath strokedPathShape(const QPainterPath& centerline, const qreal width) {
    QPainterPathStroker stroker;
    stroker.setWidth(width);
    stroker.setCapStyle(Qt::RoundCap);
    stroker.setJoinStyle(Qt::RoundJoin);
    return stroker.createStroke(centerline);
}

void drawProceduralPathDetails(QPainter& painter, const ch::MapDocument& document,
                               const PathCell& cell, const ch::ProceduralTileRecipe& recipe,
                               const QPainterPath& surfaceShape, const ch::CameraState& camera,
                               const qreal innerWidth) {
    if (recipe.vertical_profile == ch::ProceduralTileVerticalProfile::flat) return;

    const QPointF low = pathEdgePoint(document, cell.x, cell.y, recipe.low_edge, camera);
    const QPointF high = pathEdgePoint(document, cell.x, cell.y, recipe.high_edge, camera);
    QPointF axis = high - low;
    const qreal axisLength = std::hypot(axis.x(), axis.y());
    if (axisLength < 0.5) return;
    axis /= axisLength;

    painter.save();
    painter.setClipPath(surfaceShape, Qt::IntersectClip);

    if (recipe.vertical_profile == ch::ProceduralTileVerticalProfile::ramp) {
        // A quiet centre highlight makes the incline readable without changing
        // the approved dirt material into a glossy or 3D-looking surface.
        const QPointF start = low + axis * (axisLength * 0.18);
        const QPointF end = high - axis * (axisLength * 0.18);
        painter.setPen(QPen(QColor(220, 176, 112, 95), 1.4, Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(start, end);
    } else {
        const int visibleSteps = std::clamp(recipe.stair_count, 2, 9);
        const QPointF perpendicular(-axis.y(), axis.x());
        const qreal halfStepWidth = innerWidth * 0.43;

        for (int step = 1; step <= visibleSteps; ++step) {
            const qreal t = static_cast<qreal>(step) / static_cast<qreal>(visibleSteps + 1);
            const QPointF center = low + axis * (axisLength * t);
            const QPointF a = center - perpendicular * halfStepWidth;
            const QPointF b = center + perpendicular * halfStepWidth;

            painter.setPen(QPen(QColor(78, 52, 31, 185), 1.8, Qt::SolidLine, Qt::RoundCap));
            painter.drawLine(a, b);
            painter.setPen(QPen(QColor(226, 184, 120, 105), 0.8, Qt::SolidLine, Qt::RoundCap));
            painter.drawLine(a - axis * 1.3, b - axis * 1.3);
        }
    }

    painter.restore();
}

void drawProceduralPath(QPainter& painter, const ch::MapDocument& document,
                        const ch::CameraState& camera,
                        int& flatCount, int& rampCount, int& stairCount,
                        int& endCount, int& cornerCount, int& junctionCount) {
    const qreal outerWidth = 25.0 * camera.zoom;
    const qreal innerWidth = 18.0 * camera.zoom;

    // First pass: one continuous-looking 2D material network. Round caps create
    // half-moon ends and round joins create curves without extra PNG variants.
    for (const PathCell& cell : kPathCells) {
        const TileConnectionMask mask = pathConnectionMask(cell.x, cell.y);
        const ch::ProceduralTileRecipe recipe =
            ch::make_procedural_tile_2d_recipe(document, cell.x, cell.y, mask);
        const QPainterPath centerline = pathCenterline(document, cell, mask, camera);

        if (mask == 0) {
            const QPointF center = projectedPoint(document,
                                                  static_cast<float>(cell.x) + 0.5F,
                                                  static_cast<float>(cell.y) + 0.5F,
                                                  camera);
            painter.setPen(Qt::NoPen);
            painter.setBrush(QColor(74, 49, 30, 230));
            painter.drawEllipse(center, outerWidth * 0.5, outerWidth * 0.5);
            painter.setBrush(QColor(171, 121, 67, 255));
            painter.drawEllipse(center, innerWidth * 0.5, innerWidth * 0.5);
        } else {
            painter.setBrush(Qt::NoBrush);
            painter.setPen(QPen(QColor(74, 49, 30, 230), outerWidth,
                                Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
            painter.drawPath(centerline);
            painter.setPen(QPen(QColor(171, 121, 67, 255), innerWidth,
                                Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
            painter.drawPath(centerline);
        }

        switch (recipe.vertical_profile) {
            case ch::ProceduralTileVerticalProfile::flat: ++flatCount; break;
            case ch::ProceduralTileVerticalProfile::ramp: ++rampCount; break;
            case ch::ProceduralTileVerticalProfile::stairs: ++stairCount; break;
        }
        switch (recipe.topology) {
            case ch::ProceduralTileTopology::end: ++endCount; break;
            case ch::ProceduralTileTopology::corner: ++cornerCount; break;
            case ch::ProceduralTileTopology::tee:
            case ch::ProceduralTileTopology::cross: ++junctionCount; break;
            default: break;
        }
    }

    // Second pass: slope details sit on top of the complete network, so a
    // neighbouring tile cannot paint over the stair/ramp cue at a shared edge.
    for (const PathCell& cell : kPathCells) {
        const TileConnectionMask mask = pathConnectionMask(cell.x, cell.y);
        const ch::ProceduralTileRecipe recipe =
            ch::make_procedural_tile_2d_recipe(document, cell.x, cell.y, mask);
        const QPainterPath centerline = pathCenterline(document, cell, mask, camera);
        const QPainterPath surfaceShape = strokedPathShape(centerline, innerWidth);
        drawProceduralPathDetails(painter, document, cell, recipe, surfaceShape, camera, innerWidth);
    }
}

void drawFrame(const ch::MapDocument& document, const ch::CameraState& camera,
               const float brushX, const float brushY, const float brushRadius,
               const QString& operation, const int frameIndex,
               const std::filesystem::path& outputDir) {
    QImage image(kWidth, kHeight, QImage::Format_ARGB32_Premultiplied);
    image.fill(QColor(36, 48, 42));

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    // Soft viewport panel so the proof reads like a MapForge validation stage.
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(29, 39, 34));
    painter.drawRoundedRect(QRectF(18, 18, kWidth - 36, kHeight - 36), 12, 12);

    const QPen gridPen(QColor(52, 73, 57, 210), 1.0);
    const QPen brushPen(QColor(255, 206, 74, 235), 2.0);

    for (int depth = kMinTile * 2; depth <= (kMaxTile + 1) * 2; ++depth) {
        const int firstX = std::max(kMinTile, depth - kMaxTile);
        const int lastX = std::min(kMaxTile, depth - kMinTile);
        for (int x = firstX; x <= lastX; ++x) {
            const int y = depth - x;
            if (y < kMinTile || y > kMaxTile) continue;

            const QPolygonF polygon = tilePolygon(document, x, y, camera);
            painter.setPen(gridPen);
            painter.setBrush(terrainColor(tileAverageHeight(document, x, y)));
            painter.drawPolygon(polygon);

            if (insideBrush(x, y, brushX, brushY, brushRadius)) {
                QColor overlay = operation == QStringLiteral("REBAIXAR")
                    ? QColor(86, 174, 255, 38)
                    : (operation == QStringLiteral("SUAVIZAR")
                        ? QColor(223, 230, 235, 34)
                        : QColor(255, 206, 74, 38));
                painter.setPen(brushPen);
                painter.setBrush(overlay);
                painter.drawPolygon(polygon);
            }
        }
    }

    int flatCount = 0;
    int rampCount = 0;
    int stairCount = 0;
    int endCount = 0;
    int cornerCount = 0;
    int junctionCount = 0;
    drawProceduralPath(painter, document, camera,
                       flatCount, rampCount, stairCount,
                       endCount, cornerCount, junctionCount);

    QFont titleFont = painter.font();
    titleFont.setBold(true);
    titleFont.setPointSize(17);
    painter.setFont(titleFont);
    painter.setPen(QColor(239, 245, 239));
    painter.drawText(QPointF(42, 55), QStringLiteral("MapForge · CH_PROCEDURAL_TILE_2D_V1"));

    QFont infoFont = painter.font();
    infoFont.setBold(true);
    infoFont.setPointSize(12);
    painter.setFont(infoFont);
    painter.setPen(QColor(255, 211, 91));
    painter.drawText(QPointF(42, 84), QStringLiteral("Pincel: ") + operation);

    infoFont.setBold(false);
    infoFont.setPointSize(10);
    painter.setFont(infoFont);
    painter.setPen(QColor(205, 219, 208));
    painter.drawText(QPointF(42, 108),
                     QStringLiteral("Grid 2D preservado · meia-lua, curva, rampa e escada derivados de vizinhança + heightfield"));
    painter.drawText(QPointF(42, 130),
                     QStringLiteral("perfil: plano %1 · rampa %2 · escada %3")
                         .arg(flatCount).arg(rampCount).arg(stairCount));
    painter.drawText(QPointF(42, 150),
                     QStringLiteral("topologia: pontas %1 · cantos %2 · junções %3")
                         .arg(endCount).arg(cornerCount).arg(junctionCount));
    painter.drawText(QPointF(42, kHeight - 37),
                     QStringLiteral("frame %1 · raio %2 · câmera CH_CAMERA_V1")
                         .arg(frameIndex + 1, 2, 10, QLatin1Char('0')).arg(brushRadius, 0, 'f', 1));

    std::ostringstream filename;
    filename << "frame_" << std::setw(3) << std::setfill('0') << frameIndex << ".png";
    image.save(QString::fromStdString((outputDir / filename.str()).string()), "PNG");
}

} // namespace

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    if (argc < 2) return 2;

    const std::filesystem::path outputDir(argv[1]);
    std::filesystem::create_directories(outputDir);

    ch::MapDocument document = ch::MapDocument::create_empty("procedural-tile-2d-proof", 16, 16);
    ch::CameraState camera{};
    camera.zoom = 0.82F;
    camera.pan_x = 0.0F;
    camera.pan_y = -8.0F;
    camera.rotation = ch::CameraRotation::r0;

    constexpr int kFrames = 36;
    for (int frame = 0; frame < kFrames; ++frame) {
        float brushX = -2.0F;
        float brushY = -1.0F;
        float brushRadius = 3.15F;
        QString operation = QStringLiteral("ELEVAR");

        if (frame < 12) {
            document.apply_terrain_brush(-2.0F, -1.0F, 3.15F, 0.24F, ch::TerrainBrushMode::raise);
        } else if (frame < 24) {
            brushX = 2.1F;
            brushY = 1.3F;
            operation = QStringLiteral("REBAIXAR");
            document.apply_terrain_brush(2.1F, 1.3F, 3.15F, 0.22F, ch::TerrainBrushMode::lower);
        } else {
            brushX = 0.0F;
            brushY = 0.0F;
            brushRadius = 5.0F;
            operation = QStringLiteral("SUAVIZAR");
            document.apply_terrain_brush(0.0F, 0.0F, 5.0F, 0.42F, ch::TerrainBrushMode::smooth);
        }

        drawFrame(document, camera, brushX, brushY, brushRadius, operation, frame, outputDir);
    }

    return 0;
}