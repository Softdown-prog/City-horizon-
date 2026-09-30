#include "src/ch_core/projection.h"
#include "src/ch_core/terrain_heightfield.h"

#include <QColor>
#include <QFont>
#include <QGuiApplication>
#include <QImage>
#include <QPainter>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
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

QPointF projectedVertex(const ch::TerrainHeightField& field, const int x, const int y,
                        const ch::CameraState& camera) {
    ch::ScreenPoint point = ch::world_to_screen_point(
        static_cast<float>(x), static_cast<float>(y), camera,
        static_cast<float>(kWidth), static_cast<float>(kHeight));
    point.y -= field.height_at(x, y) * kHeightPixelsPerUnit * camera.zoom;
    return QPointF(point.x, point.y);
}

QPolygonF tilePolygon(const ch::TerrainHeightField& field, const int x, const int y,
                      const ch::CameraState& camera) {
    return QPolygonF{
        projectedVertex(field, x, y, camera),
        projectedVertex(field, x + 1, y, camera),
        projectedVertex(field, x + 1, y + 1, camera),
        projectedVertex(field, x, y + 1, camera),
    };
}

float tileAverageHeight(const ch::TerrainHeightField& field, const int x, const int y) {
    return (field.height_at(x, y) + field.height_at(x + 1, y) +
            field.height_at(x + 1, y + 1) + field.height_at(x, y + 1)) * 0.25F;
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

void drawFrame(const ch::TerrainHeightField& field, const ch::CameraState& camera,
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

            const QPolygonF polygon = tilePolygon(field, x, y, camera);
            painter.setPen(gridPen);
            painter.setBrush(terrainColor(tileAverageHeight(field, x, y)));
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

    QFont titleFont = painter.font();
    titleFont.setBold(true);
    titleFont.setPointSize(17);
    painter.setFont(titleFont);
    painter.setPen(QColor(239, 245, 239));
    painter.drawText(QPointF(42, 55), QStringLiteral("MapForge · CH_TERRAIN_HEIGHTFIELD_V1"));

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
    painter.drawText(QPointF(42, 108), QStringLiteral("Elevação contínua por vértices compartilhados · câmera CH_CAMERA_V1"));
    painter.drawText(QPointF(42, kHeight - 37),
                     QStringLiteral("frame %1 · raio %2").arg(frameIndex + 1, 2, 10, QLatin1Char('0')).arg(brushRadius, 0, 'f', 1));

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

    ch::TerrainHeightField field;
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
            field.apply_brush(-2.0F, -1.0F, 3.15F, 0.24F, ch::TerrainBrushMode::raise);
        } else if (frame < 24) {
            brushX = 2.1F;
            brushY = 1.3F;
            operation = QStringLiteral("REBAIXAR");
            field.apply_brush(2.1F, 1.3F, 3.15F, 0.22F, ch::TerrainBrushMode::lower);
        } else {
            brushX = 0.0F;
            brushY = 0.0F;
            brushRadius = 5.0F;
            operation = QStringLiteral("SUAVIZAR");
            field.apply_brush(0.0F, 0.0F, 5.0F, 0.42F, ch::TerrainBrushMode::smooth);
        }

        drawFrame(field, camera, brushX, brushY, brushRadius, operation, frame, outputDir);
    }

    return 0;
}
