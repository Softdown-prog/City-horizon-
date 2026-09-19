#include "animation_export_pipeline.h"

#include "animation_preview_renderer.h"

#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>

#include <algorithm>

namespace ch::studio {
namespace {

QString safeStem(QString value) {
    value = value.trimmed().toLower();
    for (QChar& ch : value) {
        if (!(ch.isLetterOrNumber() || ch == QLatin1Char('_') || ch == QLatin1Char('-'))) {
            ch = QLatin1Char('_');
        }
    }
    while (value.contains(QStringLiteral("__"))) value.replace(QStringLiteral("__"), QStringLiteral("_"));
    if (value.isEmpty()) value = QStringLiteral("animated_asset");
    return value;
}

const AnimationClip* findClip(const AnimatedAssetSpec& asset, const QString& clip_id) {
    for (const AnimationClip& clip : asset.clips) {
        if (clip.id == clip_id) return &clip;
    }
    return nullptr;
}

QJsonObject frameSampleJson(const AnimationFrameSample& sample) {
    return QJsonObject{
        {"frame", sample.frame_index},
        {"timeSeconds", static_cast<double>(sample.time_seconds)},
        {"normalizedTime", static_cast<double>(sample.normalized_time)},
        {"root", QJsonObject{
            {"offsetXPx", static_cast<double>(sample.root.offset_x_px)},
            {"offsetYPx", static_cast<double>(sample.root.offset_y_px)},
            {"rotationDegrees", static_cast<double>(sample.root.rotation_degrees)},
            {"scale", static_cast<double>(sample.root.scale)},
            {"opacity", static_cast<double>(sample.root.opacity)},
            {"visible", sample.root.visible},
        }},
    };
}

} // namespace

AnimationExportResult AnimationExportPipeline::exportClip(const AnimatedAssetSpec& asset,
                                                          const QString& clip_id,
                                                          const QString& output_directory) {
    AnimationExportResult result;
    result.output_directory = output_directory;

    QString validation_reason;
    if (!AnimationCore::validate(asset, &validation_reason)) {
        result.reason = QStringLiteral("invalid animated asset: %1").arg(validation_reason);
        return result;
    }

    const AnimationClip* clip = findClip(asset, clip_id);
    if (!clip) {
        result.reason = QStringLiteral("animation clip '%1' was not found").arg(clip_id);
        return result;
    }

    QDir directory;
    if (!directory.mkpath(output_directory)) {
        result.reason = QStringLiteral("unable to create animation export directory");
        return result;
    }
    QDir output(output_directory);

    const int columns = std::clamp(static_cast<int>(std::ceil(std::sqrt(static_cast<double>(clip->frame_count)))),
                                   1, std::max(1, clip->frame_count));
    const int rows = (clip->frame_count + columns - 1) / columns;
    const QString stem = safeStem(asset.asset_id) + QStringLiteral("_") + safeStem(clip->id);
    const QString sheet_name = stem + QStringLiteral("_spritesheet.png");
    const QString preview_name = stem + QStringLiteral("_preview.png");
    const QString manifest_name = stem + QStringLiteral("_manifest.json");

    const QString sheet_path = output.filePath(sheet_name);
    const QString preview_path = output.filePath(preview_name);
    const QString manifest_path = output.filePath(manifest_name);

    if (!AnimationPreviewRenderer::renderSpriteSheet(asset, *clip, columns).save(sheet_path, "PNG")) {
        result.reason = QStringLiteral("unable to save animation spritesheet");
        return result;
    }
    result.files.append(sheet_name);

    if (!AnimationPreviewRenderer::renderPreviewSheet(asset, *clip).save(preview_path, "PNG")) {
        result.reason = QStringLiteral("unable to save animation preview sheet");
        return result;
    }
    result.files.append(preview_name);

    QJsonArray frame_samples;
    for (int frame_index = 0; frame_index < clip->frame_count; ++frame_index) {
        frame_samples.append(frameSampleJson(AnimationCore::sampleFrame(*clip, frame_index)));
    }

    QJsonObject manifest = AnimationCore::manifest(asset);
    manifest.insert(QStringLiteral("export"), QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"clipId", clip->id},
        {"spritesheet", QJsonObject{
            {"file", sheet_name},
            {"columns", columns},
            {"rows", rows},
            {"frameWidth", asset.frame_size.width()},
            {"frameHeight", asset.frame_size.height()},
            {"frameOrder", QStringLiteral("row_major")},
        }},
        {"previewFile", preview_name},
        {"manifestFile", manifest_name},
        {"runtimeContract", QStringLiteral("SDL consumes ordered frame cells and clip timing; authoring transforms are already baked into PNG frames")},
    });
    manifest.insert(QStringLiteral("frameSamples"), frame_samples);

    QFile manifest_file(manifest_path);
    if (!manifest_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        result.reason = QStringLiteral("unable to save animation manifest");
        return result;
    }
    manifest_file.write(QJsonDocument(manifest).toJson(QJsonDocument::Indented));
    manifest_file.close();
    result.files.append(manifest_name);

    result.success = true;
    result.reason.clear();
    return result;
}

} // namespace ch::studio
