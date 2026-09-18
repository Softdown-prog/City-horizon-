#include "building_export_pipeline.h"

#include "building_roof_editor_renderer.h"
#include "src/ch_core/contracts.h"

#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QPainter>

#include <algorithm>
#include <array>
#include <cmath>

namespace ch::studio {
namespace {

constexpr std::array<BuildingView, 4> kViews = {
    BuildingView::South,
    BuildingView::East,
    BuildingView::West,
    BuildingView::North,
};

int roundUp32(const int value) {
    return ((value + 31) / 32) * 32;
}

QRect alphaBounds(const QImage& image, const int alpha_threshold = 2) {
    int min_x = image.width();
    int min_y = image.height();
    int max_x = -1;
    int max_y = -1;
    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            if (qAlpha(image.pixel(x, y)) <= alpha_threshold) continue;
            min_x = std::min(min_x, x);
            min_y = std::min(min_y, y);
            max_x = std::max(max_x, x);
            max_y = std::max(max_y, y);
        }
    }
    return max_x >= min_x && max_y >= min_y
        ? QRect(QPoint(min_x, min_y), QPoint(max_x, max_y))
        : QRect();
}

struct HaloScan {
    int clipped = 0;
    int contamination = 0;
    int suspicious = 0;
};

HaloScan scanHalo(const QImage& source) {
    const QImage image = source.convertToFormat(QImage::Format_ARGB32);
    HaloScan result;
    constexpr int kBorder = 2;

    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QRgb pixel = image.pixel(x, y);
            const int alpha = qAlpha(pixel);

            if (alpha > 8 && (x < kBorder || y < kBorder ||
                              x >= image.width() - kBorder || y >= image.height() - kBorder)) {
                ++result.clipped;
            }

            if (alpha == 0 && (qRed(pixel) != 0 || qGreen(pixel) != 0 || qBlue(pixel) != 0)) {
                ++result.contamination;
                continue;
            }

            if (alpha <= 0 || alpha > 32) continue;

            int neighbour_count = 0;
            int sum_r = 0;
            int sum_g = 0;
            int sum_b = 0;
            for (int oy = -1; oy <= 1; ++oy) {
                for (int ox = -1; ox <= 1; ++ox) {
                    if (ox == 0 && oy == 0) continue;
                    const int nx = x + ox;
                    const int ny = y + oy;
                    if (nx < 0 || ny < 0 || nx >= image.width() || ny >= image.height()) continue;
                    const QRgb neighbour = image.pixel(nx, ny);
                    if (qAlpha(neighbour) < 96) continue;
                    sum_r += qRed(neighbour);
                    sum_g += qGreen(neighbour);
                    sum_b += qBlue(neighbour);
                    ++neighbour_count;
                }
            }
            if (neighbour_count == 0) continue;

            const int avg_r = sum_r / neighbour_count;
            const int avg_g = sum_g / neighbour_count;
            const int avg_b = sum_b / neighbour_count;
            const int delta = std::max({
                std::abs(qRed(pixel) - avg_r),
                std::abs(qGreen(pixel) - avg_g),
                std::abs(qBlue(pixel) - avg_b),
            });
            const bool extreme_white = qRed(pixel) > 225 && qGreen(pixel) > 225 && qBlue(pixel) > 225;
            const bool extreme_black = qRed(pixel) < 30 && qGreen(pixel) < 30 && qBlue(pixel) < 30;
            if (delta > 92 && (extreme_white || extreme_black)) ++result.suspicious;
        }
    }
    return result;
}

bool hasGroundAnchorContact(const QImage& image) {
    const int anchor_x = image.width() / 2;
    const int anchor_y = image.height() - 42;
    const int x0 = std::max(0, anchor_x - 32);
    const int x1 = std::min(image.width() - 1, anchor_x + 32);
    const int y0 = std::max(0, anchor_y - 8);
    const int y1 = std::min(image.height() - 1, anchor_y + 8);
    for (int y = y0; y <= y1; ++y) {
        for (int x = x0; x <= x1; ++x) {
            if (qAlpha(image.pixel(x, y)) > 20) return true;
        }
    }
    return false;
}

QJsonObject rectJson(const QRect& rect) {
    return QJsonObject{
        {"x", rect.x()},
        {"y", rect.y()},
        {"width", rect.width()},
        {"height", rect.height()},
    };
}

QJsonObject buildManifest(const BuildingComposerSpec& spec, const QSize frame,
                          const BuildingExportValidation& validation) {
    QJsonObject manifest = BuildingComposer::manifest(spec, frame);
    QJsonObject geometry = manifest.value(QStringLiteral("geometry")).toObject();
    geometry.insert(QStringLiteral("roofStyle"),
                    BuildingRoofEditorRenderer::roofProfileName(spec.roof_style));
    geometry.insert(QStringLiteral("validatedFootprint"), QJsonObject{
        {"widthTiles", spec.footprint_width_tiles},
        {"depthTiles", spec.footprint_depth_tiles},
        {"frameWidth", frame.width()},
        {"frameHeight", frame.height()},
        {"groundAnchorX", frame.width() / 2},
        {"groundAnchorY", frame.height() - 42},
    });
    manifest.insert(QStringLiteral("geometry"), geometry);
    manifest.insert(QStringLiteral("architecturalModules"), BuildingComposer::architecturalModules(spec));
    manifest.insert(QStringLiteral("roofEditor"), BuildingRoofEditorRenderer::roofEditorManifest(spec));
    manifest.insert(QStringLiteral("exportPipeline"), QJsonObject{
        {"version", QStringLiteral("automatic_export_validation_1")},
        {"packageValidated", validation.export_ready},
        {"transparentRgba", true},
        {"environmentContextExported", false},
        {"validationFile", QStringLiteral("*_validation.json")},
    });
    return manifest;
}

bool writeJson(const QString& path, const QJsonObject& object, QString* error) {
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (error != nullptr) *error = QStringLiteral("Could not write %1").arg(path);
        return false;
    }
    file.write(QJsonDocument(object).toJson(QJsonDocument::Indented));
    return true;
}

} // namespace

QString BuildingExportValidation::summary() const {
    if (export_ready) {
        return QStringLiteral("PASS — footprint, frame, anchor and halo validation passed");
    }
    return QStringLiteral("FAIL — footprint=%1 halo=%2 clipped=%3 contamination=%4 suspiciousHalo=%5 anchor=%6")
        .arg(footprint_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(halo_valid ? QStringLiteral("ok") : QStringLiteral("invalid"))
        .arg(clipped_edge_pixels)
        .arg(transparent_rgb_contamination)
        .arg(suspicious_halo_pixels)
        .arg(anchor_contact ? QStringLiteral("ok") : QStringLiteral("missing"));
}

QJsonObject BuildingExportValidation::toJson() const {
    return QJsonObject{
        {"version", QStringLiteral("automatic_export_validation_1")},
        {"exportReady", export_ready},
        {"footprintValid", footprint_valid},
        {"haloValid", halo_valid},
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
    const float projected_ground_width =
        static_cast<float>(width_tiles + depth_tiles) *
        static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float roof_extra_width = overhang * static_cast<float>(ch::contracts::kTileWidth) * 2.0F;
    const int width = std::max(320, roundUp32(static_cast<int>(std::ceil(projected_ground_width + roof_extra_width + 64.0F))));

    const float ground_up_extent =
        static_cast<float>(width_tiles + depth_tiles) *
        static_cast<float>(ch::contracts::kTileHeight) * 0.25F;
    const float pitch_factor = std::clamp(spec.roof_pitch_degrees / 35.0F, 0.55F, 1.72F);
    const float roof_visual_height =
        static_cast<float>(std::max(8, spec.roof_height_px)) * pitch_factor;
    const int height = std::max(280, roundUp32(static_cast<int>(std::ceil(
        42.0F + ground_up_extent + static_cast<float>(std::max(24, spec.wall_height_px)) +
        roof_visual_height + 28.0F))));
    return QSize(width, height);
}

QString BuildingExportPipeline::automaticStem(const BuildingComposerSpec& spec) {
    return QStringLiteral("building_%1x%2_%3_seed%4")
        .arg(std::max(1, spec.footprint_width_tiles))
        .arg(std::max(1, spec.footprint_depth_tiles))
        .arg(BuildingRoofEditorRenderer::roofProfileName(spec.roof_style))
        .arg(std::max(0, spec.material_seed));
}

BuildingExportValidation BuildingExportPipeline::validate(
    const BuildingComposerSpec& spec, QSize frame) {
    BuildingExportValidation report;
    if (!frame.isValid()) frame = recommendedFrame(spec);
    report.frame = frame;

    const bool declared_footprint = spec.footprint_width_tiles >= 1 && spec.footprint_width_tiles <= 8 &&
                                    spec.footprint_depth_tiles >= 1 && spec.footprint_depth_tiles <= 8;
    const QSize minimum_frame = recommendedFrame(spec);
    const bool frame_fits = frame.width() >= minimum_frame.width() && frame.height() >= minimum_frame.height();

    int total_clipped = 0;
    int total_contamination = 0;
    int total_suspicious = 0;
    bool all_anchor_contacts = true;
    QRect aggregate_bounds;
    QJsonArray view_reports;

    for (const BuildingView view : kViews) {
        const QImage image = BuildingRoofEditorRenderer::renderView(spec, view, frame);
        const HaloScan halo = scanHalo(image);
        const QRect bounds = alphaBounds(image);
        const bool anchor = hasGroundAnchorContact(image);
        total_clipped += halo.clipped;
        total_contamination += halo.contamination;
        total_suspicious += halo.suspicious;
        all_anchor_contacts = all_anchor_contacts && anchor;
        aggregate_bounds = aggregate_bounds.isNull() ? bounds : aggregate_bounds.united(bounds);
        view_reports.append(QJsonObject{
            {"view", BuildingComposer::viewName(view)},
            {"alphaBounds", rectJson(bounds)},
            {"clippedEdgePixels", halo.clipped},
            {"transparentRgbContamination", halo.contamination},
            {"suspiciousHaloPixels", halo.suspicious},
            {"anchorContact", anchor},
        });
    }

    report.clipped_edge_pixels = total_clipped;
    report.transparent_rgb_contamination = total_contamination;
    report.suspicious_halo_pixels = total_suspicious;
    report.anchor_contact = all_anchor_contacts;
    report.alpha_bounds = aggregate_bounds;
    report.footprint_valid = declared_footprint && frame_fits && total_clipped == 0 && all_anchor_contacts;
    report.halo_valid = total_contamination == 0 && total_suspicious <= 12;
    report.export_ready = report.footprint_valid && report.halo_valid;
    report.details = QJsonObject{
        {"gridContract", QString::fromLatin1(ch::contracts::kGridContract)},
        {"tileWidth", ch::contracts::kTileWidth},
        {"tileHeight", ch::contracts::kTileHeight},
        {"declaredFootprintValid", declared_footprint},
        {"recommendedFrame", QJsonObject{{"width", minimum_frame.width()}, {"height", minimum_frame.height()}}},
        {"frameFitsRecommendedMinimum", frame_fits},
        {"haloPolicy", QStringLiteral("reject hidden RGB contamination and extreme low-alpha white/black fringe")},
        {"views", view_reports},
    };
    return report;
}

bool BuildingExportPipeline::exportPackage(
    const BuildingComposerSpec& spec,
    const QString& output_directory,
    QString* exported_stem,
    BuildingExportValidation* validation,
    QString* error) {
    QDir dir(output_directory);
    if (!dir.exists() && !dir.mkpath(QStringLiteral("."))) {
        if (error != nullptr) *error = QStringLiteral("Could not create export directory: %1").arg(output_directory);
        return false;
    }

    const QSize frame = recommendedFrame(spec);
    const BuildingExportValidation report = validate(spec, frame);
    const QString stem = automaticStem(spec);
    if (exported_stem != nullptr) *exported_stem = stem;
    if (validation != nullptr) *validation = report;

    const QString validation_path = dir.filePath(stem + QStringLiteral("_validation.json"));
    if (!writeJson(validation_path, report.toJson(), error)) return false;
    if (!report.export_ready) {
        if (error != nullptr) *error = QStringLiteral("Validation blocked production export: %1").arg(report.summary());
        return false;
    }

    for (const BuildingView view : kViews) {
        const QString view_name = BuildingComposer::viewName(view).toLower();
        const QString path = dir.filePath(stem + QStringLiteral("_") + view_name + QStringLiteral(".png"));
        if (!BuildingRoofEditorRenderer::renderView(spec, view, frame).save(path, "PNG")) {
            if (error != nullptr) *error = QStringLiteral("Could not write %1").arg(path);
            return false;
        }
    }

    const QImage sheet = BuildingRoofEditorRenderer::renderSpriteSheet(spec, frame);
    const QString sheet_path = dir.filePath(stem + QStringLiteral("_4view.png"));
    if (!sheet.save(sheet_path, "PNG")) {
        if (error != nullptr) *error = QStringLiteral("Could not write %1").arg(sheet_path);
        return false;
    }

    const QString review_path = dir.filePath(stem + QStringLiteral("_review.png"));
    if (!BuildingRoofEditorRenderer::renderReviewSheet(spec, QSize(frame.width(), frame.height() - 20)).save(review_path, "PNG")) {
        if (error != nullptr) *error = QStringLiteral("Could not write %1").arg(review_path);
        return false;
    }

    const QImage south = BuildingRoofEditorRenderer::renderView(spec, BuildingView::South, frame);
    const QImage thumbnail = south.scaled(QSize(192, 168), Qt::KeepAspectRatio, Qt::SmoothTransformation);
    const QString thumbnail_path = dir.filePath(stem + QStringLiteral("_thumb.png"));
    if (!thumbnail.save(thumbnail_path, "PNG")) {
        if (error != nullptr) *error = QStringLiteral("Could not write %1").arg(thumbnail_path);
        return false;
    }

    QJsonObject manifest = buildManifest(spec, frame, report);
    manifest.insert(QStringLiteral("files"), QJsonObject{
        {"south", stem + QStringLiteral("_south.png")},
        {"east", stem + QStringLiteral("_east.png")},
        {"west", stem + QStringLiteral("_west.png")},
        {"north", stem + QStringLiteral("_north.png")},
        {"spriteSheet", stem + QStringLiteral("_4view.png")},
        {"reviewSheet", stem + QStringLiteral("_review.png")},
        {"thumbnail", stem + QStringLiteral("_thumb.png")},
        {"validation", stem + QStringLiteral("_validation.json")},
    });
    const QString manifest_path = dir.filePath(stem + QStringLiteral("_manifest.json"));
    if (!writeJson(manifest_path, manifest, error)) return false;

    return true;
}

} // namespace ch::studio
