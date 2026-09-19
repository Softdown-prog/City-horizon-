#include "carousel_composer.h"

#include "carousel_part_library.h"

#include <QJsonArray>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

constexpr float kPi = 3.14159265358979323846F;
constexpr const char* kBasePart = "carousel.base.classic.v1";
constexpr const char* kPlatformPart = "carousel.platform.classic.v1";
constexpr const char* kCanopyPart = "carousel.canopy.classic.v1";
constexpr const char* kPolePart = "carousel.center_pole.classic.v1";
constexpr const char* kHorsePart = "carousel.horse.classic.v1";
constexpr const char* kFinialPart = "carousel.ornament.finial.v1";
constexpr const char* kRosettePart = "carousel.ornament.rosette.v1";

AnimationTrack rotationTrack(const CarouselComposerSpec& spec) {
    AnimationTrack track;
    track.target_id = QStringLiteral("platform");
    track.property = AnimationProperty::RotationDegrees;
    track.interpolation = AnimationInterpolation::Linear;
    const float full_turn = spec.clockwise ? 360.0F : -360.0F;
    track.keyframes = {{0.0F, 0.0F}, {spec.duration_seconds, full_turn}};
    return track;
}

AnimationTrack bobTrack(const QString& target,
                        const CarouselComposerSpec& spec,
                        const float phase_radians) {
    AnimationTrack track;
    track.target_id = target;
    track.property = AnimationProperty::OffsetY;
    track.interpolation = AnimationInterpolation::Linear;

    constexpr int kSegments = 16;
    const float first_value = std::sin(phase_radians) * spec.horse_bob_amplitude_px;
    track.keyframes.reserve(kSegments + 1);
    for (int i = 0; i <= kSegments; ++i) {
        const float normalized = static_cast<float>(i) / static_cast<float>(kSegments);
        const float time = spec.duration_seconds * normalized;
        const float value = i == kSegments
            ? first_value
            : std::sin(phase_radians + normalized * 2.0F * kPi)
                * spec.horse_bob_amplitude_px;
        track.keyframes.push_back({time, value});
    }
    return track;
}

QColor horseColor(const CarouselPalette& colors, const int index) {
    switch (index % 4) {
        case 0: return colors.horse_primary;
        case 1: return colors.horse_secondary;
        case 2: return colors.canopy.lighter(112);
        default: return colors.platform.darker(104);
    }
}

QSizeF platformSize(const CarouselComposerSpec& spec) {
    const qreal width = std::clamp(static_cast<qreal>(spec.platform_radius_px * 2.0F + 80.0F),
                                   150.0, static_cast<qreal>(spec.frame_size.width() - 24));
    return QSizeF(width, width * 0.31);
}

QJsonObject paletteManifest(const CarouselPalette& colors) {
    return QJsonObject{
        {"id", colors.id},
        {"base", colors.base.name(QColor::HexRgb)},
        {"platform", colors.platform.name(QColor::HexRgb)},
        {"canopy", colors.canopy.name(QColor::HexRgb)},
        {"pole", colors.pole.name(QColor::HexRgb)},
        {"horsePrimary", colors.horse_primary.name(QColor::HexRgb)},
        {"horseSecondary", colors.horse_secondary.name(QColor::HexRgb)},
        {"ornament", colors.ornament.name(QColor::HexRgb)},
        {"outline", colors.outline.name(QColor::HexRgb)},
    };
}

} // namespace

QString CarouselComposer::paletteId(const CarouselPaletteProfile palette) {
    switch (palette) {
        case CarouselPaletteProfile::ClassicRedCream: return QStringLiteral("carousel_classic_red_cream");
        case CarouselPaletteProfile::BlueGold: return QStringLiteral("carousel_blue_gold");
        case CarouselPaletteProfile::GreenIvory: return QStringLiteral("carousel_green_ivory");
    }
    return QStringLiteral("carousel_classic_red_cream");
}

CarouselPalette CarouselComposer::palette(const CarouselPaletteProfile profile) {
    CarouselPalette result;
    result.id = paletteId(profile);
    result.outline = QColor("#343638");

    switch (profile) {
        case CarouselPaletteProfile::ClassicRedCream:
            result.base = QColor("#785548");
            result.platform = QColor("#d29a42");
            result.canopy = QColor("#b94f49");
            result.pole = QColor("#e9dfcf");
            result.horse_primary = QColor("#b8524d");
            result.horse_secondary = QColor("#547a9b");
            result.ornament = QColor("#dba848");
            break;
        case CarouselPaletteProfile::BlueGold:
            result.base = QColor("#4f6478");
            result.platform = QColor("#d4a74e");
            result.canopy = QColor("#496f91");
            result.pole = QColor("#eee5d1");
            result.horse_primary = QColor("#507fa4");
            result.horse_secondary = QColor("#c66a55");
            result.ornament = QColor("#e0b55e");
            break;
        case CarouselPaletteProfile::GreenIvory:
            result.base = QColor("#596b5a");
            result.platform = QColor("#b98e4b");
            result.canopy = QColor("#668163");
            result.pole = QColor("#f0eadc");
            result.horse_primary = QColor("#718d68");
            result.horse_secondary = QColor("#b45f55");
            result.ornament = QColor("#d2a552");
            break;
    }
    return result;
}

bool CarouselComposer::validate(const CarouselComposerSpec& spec, QString* reason) {
    auto fail = [&](const QString& message) {
        if (reason) *reason = message;
        return false;
    };

    if (spec.asset_id.trimmed().isEmpty()) return fail(QStringLiteral("carousel asset id is empty"));
    if (spec.clip_id.trimmed().isEmpty()) return fail(QStringLiteral("carousel clip id is empty"));
    if (spec.clip_name.trimmed().isEmpty()) return fail(QStringLiteral("carousel clip name is empty"));
    if (spec.frame_size.width() < 240 || spec.frame_size.height() < 240)
        return fail(QStringLiteral("carousel frame size must be at least 240x240"));
    if (spec.anchor_normalized.x() < 0.0 || spec.anchor_normalized.x() > 1.0
        || spec.anchor_normalized.y() < 0.0 || spec.anchor_normalized.y() > 1.0)
        return fail(QStringLiteral("carousel anchor must be normalized inside 0..1"));
    if (spec.horse_count < 2 || spec.horse_count > 24)
        return fail(QStringLiteral("carousel horse count must be between 2 and 24"));
    if (spec.platform_radius_px < 32.0F || spec.platform_radius_px > 110.0F)
        return fail(QStringLiteral("carousel platform radius must be between 32 and 110 pixels"));
    if (spec.platform_radius_px > static_cast<float>(spec.frame_size.width()) * 0.30F)
        return fail(QStringLiteral("carousel platform radius is too large for the selected frame width"));
    if (spec.isometric_depth_scale < 0.25F || spec.isometric_depth_scale > 0.70F)
        return fail(QStringLiteral("carousel isometric depth scale must be between 0.25 and 0.70"));
    if (spec.horse_bob_amplitude_px < 0.0F || spec.horse_bob_amplitude_px > 24.0F)
        return fail(QStringLiteral("carousel horse bob amplitude must be between 0 and 24 pixels"));
    if (spec.duration_seconds < 0.50F || spec.duration_seconds > 20.0F)
        return fail(QStringLiteral("carousel duration must be between 0.50 and 20 seconds"));
    if (spec.frame_count < 4 || spec.frame_count > 120)
        return fail(QStringLiteral("carousel frame count must be between 4 and 120"));
    if (spec.rosette_count < 0 || spec.rosette_count > 16)
        return fail(QStringLiteral("carousel rosette count must be between 0 and 16"));

    if (reason) reason->clear();
    return true;
}

AnimatedAssetSpec CarouselComposer::compose(const CarouselComposerSpec& spec, QString* reason) {
    AnimatedAssetSpec asset;
    QString validation_reason;
    if (!validate(spec, &validation_reason)) {
        if (reason) *reason = validation_reason;
        return asset;
    }

    const CarouselPalette colors = palette(spec.palette);
    asset.asset_id = spec.asset_id;
    asset.category = QStringLiteral("amusement_ride");
    asset.palette_profile = colors.id;
    asset.frame_size = spec.frame_size;
    asset.anchor_normalized = spec.anchor_normalized;
    asset.view = BuildingView::South;
    asset.render_base_building = false;

    const qreal center_x = spec.frame_size.width() * 0.50;
    const qreal platform_y = spec.frame_size.height() * 0.68;
    const QSizeF deck_size = platformSize(spec);
    const qreal base_y = platform_y + deck_size.height() * 0.58;
    const qreal canopy_y = platform_y - std::max<qreal>(102.0, spec.platform_radius_px * 1.34);
    const qreal pole_y = (platform_y + canopy_y) * 0.50;
    const qreal max_visual_width = std::max<qreal>(64.0, spec.frame_size.width() - 16.0);

    AnimationNodeSpec base = CarouselPartLibrary::makeNode(
        QString::fromLatin1(kBasePart), QStringLiteral("base"), QStringLiteral("root"),
        QPointF(center_x, base_y), 0, colors.base, colors.outline);
    const qreal base_width = std::min(deck_size.width() + 26.0, max_visual_width);
    base.visual_size_px = QSizeF(base_width, std::min(deck_size.height() + 12.0, base_width * 0.34));
    asset.nodes.push_back(base);

    AnimationNodeSpec platform = CarouselPartLibrary::makeNode(
        QString::fromLatin1(kPlatformPart), QStringLiteral("platform"), QStringLiteral("root"),
        QPointF(center_x, platform_y), 10, colors.platform, colors.outline);
    platform.visual_size_px = deck_size;
    asset.nodes.push_back(platform);

    for (int i = 0; i < spec.horse_count; ++i) {
        const float phase = (2.0F * kPi * static_cast<float>(i)) / static_cast<float>(spec.horse_count);
        const qreal x = std::cos(phase) * spec.platform_radius_px;
        const qreal y = std::sin(phase) * spec.platform_radius_px * spec.isometric_depth_scale;
        const QString node_id = QStringLiteral("horse_%1").arg(i + 1, 2, 10, QLatin1Char('0'));
        AnimationNodeSpec horse = CarouselPartLibrary::makeNode(
            QString::fromLatin1(kHorsePart), node_id, QStringLiteral("platform"),
            QPointF(x, y - 10.0), 20 + i, horseColor(colors, i), colors.outline);
        asset.nodes.push_back(horse);
    }

    AnimationNodeSpec pole = CarouselPartLibrary::makeNode(
        QString::fromLatin1(kPolePart), QStringLiteral("center_pole"), QStringLiteral("root"),
        QPointF(center_x, pole_y), 60, colors.pole, colors.outline);
    pole.visual_size_px = QSizeF(24.0, std::max<qreal>(150.0, platform_y - canopy_y + 54.0));
    asset.nodes.push_back(pole);

    if (spec.canopy_enabled) {
        AnimationNodeSpec canopy = CarouselPartLibrary::makeNode(
            QString::fromLatin1(kCanopyPart), QStringLiteral("canopy"), QStringLiteral("root"),
            QPointF(center_x, canopy_y), 70, colors.canopy, colors.outline);
        const qreal canopy_width = std::min(deck_size.width() + 30.0, max_visual_width);
        canopy.visual_size_px = QSizeF(canopy_width, canopy_width * 0.47);
        asset.nodes.push_back(canopy);

        if (spec.rosettes_enabled && spec.rosette_count > 0) {
            const qreal span = canopy.visual_size_px.width() * 0.66;
            for (int i = 0; i < spec.rosette_count; ++i) {
                const qreal t = spec.rosette_count == 1
                    ? 0.5
                    : static_cast<qreal>(i) / static_cast<qreal>(spec.rosette_count - 1);
                const qreal x = (t - 0.5) * span;
                const qreal curve = 30.0 + std::abs(x) * 0.055;
                const QString node_id = QStringLiteral("rosette_%1").arg(i + 1, 2, 10, QLatin1Char('0'));
                asset.nodes.push_back(CarouselPartLibrary::makeNode(
                    QString::fromLatin1(kRosettePart), node_id, QStringLiteral("canopy"),
                    QPointF(x, curve), 71 + i, colors.ornament, colors.outline));
            }
        }

        if (spec.finial_enabled) {
            asset.nodes.push_back(CarouselPartLibrary::makeNode(
                QString::fromLatin1(kFinialPart), QStringLiteral("finial"), QStringLiteral("canopy"),
                QPointF(0.0, -canopy.visual_size_px.height() * 0.66), 96,
                colors.ornament, colors.outline));
        }
    }

    AnimationClip clip;
    clip.id = spec.clip_id;
    clip.name = spec.clip_name;
    clip.duration_seconds = spec.duration_seconds;
    clip.frame_count = spec.frame_count;
    clip.loop = true;
    clip.tracks.push_back(rotationTrack(spec));
    for (int i = 0; i < spec.horse_count; ++i) {
        const float phase = (2.0F * kPi * static_cast<float>(i)) / static_cast<float>(spec.horse_count);
        const QString node_id = QStringLiteral("horse_%1").arg(i + 1, 2, 10, QLatin1Char('0'));
        clip.tracks.push_back(bobTrack(node_id, spec, phase));
    }
    asset.clips = {clip};

    QString animation_reason;
    if (!AnimationCore::validate(asset, &animation_reason)) {
        if (reason) *reason = QStringLiteral("composed carousel failed Animation Core validation: %1").arg(animation_reason);
        return AnimatedAssetSpec{};
    }

    if (reason) reason->clear();
    return asset;
}

QJsonObject CarouselComposer::manifest(const CarouselComposerSpec& spec) {
    QString reason;
    const bool valid = validate(spec, &reason);
    const CarouselPalette colors = palette(spec.palette);

    return QJsonObject{
        {"version", QString::fromLatin1(kVersion)},
        {"partLibraryVersion", QString::fromLatin1(CarouselPartLibrary::kVersion)},
        {"animationCoreVersion", QString::fromLatin1(AnimationCore::kVersion)},
        {"assetId", spec.asset_id},
        {"clipId", spec.clip_id},
        {"valid", valid},
        {"validationReason", reason},
        {"frameSize", QJsonObject{{"width", spec.frame_size.width()}, {"height", spec.frame_size.height()}}},
        {"horseCount", spec.horse_count},
        {"platformRadiusPx", static_cast<double>(spec.platform_radius_px)},
        {"isometricDepthScale", static_cast<double>(spec.isometric_depth_scale)},
        {"horseBobAmplitudePx", static_cast<double>(spec.horse_bob_amplitude_px)},
        {"durationSeconds", static_cast<double>(spec.duration_seconds)},
        {"frameCount", spec.frame_count},
        {"clockwise", spec.clockwise},
        {"canopyEnabled", spec.canopy_enabled},
        {"rosettesEnabled", spec.rosettes_enabled},
        {"finialEnabled", spec.finial_enabled},
        {"rosetteCount", spec.rosette_count},
        {"palette", paletteManifest(colors)},
        {"deterministicHierarchyGeneration", true},
        {"automaticHorsePhaseDistribution", true},
        {"automaticHorseTrackGeneration", true},
        {"automaticLibraryPartAssembly", true},
    };
}

} // namespace ch::studio