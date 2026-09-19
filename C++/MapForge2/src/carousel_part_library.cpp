#include "carousel_part_library.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QImageReader>
#include <QJsonArray>
#include <QPainter>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

constexpr const char* kBaseId = "carousel.base.classic.v1";
constexpr const char* kPlatformId = "carousel.platform.classic.v1";
constexpr const char* kCanopyId = "carousel.canopy.classic.v1";
constexpr const char* kPoleId = "carousel.center_pole.classic.v1";
constexpr const char* kHorseId = "carousel.horse.classic.v1";
constexpr const char* kFinialId = "carousel.ornament.finial.v1";
constexpr const char* kRosetteId = "carousel.ornament.rosette.v1";

QString resolveAsset(const QString& relative_path) {
    if (relative_path.isEmpty()) return {};

    const QFileInfo direct(relative_path);
    if (direct.isAbsolute() && direct.isFile())
        return direct.canonicalFilePath();

    const QString cwd_candidate = QDir::current().filePath(relative_path);
    if (QFileInfo::exists(cwd_candidate))
        return QFileInfo(cwd_candidate).canonicalFilePath();

    QDir probe(QCoreApplication::applicationDirPath());
    for (int depth = 0; depth < 8; ++depth) {
        const QString candidate = probe.filePath(relative_path);
        if (QFileInfo::exists(candidate))
            return QFileInfo(candidate).canonicalFilePath();

        const QString bundled = probe.filePath(
            QStringLiteral("assets/amusement/carousel/classic/") +
            QFileInfo(relative_path).fileName());
        if (QFileInfo::exists(bundled))
            return QFileInfo(bundled).canonicalFilePath();

        if (!probe.cdUp()) break;
    }
    return {};
}

QImage tintPrimary(QImage image, const QColor& primary) {
    image = image.convertToFormat(QImage::Format_ARGB32);
    if (!primary.isValid()) return image;

    for (int y = 0; y < image.height(); ++y) {
        QRgb* row = reinterpret_cast<QRgb*>(image.scanLine(y));
        for (int x = 0; x < image.width(); ++x) {
            QColor source = QColor::fromRgba(row[x]);
            if (source.alpha() <= 2) continue;

            int h = 0;
            int s = 0;
            int v = 0;
            source.getHsv(&h, &s, &v);
            const bool decorative_gold = h >= 25 && h <= 58 && s >= 70;
            const bool neutral = s < 45;
            if (decorative_gold || neutral) continue;

            const float luminance = std::clamp(v / 210.0F, 0.58F, 1.22F);
            QColor mapped(
                std::clamp(static_cast<int>(std::lround(primary.red() * luminance)), 0, 255),
                std::clamp(static_cast<int>(std::lround(primary.green() * luminance)), 0, 255),
                std::clamp(static_cast<int>(std::lround(primary.blue() * luminance)), 0, 255),
                source.alpha());
            row[x] = mapped.rgba();
        }
    }
    return image;
}

QImage fitAsset(const QImage& source, const QSize& target_size) {
    const QImage scaled = source.scaled(
        target_size, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    QImage canvas(target_size, QImage::Format_ARGB32_Premultiplied);
    canvas.fill(Qt::transparent);
    QPainter painter(&canvas);
    painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
    painter.drawImage(
        QPoint((target_size.width() - scaled.width()) / 2,
               (target_size.height() - scaled.height()) / 2),
        scaled);
    painter.end();
    return canvas;
}

} // namespace

QStringList CarouselPartLibrary::partIds() {
    return {
        QString::fromLatin1(kBaseId),
        QString::fromLatin1(kPlatformId),
        QString::fromLatin1(kCanopyId),
        QString::fromLatin1(kPoleId),
        QString::fromLatin1(kHorseId),
        QString::fromLatin1(kFinialId),
        QString::fromLatin1(kRosetteId),
    };
}

bool CarouselPartLibrary::contains(const QString& part_id) {
    return partIds().contains(part_id);
}

QString CarouselPartLibrary::displayName(const QString& part_id) {
    if (part_id == QLatin1String(kBaseId)) return QStringLiteral("Classic carousel base");
    if (part_id == QLatin1String(kPlatformId)) return QStringLiteral("Classic carousel platform");
    if (part_id == QLatin1String(kCanopyId)) return QStringLiteral("Classic isometric canopy");
    if (part_id == QLatin1String(kPoleId)) return QStringLiteral("Classic center pole");
    if (part_id == QLatin1String(kHorseId)) return QStringLiteral("Classic directional carousel horse");
    if (part_id == QLatin1String(kFinialId)) return QStringLiteral("Classic canopy finial");
    if (part_id == QLatin1String(kRosetteId)) return QStringLiteral("Classic decorative rosette");
    return {};
}

QSizeF CarouselPartLibrary::defaultSize(const QString& part_id) {
    if (part_id == QLatin1String(kBaseId)) return QSizeF(320.0, 140.0);
    if (part_id == QLatin1String(kPlatformId)) return QSizeF(300.0, 112.0);
    if (part_id == QLatin1String(kCanopyId)) return QSizeF(320.0, 190.0);
    if (part_id == QLatin1String(kPoleId)) return QSizeF(40.0, 230.0);
    if (part_id == QLatin1String(kHorseId)) return QSizeF(100.0, 100.0);
    if (part_id == QLatin1String(kFinialId)) return QSizeF(52.0, 68.0);
    if (part_id == QLatin1String(kRosetteId)) return QSizeF(48.0, 48.0);
    return QSizeF(24.0, 24.0);
}

QPointF CarouselPartLibrary::defaultPivot(const QString& part_id) {
    if (part_id == QLatin1String(kHorseId)) return QPointF(0.50, 0.82);
    if (part_id == QLatin1String(kCanopyId)) return QPointF(0.50, 0.72);
    if (part_id == QLatin1String(kPoleId)) return QPointF(0.50, 0.50);
    if (part_id == QLatin1String(kFinialId)) return QPointF(0.50, 0.86);
    return QPointF(0.50, 0.50);
}

int CarouselPartLibrary::variantCount(const QString& part_id) {
    return part_id == QLatin1String(kHorseId) ? 4 : 1;
}

QString CarouselPartLibrary::assetPath(const QString& part_id, const int visual_variant) {
    const QString root = QStringLiteral("assets/amusement/carousel/classic/");
    if (part_id == QLatin1String(kBaseId)) return root + QStringLiteral("base.png");
    if (part_id == QLatin1String(kPlatformId)) return root + QStringLiteral("platform.png");
    if (part_id == QLatin1String(kCanopyId)) return root + QStringLiteral("canopy.png");
    if (part_id == QLatin1String(kPoleId)) return root + QStringLiteral("center_pole.png");
    if (part_id == QLatin1String(kFinialId)) return root + QStringLiteral("finial.png");
    if (part_id == QLatin1String(kRosetteId)) return root + QStringLiteral("rosette.png");
    if (part_id == QLatin1String(kHorseId)) {
        switch (((visual_variant % 4) + 4) % 4) {
            case 0: return root + QStringLiteral("horse_e.png");
            case 1: return root + QStringLiteral("horse_s.png");
            case 2: return root + QStringLiteral("horse_w.png");
            case 3: return root + QStringLiteral("horse_n.png");
        }
    }
    return {};
}

bool CarouselPartLibrary::assetBacked(const QString& part_id) {
    return contains(part_id) && !assetPath(part_id, 0).isEmpty();
}

bool CarouselPartLibrary::assetAvailable(const QString& part_id, const int visual_variant) {
    return !resolveAsset(assetPath(part_id, visual_variant)).isEmpty();
}

AnimationNodeSpec CarouselPartLibrary::makeNode(const QString& part_id,
                                                const QString& node_id,
                                                const QString& parent_id,
                                                const QPointF& position_px,
                                                const int draw_order,
                                                const QColor& primary,
                                                const QColor& outline) {
    AnimationNodeSpec node;
    node.id = node_id;
    node.parent_id = parent_id;
    node.position_px = position_px;
    node.draw_order = draw_order;
    node.visual_kind = AnimationNodeVisualKind::LibraryPart;
    node.visual_library_id = part_id;
    node.visual_size_px = defaultSize(part_id);
    node.pivot_normalized = defaultPivot(part_id);
    node.fill_color = primary;
    node.outline_color = outline;
    node.visual_trim_transparent = false;
    node.visual_preserve_aspect = true;
    node.visual_smooth_scaling = true;
    return node;
}

QImage CarouselPartLibrary::renderPart(const QString& part_id,
                                       const QSize& target_size,
                                       const QColor& primary,
                                       const QColor& outline,
                                       QString* reason) {
    return renderPartVariant(part_id, target_size, primary, outline, 0, reason);
}

QImage CarouselPartLibrary::renderPartVariant(const QString& part_id,
                                              const QSize& target_size,
                                              const QColor& primary,
                                              const QColor& outline,
                                              const int visual_variant,
                                              QString* reason) {
    Q_UNUSED(outline);

    if (!contains(part_id)) {
        if (reason) *reason = QStringLiteral("unknown carousel library part: %1").arg(part_id);
        return {};
    }
    if (target_size.width() <= 0 || target_size.height() <= 0) {
        if (reason) *reason = QStringLiteral("carousel part target size must be positive");
        return {};
    }
    if (visual_variant < 0 || visual_variant >= variantCount(part_id)) {
        if (reason) *reason = QStringLiteral("carousel part visual variant is outside the registered range");
        return {};
    }

    const QString authored = assetPath(part_id, visual_variant);
    const QString resolved = resolveAsset(authored);
    if (resolved.isEmpty()) {
        if (reason) *reason = QStringLiteral("carousel art asset not found: %1").arg(authored);
        return {};
    }

    QImageReader reader(resolved);
    reader.setAutoTransform(true);
    QImage source = reader.read();
    if (source.isNull()) {
        if (reason) *reason = QStringLiteral("unable to decode carousel art asset: %1").arg(resolved);
        return {};
    }

    source = tintPrimary(source, primary);
    if (reason) reason->clear();
    return fitAsset(source, target_size);
}

QJsonObject CarouselPartLibrary::manifest() {
    QJsonArray parts;
    for (const QString& id : partIds()) {
        const QSizeF size = defaultSize(id);
        const QPointF pivot = defaultPivot(id);
        QJsonArray variants;
        for (int variant = 0; variant < variantCount(id); ++variant) {
            variants.append(QJsonObject{
                {"variant", variant},
                {"assetPath", assetPath(id, variant)},
            });
        }

        parts.append(QJsonObject{
            {"id", id},
            {"name", displayName(id)},
            {"defaultSizePx", QJsonObject{{"width", size.width()}, {"height", size.height()}}},
            {"defaultPivot", QJsonObject{{"x", pivot.x()}, {"y", pivot.y()}}},
            {"source", QStringLiteral("authored_raster_asset")},
            {"proceduralFallback", false},
            {"transparentRgba", true},
            {"variants", variants},
        });
    }

    return QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"namespace", QStringLiteral("carousel.*")},
        {"style", QStringLiteral("city_horizon_classic_tycoon")},
        {"partCount", parts.size()},
        {"parts", parts},
        {"productionReadySourceType", QStringLiteral("authored_raster_asset")},
        {"proceduralCarouselArtwork", false},
    };
}

} // namespace ch::studio
