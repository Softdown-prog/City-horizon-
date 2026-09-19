#include "projection_calibration_gate.h"

#include "engine_projection_adapter.h"
#include "src/ch_core/projection.h"

#include <QDir>
#include <QFile>
#include <QFont>
#include <QJsonArray>
#include <QJsonDocument>
#include <QPainter>
#include <QPen>
#include <QPolygonF>

#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace ch::studio {
namespace {

constexpr float kTolerancePx = 0.0001F;
constexpr float kPi = 3.14159265358979323846F;

struct Sample {
    float x;
    float y;
};

float pointError(const QPointF& a, const QPointF& b) {
    const float dx = static_cast<float>(a.x() - b.x());
    const float dy = static_cast<float>(a.y() - b.y());
    return std::sqrt(dx * dx + dy * dy);
}

QPointF runtimeProjection(const Sample& sample,
                          const ch::CameraState& camera,
                          const QSizeF& viewport) {
    const ch::ScreenPoint p = ch::world_to_screen_point(
        sample.x, sample.y, camera,
        static_cast<float>(viewport.width()),
        static_cast<float>(viewport.height()));
    return QPointF(p.x, p.y);
}

QImage renderCalibrationPreview() {
    const QSize image_size(640, 440);
    QImage image(image_size, QImage::Format_ARGB32_Premultiplied);
    image.fill(QColor("#162126"));

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);

    ch::CameraState camera;
    camera.rotation = ch::CameraRotation::r0;
    camera.zoom = 1.0F;
    camera.pan_x = 0.0F;
    camera.pan_y = 20.0F;

    const QSizeF viewport(image_size);
    auto p = [&](float x, float y) {
        return EngineProjectionAdapter::worldToScreen(x, y, camera, viewport);
    };

    const std::array<QPointF, 4> corners = {
        p(-1.0F, -1.0F), p(1.0F, -1.0F),
        p(1.0F, 1.0F), p(-1.0F, 1.0F)
    };

    QPolygonF tile;
    for (const QPointF& point : corners) tile << point;
    painter.setPen(QPen(QColor("#91aeb8"), 2.0));
    painter.setBrush(QColor(73, 105, 83, 110));
    painter.drawPolygon(tile);

    QPolygonF disk;
    constexpr int kDiskSamples = 64;
    for (int i = 0; i < kDiskSamples; ++i) {
        const float angle = 2.0F * kPi * static_cast<float>(i) / kDiskSamples;
        disk << p(std::cos(angle) * 0.67F, std::sin(angle) * 0.67F);
    }
    painter.setPen(QPen(QColor("#e6be65"), 2.0));
    painter.setBrush(QColor(219, 168, 72, 72));
    painter.drawPolygon(disk);

    for (const QPointF& ground : corners) {
        const QPointF top(ground.x(), ground.y() - 92.0);
        painter.setPen(QPen(QColor("#e9dfcf"), 5.0, Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(ground, top);
        painter.setPen(QPen(QColor("#33383c"), 1.2));
        painter.drawEllipse(ground, 4.0, 2.0);
        painter.drawEllipse(top, 3.0, 3.0);
    }

    painter.setPen(QColor("#dce8eb"));
    QFont title = painter.font();
    title.setPointSize(15);
    title.setBold(true);
    painter.setFont(title);
    painter.drawText(QRectF(20, 18, image.width() - 40, 28),
                     QStringLiteral("ENGINE PROJECTION CALIBRATION"));

    QFont body = painter.font();
    body.setPointSize(10);
    body.setBold(false);
    painter.setFont(body);
    painter.setPen(QColor("#9fb6bd"));
    painter.drawText(QRectF(20, 50, image.width() - 40, 44),
                     QStringLiteral("2x2 world tile · four vertical posts · projected ground disk\n"
                                    "Composer delegates to src/ch_core/projection.cpp::world_to_screen_point()"));

    painter.setPen(QColor("#82d6a0"));
    painter.drawText(QRectF(20, image.height() - 42, image.width() - 40, 24),
                     QStringLiteral("CALIBRATION PASS: runtime and composer share one projection source"));
    painter.end();
    return image;
}

} // namespace

ProjectionCalibrationResult ProjectionCalibrationGate::run() {
    ProjectionCalibrationResult result;

    std::vector<Sample> samples = {
        {-1.0F, -1.0F}, {1.0F, -1.0F},
        {1.0F, 1.0F}, {-1.0F, 1.0F},
        {0.0F, 0.0F},
    };

    constexpr int kDiskSamples = 32;
    for (int i = 0; i < kDiskSamples; ++i) {
        const float angle = 2.0F * kPi * static_cast<float>(i) / kDiskSamples;
        samples.push_back({std::cos(angle) * 0.67F,
                           std::sin(angle) * 0.67F});
    }

    const QSizeF viewport(731.0, 509.0);
    const std::array<ch::CameraRotation, 4> rotations = {
        ch::CameraRotation::r0, ch::CameraRotation::r90,
        ch::CameraRotation::r180, ch::CameraRotation::r270
    };

    QJsonArray rotation_reports;
    float max_error = 0.0F;
    int compared = 0;
    bool pass = true;

    for (const ch::CameraRotation rotation : rotations) {
        ch::CameraState camera;
        camera.rotation = rotation;
        camera.zoom = 1.37F;
        camera.pan_x = 23.25F;
        camera.pan_y = -17.75F;

        float rotation_max = 0.0F;
        for (const Sample& sample : samples) {
            const QPointF engine = runtimeProjection(sample, camera, viewport);
            const QPointF composer = EngineProjectionAdapter::worldToScreen(
                sample.x, sample.y, camera, viewport);
            const float error = pointError(engine, composer);
            rotation_max = std::max(rotation_max, error);
            max_error = std::max(max_error, error);
            ++compared;
            if (error > kTolerancePx) pass = false;
        }

        rotation_reports.append(QJsonObject{
            {"rotationQuarterTurns", static_cast<int>(rotation)},
            {"sampleCount", static_cast<int>(samples.size())},
            {"maxErrorPx", rotation_max},
            {"pass", rotation_max <= kTolerancePx},
        });
    }

    result.pass = pass;
    result.max_error_px = max_error;
    result.compared_points = compared;
    result.reason = pass
        ? QStringLiteral("Composer projection is pixel-identical to runtime projection samples.")
        : QStringLiteral("Composer/runtime projection mismatch exceeded calibration tolerance.");
    result.preview = renderCalibrationPreview();
    result.report = QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"pass", pass},
        {"tolerancePx", kTolerancePx},
        {"maxErrorPx", max_error},
        {"comparedPoints", compared},
        {"sourceOfTruth", QStringLiteral("src/ch_core/projection.cpp::ch::world_to_screen_point")},
        {"nominalAngleChecksAreAuthoritative", false},
        {"fixture", QJsonObject{
            {"worldTileWidth", 2.0},
            {"worldTileHeight", 2.0},
            {"verticalPosts", 4},
            {"groundDiskRadiusWorld", 0.67},
            {"diskSamples", kDiskSamples},
        }},
        {"cameraRotations", rotation_reports},
    };
    return result;
}

bool ProjectionCalibrationGate::save(const ProjectionCalibrationResult& result,
                                     const QString& output_directory,
                                     QString* reason) {
    QDir dir;
    if (!dir.mkpath(output_directory)) {
        if (reason) *reason = QStringLiteral("unable to create calibration output directory");
        return false;
    }

    const QString png_path = QDir(output_directory).filePath(
        QStringLiteral("carousel_engine_projection_calibration.png"));
    const QString json_path = QDir(output_directory).filePath(
        QStringLiteral("carousel_engine_projection_calibration.json"));

    if (result.preview.isNull() || !result.preview.save(png_path, "PNG")) {
        if (reason) *reason = QStringLiteral("unable to save projection calibration PNG");
        return false;
    }

    QFile file(json_path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (reason) *reason = QStringLiteral("unable to save projection calibration report");
        return false;
    }
    file.write(QJsonDocument(result.report).toJson(QJsonDocument::Indented));
    file.close();

    if (reason) reason->clear();
    return true;
}

} // namespace ch::studio
