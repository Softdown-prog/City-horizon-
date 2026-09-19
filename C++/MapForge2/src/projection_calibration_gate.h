#pragma once

#include <QImage>
#include <QJsonObject>
#include <QString>

namespace ch::studio {

struct ProjectionCalibrationResult {
    bool pass = false;
    float max_error_px = 0.0F;
    int compared_points = 0;
    QString reason;
    QImage preview;
    QJsonObject report;
};

class ProjectionCalibrationGate final {
public:
    static constexpr const char* kVersion = "engine_projection_calibration_1";

    static ProjectionCalibrationResult run();
    static bool save(const ProjectionCalibrationResult& result,
                     const QString& output_directory,
                     QString* reason = nullptr);
};

} // namespace ch::studio
