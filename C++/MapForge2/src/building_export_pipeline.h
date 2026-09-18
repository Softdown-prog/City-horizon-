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
    // Chooses a frame large enough for the declared footprint, wall/roof height
    // and authored roof overhang, rounded to stable 32 px increments.
    static QSize recommendedFrame(const BuildingComposerSpec& spec);

    // Deterministic production stem. Re-exporting the same authored definition
    // replaces the same package instead of generating arbitrary duplicate names.
    static QString automaticStem(const BuildingComposerSpec& spec);

    static BuildingExportValidation validate(
        const BuildingComposerSpec& spec,
        QSize frame = QSize());

    // Writes the complete production package only when validation passes:
    // 4 individual RGBA views, 4-view sheet, review sheet, thumbnail, manifest
    // and validation report. Environment preview pixels are never exported.
    static bool exportPackage(
        const BuildingComposerSpec& spec,
        const QString& output_directory,
        QString* exported_stem = nullptr,
        BuildingExportValidation* validation = nullptr,
        QString* error = nullptr);
};

} // namespace ch::studio
