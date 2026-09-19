#include "building_export_pipeline.h"

#include "building_block_preview_renderer.h"
#include "building_facade_renderer.h"
#include "building_footprint_model.h"
#include "building_lod_validator.h"
#include "building_procedural_variation.h"
#include "building_roof_editor_renderer.h"
#include "building_urban_integration_validator.h"
#include "src/ch_core/contracts.h"

#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>

#include <algorithm>
#include <array>
#include <cmath>

namespace ch::studio {
namespace {

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South, BuildingView::East, BuildingView::West, BuildingView::North,
};

int roundUp32(const int value) { return ((value + 31) / 32) * 32; }

QRect alphaBounds(const QImage& image, const int alpha_threshold = 2) {
    int min_x = image.width(), min_y = image.height(), max_x = -1, max_y = -1;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            if (qAlpha(image.pixel(x, y)) <= alpha_threshold) continue;
            min_x = std::min(min_x, x); min_y = std::min(min_y, y);
            max_x = std::max(max_x, x); max_y = std::max(max_y, y);
        }
    }
    return max_x >= min_x && max_y >= min_y ? QRect(QPoint(min_x, min_y), QPoint(max_x, max_y)) : QRect();
}

struct HaloScan { int clipped = 0; int contamination = 0; int suspicious = 0; };

HaloScan scanHalo(const QImage& source) {
    const QImage image = source.convertToFormat(QImage::Format_ARGB32);
    HaloScan result;
    constexpr int kBorder = 2;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QRgb pixel = image.pixel(x, y);
            const int alpha = qAlpha(pixel);
            if (alpha > 8 && (x < kBorder || y < kBorder || x >= image.width() - kBorder || y >= image.height() - kBorder))
                ++result.clipped;
            if (alpha == 0 && (qRed(pixel) != 0 || qGreen(pixel) != 0 || qBlue(pixel) != 0)) {
                ++result.contamination; continue;
            }
            if (alpha <= 0 || alpha > 32) continue;
            int neighbour_count = 0, sum_r = 0, sum_g = 0, sum_b = 0;
            for (int oy = -1; oy <= 1; ++oy) {
                for (int ox = -1; ox <= 1; ++ox) {
                    if (ox == 0 && oy == 0) continue;
                    const int nx = x + ox, ny = y + oy;
                    if (nx < 0 || ny < 0 || nx >= image.width() || ny >= image.height()) continue;
                    const QRgb neighbour = image.pixel(nx, ny);
                    if (qAlpha(neighbour) < 96) continue;
                    sum_r += qRed(neighbour); sum_g += qGreen(neighbour); sum_b += qBlue(neighbour); ++neighbour_count;
                }
            }
            if (neighbour_count == 0) continue;
            const int delta = std::max({
                std::abs(qRed(pixel) - sum_r / neighbour_count),
                std::abs(qGreen(pixel) - sum_g / neighbour_count),
                std::abs(qBlue(pixel) - sum_b / neighbour_count),
            });
            const bool extreme_white = qRed(pixel) > 225 && qGreen(pixel) > 225 && qBlue(pixel) > 225;
            const bool extreme_black = qRed(pixel) < 30 && qGreen(pixel) < 30 && qBlue(pixel) < 30;
            if (delta > 92 && (extreme_white || extreme_black)) ++result.suspicious;
        }
    }
    return result;
}

bool hasGroundAnchorContact(const QImage& image) {
    const int anchor_x = image.width() / 2, anchor_y = image.height() - 42;
    for (int y = std::max(0, anchor_y - 8); y <= std::min(image.height() - 1, anchor_y + 8); ++y)
        for (int x = std::max(0, anchor_x - 32); x <= std::min(image.width() - 1, anchor_x + 32); ++x)
            if (qAlpha(image.pixel(x, y)) > 20) return true;
    return false;
}

QJsonObject rectJson(const QRect& rect) {
    return QJsonObject{{"x", rect.x()}, {"y", rect.y()}, {"width", rect.width()}, {"height", rect.height()}};
}

QJsonObject buildManifest(const BuildingComposerSpec& spec, const QSize frame,
                          const BuildingExportValidation& validation) {
    QJsonObject manifest = BuildingComposer::manifest(spec, frame);
    QJsonObject geometry = manifest.value(QStringLiteral("geometry")).toObject();
    geometry.insert(QStringLiteral("roofStyle"), BuildingRoofEditorRenderer::roofProfileName(spec.roof_style));
    geometry.insert(QStringLiteral("floorCount"), std::clamp(spec.floor_count, 1, 8));
    geometry.insert(QStringLiteral("floorHeightPx"), std::clamp(spec.floor_height_px, 36, 132));
    geometry.insert(QStringLiteral("wallHeightPx"), BuildingComposer::effectiveWallHeightPx(spec));
    geometry.insert(QStringLiteral("validatedFootprint"), QJsonObject{
        {"widthTiles", spec.footprint_width_tiles}, {"depthTiles", spec.footprint_depth_tiles},
        {"frameWidth", frame.width()}, {"frameHeight", frame.height()},
        {"groundAnchorX", frame.width() / 2}, {"groundAnchorY", frame.height() - 42},
    });
    geometry.insert(QStringLiteral("flexibleFootprint"), BuildingFootprintModel::manifest(spec));
    manifest.insert(QStringLiteral("geometry"), geometry);
    manifest.insert(QStringLiteral("architecturalModules"), BuildingComposer::architecturalModules(spec));
    manifest.insert(QStringLiteral("facadeEditor"), BuildingFacadeRenderer::manifest(spec));
    manifest.insert(QStringLiteral("roofEditor"), BuildingRoofEditorRenderer::roofEditorManifest(spec));
    manifest.insert(QStringLiteral("proceduralVariation"), BuildingProceduralVariation::manifest(spec));
    manifest.insert(QStringLiteral("smallBlockPreview"), BuildingBlockPreviewRenderer::manifest(401));
    manifest.insert(QStringLiteral("lodVisualGate"), BuildingLodValidator::manifest(spec));
    manifest.insert(QStringLiteral("urbanIntegrationValidation"),
                    BuildingUrbanIntegrationValidator::validate(spec).toJson());
    manifest.insert(QStringLiteral("exportPipeline"), QJsonObject{
        {"version", QStringLiteral("automatic_export_validation_6")},
        {"packageValidated", validation.export_ready},
        {"flexibleFootprintValidated", validation.footprint_valid},
        {"urbanIntegrationValidated", validation.urban_integration_valid},
        {"lodVisualValidated", validation.lod_visual_valid},
        {"proceduralVariationRecorded", true},
        {"smallBlockQaPreviewGenerated", true},
        {"lodQaPreviewGenerated", true},
        {"transparentRgba", true},
        {"environmentContextExportedIntoSprite", false},
        {"validationFile", QStringLiteral("*_validation.json")},
    });
    return manifest;
}

bool writeJson(const QString& path, const QJsonObject& object, QString* error) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (error) *error = QStringLiteral("Could not write %1").arg(path);
        return false;
    }
    file.write(QJsonDocument(object).toJson(QJsonDocument::Indented));
    return true;
}

} // namespace

QString BuildingExportValidation::summary() const {
    if (export_ready)
        return QStringLiteral("PASS — footprint, halo, urban integration and LOD gameplay-scale validation passed");
    return QStringLiteral("FAIL — footprint=%1 halo=%2 urban=%3 lod=%4 clipped=%5 contamination=%6 suspiciousHalo=%7 anchor=%8")
        .arg(footprint_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(halo_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(urban_integration_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(lod_visual_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(clipped_edge_pixels).arg(transparent_rgb_contamination).arg(suspicious_halo_pixels)
        .arg(anchor_contact ? QStringLiteral("ok") : QStringLiteral("missing"));
}

QJsonObject BuildingExportValidation::toJson() const {
    return QJsonObject{
        {"version", QStringLiteral("automatic_export_validation_6")},
        {"exportReady", export_ready},
        {"footprintValid", footprint_valid},
        {"haloValid", halo_valid},
        {"urbanIntegrationValid", urban_integration_valid},
        {"lodVisualValid", lod_visual_valid},
        {"anchorContact", anchor_contact},
        {"clippedEdgePixels", clipped_edge_pixels},
        {"transparentRgbContamination", transparent_rgb_contamination},
        {"suspiciousHaloPixels", suspicious_halo_pixels},
        {"alphaBounds", rectJson(alpha_bounds)},
        {"frame", QJsonObject{{"width", frame.width()}, {"height", frame.height()}}},
        {"details", details},
        {"summary", summary()},
    };
}

QSize BuildingExportPipeline::recommendedFrame(const BuildingComposerSpec& spec) {
    const int width_tiles = std::clamp(spec.footprint_width_tiles, 1, 8);
    const int depth_tiles = std::clamp(spec.footprint_depth_tiles, 1, 8);
    const float overhang = std::clamp(spec.roof_overhang, 0.0F, 0.24F);
    const float projected_ground_width = static_cast<float>(width_tiles + depth_tiles) *
                                         static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float roof_extra_width = overhang * static_cast<float>(ch::contracts::kTileWidth) * 2.0F;
    const int width = std::max(320, roundUp32(static_cast<int>(std::ceil(projected_ground_width + roof_extra_width + 64.0F))));
    const float ground_up_extent = static_cast<float>(width_tiles + depth_tiles) *
                                   static_cast<float>(ch::contracts::kTileHeight) * 0.25F;
    const float pitch_factor = std::clamp(spec.roof_pitch_degrees / 35.0F, 0.55F, 1.72F);
    const float roof_visual_height = static_cast<float>(std::max(8, spec.roof_height_px)) * pitch_factor;
    const int height = std::max(280, roundUp32(static_cast<int>(std::ceil(
        42.0F + ground_up_extent + static_cast<float>(BuildingComposer::effectiveWallHeightPx(spec)) +
        roof_visual_height + 28.0F))));
    return QSize(width, height);
}

QString BuildingExportPipeline::automaticStem(const BuildingComposerSpec& spec) {
    const QString variant_suffix = spec.procedural_variation_applied
        ? QStringLiteral("_v%1").arg(std::max(0, spec.procedural_variation_seed))
        : QString();
    return QStringLiteral("building_%1_%2_%3x%4_%5f_%6_seed%7%8")
        .arg(BuildingComposer::typologyId(spec.building_typology))
        .arg(BuildingFootprintModel::shapeId(spec.footprint_shape))
        .arg(std::max(1, spec.footprint_width_tiles)).arg(std::max(1, spec.footprint_depth_tiles))
        .arg(std::clamp(spec.floor_count, 1, 8))
        .arg(BuildingRoofEditorRenderer::roofProfileName(spec.roof_style)).arg(std::max(0, spec.material_seed))
        .arg(variant_suffix);
}

BuildingExportValidation BuildingExportPipeline::validate(const BuildingComposerSpec& spec, QSize frame) {
    BuildingExportValidation report;
    if (!frame.isValid()) frame = recommendedFrame(spec);
    report.frame = frame;
    QString footprint_reason;
    const bool flexible_footprint_valid = BuildingFootprintModel::isValid(spec, &footprint_reason);
    const bool declared_footprint = flexible_footprint_valid && spec.floor_count >= 1 && spec.floor_count <= 8;
    const QSize minimum_frame = recommendedFrame(spec);
    const bool frame_fits = frame.width() >= minimum_frame.width() && frame.height() >= minimum_frame.height();
    int total_clipped = 0, total_contamination = 0, total_suspicious = 0;
    bool all_anchor_contacts = true;
    QRect aggregate_bounds;
    QJsonArray view_reports;
    for (const BuildingView view : kViews) {
        const QImage image = BuildingFacadeRenderer::renderView(spec, view, frame);
        const HaloScan halo = scanHalo(image);
        const QRect bounds = alphaBounds(image);
        const bool anchor = hasGroundAnchorContact(image);
        total_clipped += halo.clipped; total_contamination += halo.contamination; total_suspicious += halo.suspicious;
        all_anchor_contacts = all_anchor_contacts && anchor;
        aggregate_bounds = aggregate_bounds.isNull() ? bounds : aggregate_bounds.united(bounds);
        view_reports.append(QJsonObject{{"view", BuildingComposer::viewName(view)}, {"alphaBounds", rectJson(bounds)},
            {"clippedEdgePixels", halo.clipped}, {"transparentRgbContamination", halo.contamination},
            {"suspiciousHaloPixels", halo.suspicious}, {"anchorContact", anchor}});
    }

    const BuildingUrbanIntegrationValidation urban = BuildingUrbanIntegrationValidator::validate(spec);
    const BuildingLodValidation lod = BuildingLodValidator::validate(spec);

    report.clipped_edge_pixels = total_clipped;
    report.transparent_rgb_contamination = total_contamination;
    report.suspicious_halo_pixels = total_suspicious;
    report.anchor_contact = all_anchor_contacts;
    report.alpha_bounds = aggregate_bounds;
    report.footprint_valid = declared_footprint && frame_fits && total_clipped == 0 && all_anchor_contacts;
    report.halo_valid = total_contamination == 0 && total_suspicious <= 12;
    report.urban_integration_valid = urban.valid;
    report.lod_visual_valid = lod.valid;
    report.export_ready = report.footprint_valid && report.halo_valid && report.urban_integration_valid && report.lod_visual_valid;
    report.details = QJsonObject{
        {"gridContract", QString::fromLatin1(ch::contracts::kGridContract)},
        {"tileWidth", ch::contracts::kTileWidth},
        {"tileHeight", ch::contracts::kTileHeight},
        {"declaredFootprintValid", declared_footprint},
        {"flexibleFootprint", BuildingFootprintModel::manifest(spec)},
        {"footprintValidationReason", footprint_reason},
        {"proceduralVariation", BuildingProceduralVariation::manifest(spec)},
        {"smallBlockPreview", BuildingBlockPreviewRenderer::manifest(401)},
        {"lodVisualGate", lod.toJson()},
        {"floorCount", std::clamp(spec.floor_count, 1, 8)},
        {"recommendedFrame", QJsonObject{{"width", minimum_frame.width()}, {"height", minimum_frame.height()}}},
        {"frameFitsRecommendedMinimum", frame_fits},
        {"haloPolicy", QStringLiteral("reject hidden RGB contamination and extreme low-alpha white/black fringe")},
        {"urbanIntegration", urban.toJson()},
        {"views", view_reports},
    };
    return report;
}

bool BuildingExportPipeline::exportPackage(const BuildingComposerSpec& spec, const QString& output_directory,
                                           QString* exported_stem, BuildingExportValidation* validation,
                                           QString* error) {
    QDir dir(output_directory);
    if (!dir.exists() && !dir.mkpath(QStringLiteral("."))) {
        if (error) *error = QStringLiteral("Could not create export directory: %1").arg(output_directory);
        return false;
    }
    const QSize frame = recommendedFrame(spec);
    const BuildingExportValidation report = validate(spec, frame);
    const QString stem = automaticStem(spec);
    if (exported_stem) *exported_stem = stem;
    if (validation) *validation = report;

    const QString validation_path = dir.filePath(stem + QStringLiteral("_validation.json"));
    if (!writeJson(validation_path, report.toJson(), error)) return false;

    const QString lod_preview_path = dir.filePath(stem + QStringLiteral("_lod_preview.png"));
    if (!BuildingLodValidator::renderReviewSheet(spec, QSize(960, 420)).save(lod_preview_path, "PNG")) {
        if (error) *error = QStringLiteral("Could not write %1").arg(lod_preview_path); return false;
    }

    if (!report.export_ready) {
        if (error) *error = QStringLiteral("Validation blocked production export: %1").arg(report.summary());
        return false;
    }
    for (const BuildingView view : kViews) {
        const QString path = dir.filePath(stem + QStringLiteral("_") + BuildingComposer::viewName(view).toLower() + QStringLiteral(".png"));
        if (!BuildingFacadeRenderer::renderView(spec, view, frame).save(path, "PNG")) {
            if (error) *error = QStringLiteral("Could not write %1").arg(path); return false;
        }
    }
    const QString sheet_path = dir.filePath(stem + QStringLiteral("_4view.png"));
    if (!BuildingFacadeRenderer::renderSpriteSheet(spec, frame).save(sheet_path, "PNG")) {
        if (error) *error = QStringLiteral("Could not write %1").arg(sheet_path); return false;
    }
    const QString review_path = dir.filePath(stem + QStringLiteral("_review.png"));
    if (!BuildingFacadeRenderer::renderReviewSheet(spec, QSize(frame.width(), frame.height() - 20)).save(review_path, "PNG")) {
        if (error) *error = QStringLiteral("Could not write %1").arg(review_path); return false;
    }
    const QString block_preview_path = dir.filePath(stem + QStringLiteral("_block_preview.png"));
    if (!BuildingBlockPreviewRenderer::render(spec, QSize(960, 560), 401).save(block_preview_path, "PNG")) {
        if (error) *error = QStringLiteral("Could not write %1").arg(block_preview_path); return false;
    }
    const QImage south = BuildingFacadeRenderer::renderView(spec, BuildingView::South, frame);
    const QString thumbnail_path = dir.filePath(stem + QStringLiteral("_thumb.png"));
    if (!south.scaled(QSize(192, 168), Qt::KeepAspectRatio, Qt::SmoothTransformation).save(thumbnail_path, "PNG")) {
        if (error) *error = QStringLiteral("Could not write %1").arg(thumbnail_path); return false;
    }
    QJsonObject manifest = buildManifest(spec, frame, report);
    manifest.insert(QStringLiteral("files"), QJsonObject{
        {"south", stem + QStringLiteral("_south.png")}, {"east", stem + QStringLiteral("_east.png")},
        {"west", stem + QStringLiteral("_west.png")}, {"north", stem + QStringLiteral("_north.png")},
        {"spriteSheet", stem + QStringLiteral("_4view.png")}, {"reviewSheet", stem + QStringLiteral("_review.png")},
        {"blockPreview", stem + QStringLiteral("_block_preview.png")},
        {"lodPreview", stem + QStringLiteral("_lod_preview.png")},
        {"thumbnail", stem + QStringLiteral("_thumb.png")}, {"validation", stem + QStringLiteral("_validation.json")},
    });
    return writeJson(dir.filePath(stem + QStringLiteral("_manifest.json")), manifest, error);
}

} // namespace ch::studio
