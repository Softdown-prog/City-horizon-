#include "animation_visual_source_renderer.h"

#include "building_facade_renderer.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QImageReader>
#include <QPainter>

#include <algorithm>
#include <array>
#include <cmath>

namespace ch::studio {
namespace {

QSize targetSize(const AnimationNodeSpec& node) {
    return QSize(std::max(1, static_cast<int>(std::lround(node.visual_size_px.width()))),
                 std::max(1, static_cast<int>(std::lround(node.visual_size_px.height()))));
}

QString resolveRasterPath(const AnimatedAssetSpec& asset, const QString& authored_path) {
    if (authored_path.trimmed().isEmpty()) return {};

    const QFileInfo direct(authored_path);
    if (direct.isAbsolute() && direct.isFile()) return direct.canonicalFilePath();

    const QString rooted = QDir(asset.visual_source_root).filePath(authored_path);
    if (QFileInfo::exists(rooted)) return QFileInfo(rooted).canonicalFilePath();

    // Authoring executables are commonly launched from build/Debug or build/Release.
    // Search a bounded set of parents without hard-coding a machine-specific path.
    QDir probe(QCoreApplication::applicationDirPath());
    for (int depth = 0; depth < 7; ++depth) {
        const QString candidate = probe.filePath(authored_path);
        if (QFileInfo::exists(candidate)) return QFileInfo(candidate).canonicalFilePath();
        if (!probe.cdUp()) break;
    }
    return {};
}

QImage cropTransparent(const QImage& source) {
    if (source.isNull()) return {};

    int left = source.width();
    int top = source.height();
    int right = -1;
    int bottom = -1;
    for (int y = 0; y < source.height(); ++y) {
        const QRgb* row = reinterpret_cast<const QRgb*>(source.constScanLine(y));
        for (int x = 0; x < source.width(); ++x) {
            if (qAlpha(row[x]) <= 2) continue;
            left = std::min(left, x);
            top = std::min(top, y);
            right = std::max(right, x);
            bottom = std::max(bottom, y);
        }
    }

    if (right < left || bottom < top) return source;
    return source.copy(QRect(left, top, right - left + 1, bottom - top + 1));
}

QImage fitSource(const QImage& source, const AnimationNodeSpec& node) {
    if (source.isNull()) return {};
    const QSize target = targetSize(node);
    const Qt::TransformationMode mode = node.visual_smooth_scaling
        ? Qt::SmoothTransformation : Qt::FastTransformation;
    const Qt::AspectRatioMode aspect = node.visual_preserve_aspect
        ? Qt::KeepAspectRatio : Qt::IgnoreAspectRatio;
    const QImage scaled = source.scaled(target, aspect, mode);

    QImage canvas(target, QImage::Format_ARGB32_Premultiplied);
    canvas.fill(Qt::transparent);
    QPainter painter(&canvas);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, node.visual_smooth_scaling);
    painter.drawImage(QPoint((target.width() - scaled.width()) / 2,
                             (target.height() - scaled.height()) / 2), scaled);
    painter.end();
    return canvas;
}

QImage primitiveSource(const AnimationNodeSpec& node) {
    const QSize size = targetSize(node);
    QImage image(size, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);
    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(QPen(node.outline_color, 1.2, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
    painter.setBrush(node.fill_color);
    const QRectF bounds(0.6, 0.6, std::max(0.0, size.width() - 1.2),
                        std::max(0.0, size.height() - 1.2));
    if (node.visual_kind == AnimationNodeVisualKind::PrimitiveRectangle) {
        painter.drawRoundedRect(bounds, 2.0, 2.0);
    } else {
        painter.drawEllipse(bounds);
    }
    painter.end();
    return image;
}

QImage rasterSource(const AnimatedAssetSpec& asset, const AnimationNodeSpec& node,
                    QString* reason) {
    const QString resolved = resolveRasterPath(asset, node.visual_asset_path);
    if (resolved.isEmpty()) {
        if (reason) *reason = QStringLiteral("raster source not found: %1").arg(node.visual_asset_path);
        return {};
    }

    QImageReader reader(resolved);
    reader.setAutoTransform(true);
    QImage image = reader.read().convertToFormat(QImage::Format_ARGB32_Premultiplied);
    if (image.isNull()) {
        if (reason) *reason = QStringLiteral("unable to decode raster source: %1").arg(resolved);
        return {};
    }

    if (!node.visual_source_rect_px.isNull() && !node.visual_source_rect_px.isEmpty()) {
        const QRect requested = node.visual_source_rect_px.toAlignedRect();
        const QRect clipped = requested.intersected(image.rect());
        if (clipped.isEmpty()) {
            if (reason) *reason = QStringLiteral("raster source rect is outside image bounds");
            return {};
        }
        image = image.copy(clipped);
    }
    if (node.visual_trim_transparent) image = cropTransparent(image);
    if (reason) reason->clear();
    return fitSource(image, node);
}

QImage buildingSource(const AnimationNodeSpec& node, QString* reason) {
    const QSize target = targetSize(node);
    const QSize render_canvas(std::max(260, target.width() * 3),
                              std::max(260, target.height() * 3));
    QImage image = BuildingFacadeRenderer::renderView(
        node.visual_building, node.visual_building_view, render_canvas);
    if (image.isNull()) {
        if (reason) *reason = QStringLiteral("Building Composer visual source returned an empty image");
        return {};
    }
    if (node.visual_trim_transparent) image = cropTransparent(image);
    if (reason) reason->clear();
    return fitSource(image, node);
}

} // namespace

bool AnimationVisualSourceRenderer::validateSource(const AnimatedAssetSpec& asset,
                                                   const AnimationNodeSpec& node,
                                                   QString* reason) {
    auto fail = [&](const QString& message) {
        if (reason) *reason = message;
        return false;
    };

    if (node.visual_kind == AnimationNodeVisualKind::None) {
        if (reason) reason->clear();
        return true;
    }
    if (node.visual_size_px.width() <= 0.0 || node.visual_size_px.height() <= 0.0)
        return fail(QStringLiteral("visual size must be positive"));

    if (node.visual_kind == AnimationNodeVisualKind::RasterSprite) {
        if (node.visual_asset_path.trimmed().isEmpty())
            return fail(QStringLiteral("raster visual source path is empty"));
        if (resolveRasterPath(asset, node.visual_asset_path).isEmpty())
            return fail(QStringLiteral("raster visual source cannot be resolved: %1").arg(node.visual_asset_path));
        if (!node.visual_source_rect_px.isNull()
            && (node.visual_source_rect_px.x() < 0.0 || node.visual_source_rect_px.y() < 0.0
                || node.visual_source_rect_px.width() <= 0.0
                || node.visual_source_rect_px.height() <= 0.0)) {
            return fail(QStringLiteral("raster source rect must be positive and non-negative"));
        }
    }

    if (reason) reason->clear();
    return true;
}

QImage AnimationVisualSourceRenderer::renderSource(const AnimatedAssetSpec& asset,
                                                   const AnimationNodeSpec& node,
                                                   QString* reason) {
    switch (node.visual_kind) {
        case AnimationNodeVisualKind::None:
            if (reason) reason->clear();
            return {};
        case AnimationNodeVisualKind::PrimitiveRectangle:
        case AnimationNodeVisualKind::PrimitiveEllipse:
            if (reason) reason->clear();
            return primitiveSource(node);
        case AnimationNodeVisualKind::RasterSprite:
            return rasterSource(asset, node, reason);
        case AnimationNodeVisualKind::BuildingRender:
            return buildingSource(node, reason);
    }
    if (reason) *reason = QStringLiteral("unsupported animation visual source kind");
    return {};
}

QJsonObject AnimationVisualSourceRenderer::manifest(const AnimationNodeSpec& node) {
    QJsonObject source{
        {"version", QString::fromLatin1(kVersion)},
        {"kind", AnimationCore::nodeVisualKindId(node.visual_kind)},
        {"widthPx", node.visual_size_px.width()},
        {"heightPx", node.visual_size_px.height()},
        {"trimTransparent", node.visual_trim_transparent},
        {"preserveAspect", node.visual_preserve_aspect},
        {"smoothScaling", node.visual_smooth_scaling},
    };

    if (node.visual_kind == AnimationNodeVisualKind::RasterSprite) {
        source.insert(QStringLiteral("assetPath"), node.visual_asset_path);
        if (!node.visual_source_rect_px.isNull() && !node.visual_source_rect_px.isEmpty()) {
            source.insert(QStringLiteral("sourceRectPx"), QJsonObject{
                {"x", node.visual_source_rect_px.x()},
                {"y", node.visual_source_rect_px.y()},
                {"width", node.visual_source_rect_px.width()},
                {"height", node.visual_source_rect_px.height()},
            });
        }
    } else if (node.visual_kind == AnimationNodeVisualKind::BuildingRender) {
        source.insert(QStringLiteral("view"), BuildingComposer::viewName(node.visual_building_view));
        source.insert(QStringLiteral("visualPreset"), BuildingComposer::visualPresetId(node.visual_building.visual_preset));
        source.insert(QStringLiteral("typology"), BuildingComposer::typologyId(node.visual_building.building_typology));
    } else if (node.visual_kind == AnimationNodeVisualKind::PrimitiveRectangle
               || node.visual_kind == AnimationNodeVisualKind::PrimitiveEllipse) {
        source.insert(QStringLiteral("fill"), node.fill_color.name(QColor::HexArgb));
        source.insert(QStringLiteral("outline"), node.outline_color.name(QColor::HexArgb));
        source.insert(QStringLiteral("qaFallbackOnly"), true);
    }
    return source;
}

} // namespace ch::studio
