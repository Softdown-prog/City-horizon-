#include "map_capture_service.h"
#include "engine_projection_adapter.h"
#include "src/ch_core/contracts.h"
#include "src/ch_core/projection.h"

#include <QColor>
#include <QFile>
#include <QFont>
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
#include <optional>

namespace ch::studio {
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

ch::CameraRotation cameraRotationOr(const QJsonObject& cameraSpec) {
    int turns = cameraSpec.value("rotationQuarterTurns").toInt(0) % 4;
    if (turns < 0) turns += 4;
    return static_cast<ch::CameraRotation>(turns);
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
                       const float worldZ, const ch::CameraState& camera, const int width, const int height,
                       const float scale, const QPointF& offsetPixels) {
    const auto anchor = opaqueBottomAnchor(sprite);
    if (!anchor) return;
    const QPointF ground = EngineProjectionAdapter::worldToScreen(
        static_cast<float>(tile.x()) + 0.5F,
        static_cast<float>(tile.y()) + 0.5F,
        worldZ,
        camera,
        QSizeF(width, height));
    const QSizeF targetSize(sprite.width() * scale, sprite.height() * scale);
    const QPointF targetAnchor(anchor->x() * scale, anchor->y() * scale);
    const QRectF target(QPointF(ground.x() - targetAnchor.x() + offsetPixels.x(),
                               ground.y() - targetAnchor.y() + offsetPixels.y()), targetSize);
    painter.drawImage(target, sprite);
}

void drawPortalMarker(QPainter& painter, const QJsonObject& portal,
                      const ch::CameraState& camera, const int width, const int height) {
    if (!portal.value("enabled").toBool(false)) return;
    const QPointF tile = pairOr(portal, "tile", QPointF(0.0, 0.0));
    const int tileX = static_cast<int>(tile.x());
    const int tileY = static_cast<int>(tile.y());
    const QColor accent = colorOr(portal, "color", QColor(255, 192, 62, 245));

    const bool drawApproach = portal.value("drawApproach").toBool(true);
    if (drawApproach) {
        const QPolygonF outside = tilePolygon(tileX - 1, tileY, camera, width, height);
        painter.setPen(QPen(QColor(47, 51, 54, 245), 1.0));
        painter.setBrush(QColor(58, 62, 65, 245));
        painter.drawPolygon(outside);

        const QPointF leftMid = (outside.at(0) + outside.at(3)) * 0.5;
        const QPointF rightMid = (outside.at(1) + outside.at(2)) * 0.5;
        painter.setPen(QPen(QColor(224, 190, 70, 220), 1.8));
        painter.drawLine(leftMid, rightMid);
    }

    const QPolygonF polygon = tilePolygon(tileX, tileY, camera, width, height);
    QPen portalPen(accent);
    portalPen.setWidthF(2.2);
    painter.setPen(portalPen);
    painter.setBrush(Qt::NoBrush);
    painter.drawPolyline(polygon);

    const auto center = ch::world_to_screen_point(static_cast<float>(tile.x()) - 0.10F,
                                                   static_cast<float>(tile.y()) + 0.36F,
                                                   camera, width, height);

    const QRectF sign(center.x - 78.0, center.y - 78.0, 156.0, 48.0);
    painter.setPen(QPen(QColor(216, 225, 218, 255), 2.0));
    painter.setBrush(QColor(28, 92, 79, 248));
    painter.drawRoundedRect(sign, 5.0, 5.0);
    painter.setPen(QPen(QColor(112, 120, 110, 255), 3.0));
    painter.drawLine(QPointF(sign.left() + 25.0, sign.bottom()), QPointF(sign.left() + 25.0, sign.bottom() + 24.0));
    painter.drawLine(QPointF(sign.right() - 25.0, sign.bottom()), QPointF(sign.right() - 25.0, sign.bottom() + 24.0));

    QFont font = painter.font();
    font.setBold(true);
    font.setPointSize(10);
    painter.setFont(font);
    painter.setPen(QColor(242, 247, 239, 255));
    const QString signLabel = portal.value("signLabel").toString(QStringLiteral("CITY HORIZON"));
    painter.drawText(sign.adjusted(8.0, 5.0, -8.0, -22.0), Qt::AlignCenter, signLabel);
    font.setBold(false);
    font.setPointSize(8);
    painter.setFont(font);
    const QString signDetail = portal.value("signDetail").toString(QStringLiteral("ENTRADA DA CIDADE"));
    painter.drawText(sign.adjusted(8.0, 23.0, -8.0, -4.0), Qt::AlignCenter, signDetail);

    if (portal.value("showTutorialLabel").toBool(false)) {
        const QString label = portal.value("label").toString(QStringLiteral("CONEXAO RODOVIARIA"));
        font.setBold(true);
        font.setPointSize(10);
        painter.setFont(font);
        painter.setPen(accent);
        painter.drawText(QPointF(center.x + 92.0, center.y - 46.0), label);

        const QString detail = portal.value("detail").toString();
        if (!detail.isEmpty()) {
            font.setBold(false);
            font.setPointSize(8);
            painter.setFont(font);
            painter.setPen(QColor(225, 235, 230, 245));
            painter.drawText(QPointF(center.x + 92.0, center.y - 27.0), detail);
        }
    }
}

MapCaptureResult fail(int code, const QString& message) {
    return MapCaptureResult{false, code, message};
}

} // namespace

MapCaptureResult runMapCapture(const QString& output_path,
                               const QString& candidate_path,
                               const QString& request_path) {
    QFile requestFile(request_path);
    if (!requestFile.open(QIODevice::ReadOnly)) return fail(3, QStringLiteral("unable to open capture request"));

    QJsonParseError parseError{};
    const QJsonDocument requestDocument = QJsonDocument::fromJson(requestFile.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !requestDocument.isObject()) {
        return fail(4, QStringLiteral("invalid capture request JSON"));
    }

    const QJsonObject root = requestDocument.object();
    if (root.value("contract").toString() != QStringLiteral("MAPFORGE_CAPTURE_REQUEST_V1")) {
        return fail(5, QStringLiteral("unsupported capture request contract"));
    }

    const QJsonObject capture = root.value("capture").toObject();
    const QJsonObject canvas = capture.value("canvas").toObject();
    const QJsonObject cameraSpec = capture.value("camera").toObject();
    const QJsonObject stage = capture.value("stage").toObject();
    const QJsonObject candidateSpec = capture.value("candidate").toObject();
    const QJsonObject portalSpec = capture.value("portal").toObject();

    const QString requestedCameraContract = cameraSpec.value("contract").toString();
    if (!requestedCameraContract.isEmpty()
        && requestedCameraContract != QString::fromLatin1(ch::contracts::kCameraContract)) {
        return fail(8, QStringLiteral("capture camera contract mismatch: %1").arg(requestedCameraContract));
    }

    const int width = std::clamp(canvas.value("width").toInt(1024), 320, 4096);
    const int height = std::clamp(canvas.value("height").toInt(768), 240, 4096);
    const QImage candidate(candidate_path);
    if (candidate.isNull()) return fail(6, QStringLiteral("unable to load candidate PNG: %1").arg(candidate_path));

    QImage frame(width, height, QImage::Format_ARGB32);
    frame.fill(colorOr(canvas, "background", QColor(49, 57, 52)));

    ch::CameraState camera{};
    camera.zoom = static_cast<float>(cameraSpec.value("zoom").toDouble(0.92));
    camera.rotation = cameraRotationOr(cameraSpec);

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
    const QJsonArray tileList = candidateSpec.value("tiles").toArray();
    const float candidateElevation = static_cast<float>(candidateSpec.value("elevationWorld").toDouble(0.0));
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
    if (!tileList.isEmpty() && candidateSpec.value("renderAsGroundTile").toBool(false)) {
        for (const QJsonValue& entry : tileList) {
            const QJsonArray coords = entry.toArray();
            if (coords.size() != 2) continue;
            drawGroundTileSprite(painter, candidate,
                                 QPointF(coords.at(0).toDouble(), coords.at(1).toDouble()),
                                 camera, width, height);
        }
    } else if (candidateSpec.value("renderAsGroundTile").toBool(false)) {
        drawGroundTileSprite(painter, candidate, candidateTile, camera, width, height);
    } else {
        drawAnchoredSprite(painter, candidate, candidateTile, candidateElevation,
                           camera, width, height, scale, offsetPixels);
    }

    drawPortalMarker(painter, portalSpec, camera, width, height);

    if (candidateSpec.value("showAnchor").toBool(true)) {
        const QPointF ground = EngineProjectionAdapter::worldToScreen(
            static_cast<float>(candidateTile.x()) + 0.5F,
            static_cast<float>(candidateTile.y()) + 0.5F,
            candidateElevation,
            camera,
            QSizeF(width, height));
        painter.setPen(colorOr(candidateSpec, "anchorColor", QColor(255, 214, 64, 230)));
        painter.drawPoint(ground);
    }
    painter.end();

    const std::filesystem::path outputPath = output_path.toStdString();
    if (!outputPath.parent_path().empty()) std::filesystem::create_directories(outputPath.parent_path());
    if (!frame.save(output_path, "PNG")) return fail(7, QStringLiteral("failed to save capture: %1").arg(output_path));

    return MapCaptureResult{true, 0, QString()};
}

} // namespace ch::studio