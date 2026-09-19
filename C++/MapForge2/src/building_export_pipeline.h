#pragma once

#include "building_composer.h"

#include <QJsonObject>
#include <QRect>
#include <QSize>
#include <QString>

namespace ch::studio {

struct BuildingExportValidation {
    bool footprint_valid = false;
    bool halo_valid = false;
    bool urban_integration_valid = false;
    bool lod_visual_valid = false;
    bool export_ready = false;
    bool anchor_contact = false;
    int clipped_edge_pixels = 0;
    int transparent_rgb_contamination = 0;
    int suspicious_halo_pixels = 0;
    QRect alpha_bounds;
    QSize frame;
    QJsonObject details;

    QString summary() const;
    QJsonObject toJson() const;
};

class BuildingExportPipeline final {
public:
    static QSize recommendedFrame(const BuildingComposerSpec& spec);
    static QString automaticStem(const BuildingComposerSpec& spec);

    static BuildingExportValidation validate(
        const BuildingComposerSpec& spec,
        QSize frame = QSize());

    // Writes production sprites only after footprint/frame/anchor, halo,
    // urban-integration and gameplay-scale LOD readability gates all pass.
    static bool exportPackage(
        const BuildingComposerSpec& spec,
        const QString& output_directory,
        QString* exported_stem = nullptr,
        BuildingExportValidation* validation = nullptr,
        QString* error = nullptr);
};

} // namespace ch::studio
