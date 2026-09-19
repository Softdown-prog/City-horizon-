#include "src/ch_core/projection.h"

#include <QColor>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QPainterPath>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>

namespace {

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

QColor colorOr(const QJsonObject& object, const char* key, const QColor& fallback) {
    const QString value = object.value(key).toString();
    if (value.isEmpty()) return fallback;
    const QColor parsed(value);
    return parsed.isValid() ? parsed : fallback;
}

QPointF pairOr(const QJsonObject& object, const char* key, const QPointF& fallback) {
    const QJsonArray values = object.value(key).toArray();
    if (values.size() != 2) return fallback;
    return QPointF(values.at(0).toDouble(fallback.x()), values.at(1).toDouble(fallback.y()));
}

QPolygonF tilePolygon(const int x, const int y, const ch::CameraState& camera,
                      const int width, const int height) {
    const auto a = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y), camera, width, height);
    const auto b = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y), camera, width, height);
    const auto c = ch::world_to_screen_point(static_cast<float>(x + 1), static_cast<float>(y + 1), camera, width, height);
    const auto d = ch::world_to_screen_point(static_cast<float>(x), static_cast<float>(y + 1), camera, width, height);
    return QPolygonF{QPointF(a.x, a.y), QPointF(b.x, b.y), QPointF(c.x, c.y), QPointF(d.x, d.y)};
}

void drawGroundTileSprite(QPainter& painter, const QImage& sprite, const QPointF& tile,
                           const ch::CameraState& camera, const int width, const int height) {
    const QPolygonF polygon = tilePolygon(static_cast<int>(tile.x()), static_cast<int>(tile.y()), camera, width, height);
    painter.save();
    QPainterPath clip;
    clip.addPolygon(polygon);
    painter.setClipPath(clip);
    painter.drawImage(polygon.boundingRect(), sprite);
    painter.restore();
}

void drawAnchoredSprite(QPainter& painter, const QImage& sprite, const QPointF& tile,
                        const ch::CameraState& camera, const int width, const int height,
                        const float scale, const QPointF& offsetPixels) {
    const auto anchor = opaqueBottomAnchor(sprite);
    if (!anchor) return;
    const auto ground = ch::world_to_screen_point(static_cast<float>(tile.x()) + 0.5F,
                                                   static_cast<float>(tile.y()) + 0.5F,
                                                   camera, width, height);
    const QSizeF targetSize(sprite.width() * scale, sprite.height() * scale);
    const QPointF targetAnchor(anchor->x() * scale, anchor->y() * scale);
    const QRectF target(QPointF(ground.x - targetAnchor.x() + offsetPixels.x(),
                                ground.y - targetAnchor.y() + offsetPixels.y()), targetSize);
    painter.drawImage(target, sprite);
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 4) {
        std::cerr << "usage: MapForge2MapCapture <output.png> <candidate.png> <capture_request.json>\n";
        return 2;
    }

    const std::filesystem::path outputPath = argv[1];
    const std::filesystem::path candidatePath = argv[2];
    const QString requestPath = QString::fromStdString(argv[3]);

    QFile requestFile(requestPath);
    if (!requestFile.open(QIODevice::ReadOnly)) {
        std::cerr << "unable to open capture request\n";
        return 3;
    }
    QJsonParseError parseError{};
    const QJsonDocument requestDocument = QJsonDocument::fromJson(requestFile.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !requestDocument.isObject()) {
        std::cerr << "invalid capture request JSON\n";
        return 4;
    }
    const QJsonObject root = requestDocument.object();
    if (root.value("contract").toString() != "MAPFORGE_CAPTURE_REQUEST_V1") {
        std::cerr << "unsupported capture request contract\n";
        return 5;
    }

    const QJsonObject capture = root.value("capture").toObject();
    const QJsonObject canvas = capture.value("canvas").toObject();
    const QJsonObject cameraSpec = capture.value("camera").toObject();
    const QJsonObject stage = capture.value("stage").toObject();
    const QJsonObject candidateSpec = capture.value("candidate").toObject();

    const int width = std::clamp(canvas.value("width").toInt(1024), 320, 4096);
    const int height = std::clamp(canvas.value("height").toInt(768), 240, 4096);
    const QImage candidate(QString::fromStdString(candidatePath.string()));
    if (candidate.isNull()) {
        std::cerr << "unable to load candidate PNG: " << candidatePath.string() << "\n";
        return 6;
    }

    QImage frame(width, height, QImage::Format_ARGB32);
    frame.fill(colorOr(canvas, "background", QColor(49, 57, 52)));

    ch::CameraState camera{};
    camera.zoom = static_cast<float>(cameraSpec.value("zoom").toDouble(0.92));
    camera.rotation = ch::CameraRotation::r0;

    const QPointF focusTile = pairOr(cameraSpec, "focusTile", QPointF(0.0, 0.0));
    const QPointF focusScreen = pairOr(cameraSpec, "focusScreen", QPointF(0.5, 0.57));
    const auto focusPoint = ch::world_to_screen_point(static_cast<float>(focusTile.x()) + 0.5F,
                                                       static_cast<float>(focusTile.y()) + 0.5F,
                                                       camera, width, height);
    camera.pan_x += static_cast<float>(width * focusScreen.x() - focusPoint.x);
    camera.pan_y += static_cast<float>(height * focusScreen.y() - focusPoint.y);

    QPainter painter(&frame);
    painter.setRenderHint(QPainter::Antialiasing, false);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);

    const int minTile = std::clamp(stage.value("minTile").toInt(-6), -64, 0);
    const int maxTile = std::clamp(stage.value("maxTile").toInt(6), 0, 64);
    const QColor groundA = colorOr(stage, "groundColor", QColor(112, 137, 99));
    const QColor groundB = colorOr(stage, "alternateGroundColor", QColor(118, 143, 105));
    const QColor gridColor = colorOr(stage, "gridColor", QColor(62, 79, 59, 150));
    const bool drawGrid = stage.value("drawGrid").toBool(true);

    QPen gridPen(gridColor);
    gridPen.setWidthF(1.0);
    for (int depth = minTile * 2; depth <= maxTile * 2; ++depth) {
        const int firstX = std::max(minTile, depth - maxTile);
        const int lastX = std::min(maxTile, depth - minTile);
        for (int x = firstX; x <= lastX; ++x) {
            const int y = depth - x;
            painter.setPen(drawGrid ? gridPen : Qt::NoPen);
            painter.setBrush(((x + y) & 1) == 0 ? groundA : groundB);
            const QPolygonF groundTile = tilePolygon(x, y, camera, width, height);
            painter.drawPolygon(groundTile);
            if (stage.value("drawGrassTexture").toBool(true)) {
                const QColor speckle = colorOr(stage, "grassSpeckleColor", QColor(92, 122, 78, 95));
                painter.setPen(QPen(speckle, 1.0));
                const QRectF bounds = groundTile.boundingRect();
                const unsigned seed = static_cast<unsigned>((x * 92837111) ^ (y * 689287499));
                for (int i = 0; i < 6; ++i) {
                    const unsigned value = seed + static_cast<unsigned>(i * 2654435761u);
                    const double fx = 0.18 + 0.64 * ((value & 0xffffu) / 65535.0);
                    const double fy = 0.18 + 0.64 * (((value >> 16) & 0xffffu) / 65535.0);
                    painter.drawPoint(QPointF(bounds.left() + bounds.width() * fx,
                                              bounds.top() + bounds.height() * fy));
                }
            }
        }
    }

    const QPointF candidateTile = pairOr(candidateSpec, "tile", QPointF(0.0, 0.0));
    const QPointF footprint = pairOr(candidateSpec, "footprint", QPointF(1.0, 1.0));
    const bool showFootprint = candidateSpec.value("showFootprint").toBool(true);
    if (showFootprint) {
        QPen footprintPen(colorOr(candidateSpec, "footprintColor", QColor(246, 196, 72, 210)));
        footprintPen.setWidthF(2.0);
        painter.setPen(footprintPen);
        painter.setBrush(Qt::NoBrush);
        const int fw = std::max(1, static_cast<int>(std::round(footprint.x())));
        const int fd = std::max(1, static_cast<int>(std::round(footprint.y())));
        for (int dx = 0; dx < fw; ++dx) {
            for (int dy = 0; dy < fd; ++dy) {
                painter.drawPolygon(tilePolygon(static_cast<int>(candidateTile.x()) + dx,
                                                static_cast<int>(candidateTile.y()) + dy,
                                                camera, width, height));
            }
        }
    }

    const float scale = static_cast<float>(std::clamp(candidateSpec.value("scale").toDouble(1.0), 0.05, 8.0));
    const QPointF offsetPixels = pairOr(candidateSpec, "offsetPixels", QPointF(0.0, 0.0));
    if (candidateSpec.value("renderAsGroundTile").toBool(false)) {
        drawGroundTileSprite(painter, candidate, candidateTile, camera, width, height);
    } else {
        drawAnchoredSprite(painter, candidate, candidateTile, camera, width, height, scale, offsetPixels);
    }

    if (candidateSpec.value("showAnchor").toBool(true)) {
        const auto ground = ch::world_to_screen_point(static_cast<float>(candidateTile.x()) + 0.5F,
                                                       static_cast<float>(candidateTile.y()) + 0.5F,
                                                       camera, width, height);
        painter.setPen(colorOr(candidateSpec, "anchorColor", QColor(255, 214, 64, 230)));
        painter.drawPoint(QPointF(ground.x, ground.y));
    }
    painter.end();

    if (!outputPath.parent_path().empty()) {
        std::filesystem::create_directories(outputPath.parent_path());
    }
    if (!frame.save(QString::fromStdString(outputPath.string()), "PNG")) {
        std::cerr << "failed to save capture: " << outputPath.string() << "\n";
        return 7;
    }

    std::cout << "mapForgeGenericDeterministicCapture: PASS\n";
    std::cout << "output=" << outputPath.string() << "\n";
    std::cout << "candidate=" << candidatePath.string() << "\n";
    std::cout << "request=" << requestPath.toStdString() << "\n";
    return 0;
}
