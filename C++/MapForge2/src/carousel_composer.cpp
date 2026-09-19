#include "carousel_composer.h"

#include "carousel_part_library.h"
#include "src/ch_core/contracts.h"

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
constexpr float kCanonicalDepthScale =
    static_cast<float>(ch::contracts::kTileHeight) / static_cast<float>(ch::contracts::kTileWidth);

float rotationSign(const CarouselComposerSpec& spec) {
    return spec.clockwise ? 1.0F : -1.0F;
}

QPointF projectCanonicalWorldVector(const float world_x,
                                    const float world_y,
                                    const float horizontal_radius_px) {
    const float half_w = static_cast<float>(ch::contracts::kTileWidth) * 0.5F;
    const float half_h = static_cast<float>(ch::contracts::kTileHeight) * 0.5F;
    const float normalize = horizontal_radius_px / (std::sqrt(2.0F) * half_w);
    return QPointF(
        (world_x - world_y) * half_w * normalize,
        (world_x + world_y) * half_h * normalize);
}

QPointF projectedOrbitOffset(const float angle_radians,
                             const CarouselComposerSpec& spec) {
    return projectCanonicalWorldVector(
        std::cos(angle_radians), std::sin(angle_radians), spec.platform_radius_px);
}

QPointF projectedTangent(const float angle_radians,
                         const CarouselComposerSpec& spec) {
    const float sign = rotationSign(spec);
    return projectCanonicalWorldVector(
        -std::sin(angle_radians) * sign,
        std::cos(angle_radians) * sign,
        spec.platform_radius_px);
}

float bobValue(const float orbit_phase,
               const float normalized_time,
               const CarouselComposerSpec& spec) {
    return std::sin(orbit_phase + normalized_time * 2.0F * kPi)
        * spec.horse_bob_amplitude_px;
}

AnimationTrack projectedOrbitTrack(const QString& target,
                                   const AnimationProperty property,
                                   const CarouselComposerSpec& spec,
                                   const float phase_radians) {
    AnimationTrack track;
    track.target_id = target;
    track.property = property;
    track.interpolation = AnimationInterpolation::Linear;

    const int segments = std::max(32, spec.frame_count * 2);
    const QPointF first = projectedOrbitOffset(phase_radians, spec);
    const float first_value = property == AnimationProperty::OffsetX
        ? static_cast<float>(first.x())
        : static_cast<float>(first.y()) + bobValue(phase_radians, 0.0F, spec);

    track.keyframes.reserve(segments + 1);
    for (int i = 0; i <= segments; ++i) {
        const float normalized = static_cast<float>(i) / static_cast<float>(segments);
        const float angle = phase_radians
            + rotationSign(spec) * normalized * 2.0F * kPi;
        const QPointF projected = projectedOrbitOffset(angle, spec);
        float value = property == AnimationProperty::OffsetX
            ? static_cast<float>(projected.x())
            : static_cast<float>(projected.y()) + bobValue(phase_radians, normalized, spec);
        if (i == segments) value = first_value;
        track.keyframes.push_back({spec.duration_seconds * normalized, value});
    }
    return track;
}

int directionalVariant(const float angle_radians,
                       const CarouselComposerSpec& spec) {
    // Variant selection is based on the projected tangent under CH_GRID_V1,
    // not on an arbitrary screen-space rotation. 0=east, 1=south,
    // 2=west, 3=north.
    const QPointF tangent = projectedTangent(angle_radians, spec);
    const float x = static_cast<float>(tangent.x());
    const float y = static_cast<float>(tangent.y());
    if (std::abs(x) >= std::abs(y)) return x >= 0.0F ? 0 : 2;
    return y >= 0.0F ? 1 : 3;
}

int depthOrder(const float orbit_angle_radians,
               const CarouselComposerSpec& spec) {
    // Under the canonical projection, positive screen Y is the near half of
    // the ground-plane orbit. Back horses render behind the center pole.
    return projectedOrbitOffset(orbit_angle_radians, spec).y() >= 0.0 ? 65 : 20;
}

AnimationTrack discreteOrbitTrack(const QString& target,
                                  const AnimationProperty property,
                                  const CarouselComposerSpec& spec,
                                  const float phase_radians) {
    AnimationTrack track;
    track.target_id = target;
    track.property = property;
    track.interpolation = AnimationInterpolation::Step;

    const int segments = std::max(32, spec.frame_count * 2);
    const float first_value = property == AnimationProperty::DrawOrder
        ? static_cast<float>(depthOrder(phase_radians, spec))
        : static_cast<float>(directionalVariant(phase_radians, spec));

    track.keyframes.reserve(segments + 1);
    for (int i = 0; i <= segments; ++i) {
        const float normalized = static_cast<float>(i) / static_cast<float>(segments);
        const float angle = phase_radians
            + rotationSign(spec) * normalized * 2.0F * kPi;
        float value = property == AnimationProperty::DrawOrder
            ? static_cast<float>(depthOrder(angle, spec))
            : static_cast<float>(directionalVariant(angle, spec));
        if (i == segments) value = first_value;
        track.keyframes.push_back({spec.duration_seconds * normalized, value});
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
    return QSizeF(width, width * kCanonicalDepthScale * 0.62);
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
    auto fail = [&](const QString& message) { if (reason) *reason = message; return false; };

    if (spec.asset_id.trimmed().isEmpty()) return fail(QStringLiteral("carousel asset id is empty"));
    if (spec.clip_id.trimmed().isEmpty()) return fail(QStringLiteral("carousel clip id is empty"));
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
    if (std::abs(spec.isometric_depth_scale - kCanonicalDepthScale) > 0.0001F)
        return fail(QStringLiteral("carousel depth scale is locked to CH_GRID_V1 (0.50)"));
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

    AnimationNodeSpec base = CarouselPartLibrary::makeNode(
        QString::fromLatin1(kBasePart), QStringLiteral("base"), QStringLiteral("root"),
        QPointF(center_x, base_y), 0, colors.base, colors.outline);
    base.visual_size_px = QSizeF(std::min<qreal>(deck_size.width() + 26.0, spec.frame_size.width() - 12.0),
                                deck_size.height() + 12.0);
    asset.nodes.push_back(base);

    AnimationNodeSpec platform = CarouselPartLibrary::makeNode(
        QString::fromLatin1(kPlatformPart), QStringLiteral("platform"), QStringLiteral("root"),
        QPointF(center_x, platform_y), 10, colors.platform, colors.outline);
    platform.visual_size_px = deck_size;
    asset.nodes.push_back(platform);

    for (int i = 0; i < spec.horse_count; ++i) {
        const float phase = (2.0F * kPi * static_cast<float>(i)) / static_cast<float>(spec.horse_count);
        const QString node_id = QStringLiteral("horse_%1").arg(i + 1, 2, 10, QLatin1Char('0'));
        AnimationNodeSpec horse = CarouselPartLibrary::makeNode(
            QString::fromLatin1(kHorsePart), node_id, QStringLiteral("platform"),
            QPointF(0.0, -10.0), 20 + i, horseColor(colors, i), colors.outline);
        horse.visual_variant = spec.directional_horses
            ? directionalVariant(phase, spec) : 0;
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
            QPointF(center_x, canopy_y), 90, colors.canopy, colors.outline);
        const qreal canopy_width = std::min<qreal>(deck_size.width() + 30.0,
                                                  spec.frame_size.width() - 12.0);
        canopy.visual_size_px = QSizeF(canopy_width, canopy_width * 0.47);
        asset.nodes.push_back(canopy);

        if (spec.rosettes_enabled && spec.rosette_count > 0) {
            const qreal span = canopy.visual_size_px.width() * 0.66;
            for (int i = 0; i < spec.rosette_count; ++i) {
                const qreal t = spec.rosette_count == 1 ? 0.5
                    : static_cast<qreal>(i) / static_cast<qreal>(spec.rosette_count - 1);
                const qreal x = (t - 0.5) * span;
                const qreal curve = 30.0 + std::abs(x) * 0.055;
                const QString node_id = QStringLiteral("rosette_%1").arg(i + 1, 2, 10, QLatin1Char('0'));
                asset.nodes.push_back(CarouselPartLibrary::makeNode(
                    QString::fromLatin1(kRosettePart), node_id, QStringLiteral("canopy"),
                    QPointF(x, curve), 91 + i, colors.ornament, colors.outline));
            }
        }

        if (spec.finial_enabled) {
            asset.nodes.push_back(CarouselPartLibrary::makeNode(
                QString::fromLatin1(kFinialPart), QStringLiteral("finial"), QStringLiteral("canopy"),
                QPointF(0.0, -canopy.visual_size_px.height() * 0.66), 116,
                colors.ornament, colors.outline));
        }
    }

    AnimationClip clip;
    clip.id = spec.clip_id;
    clip.name = spec.clip_name;
    clip.duration_seconds = spec.duration_seconds;
    clip.frame_count = spec.frame_count;
    clip.loop = true;

    for (int i = 0; i < spec.horse_count; ++i) {
        const float phase = (2.0F * kPi * static_cast<float>(i)) / static_cast<float>(spec.horse_count);
        const QString node_id = QStringLiteral("horse_%1").arg(i + 1, 2, 10, QLatin1Char('0'));

        clip.tracks.push_back(projectedOrbitTrack(
            node_id, AnimationProperty::OffsetX, spec, phase));
        clip.tracks.push_back(projectedOrbitTrack(
            node_id, AnimationProperty::OffsetY, spec, phase));

        if (spec.directional_horses) {
            clip.tracks.push_back(discreteOrbitTrack(
                node_id, AnimationProperty::VisualVariant, spec, phase));
        }
        if (spec.dynamic_depth_ordering) {
            clip.tracks.push_back(discreteOrbitTrack(
                node_id, AnimationProperty::DrawOrder, spec, phase));
        }
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
        {"dynamicDepthOrdering", spec.dynamic_depth_ordering},
        {"directionalHorses", spec.directional_horses},
        {"horseDirectionalVariants", 4},
        {"backHorseDrawOrder", 20},
        {"centerPoleDrawOrder", 60},
        {"frontHorseDrawOrder", 65},
        {"canopyEnabled", spec.canopy_enabled},
        {"rosettesEnabled", spec.rosettes_enabled},
        {"finialEnabled", spec.finial_enabled},
        {"rosetteCount", spec.rosette_count},
        {"palette", paletteManifest(colors)},
        {"cameraContract", QJsonObject{
            {"gridContract", QString::fromLatin1(ch::contracts::kGridContract)},
            {"tileWidth", ch::contracts::kTileWidth},
            {"tileHeight", ch::contracts::kTileHeight},
            {"diamondRatio", ch::contracts::kDiamondRatio},
            {"worldRotationDegrees", ch::contracts::kHorizontalWorldRotationDeg},
            {"inclinationDegrees", ch::contracts::kIsometricInclinationDeg},
            {"screenSpaceParentRotation", false},
            {"worldOrbitProjectedToScreen", true},
        }},
        {"deterministicHierarchyGeneration", true},
        {"automaticHorsePhaseDistribution", true},
        {"automaticHorseTrackGeneration", true},
        {"automaticProjectedOrbitTracks", true},
        {"automaticDepthTracks", spec.dynamic_depth_ordering},
        {"automaticDirectionalVariantTracks", spec.directional_horses},
        {"automaticCounterRotationTracks", false},
        {"automaticLibraryPartAssembly", true},
    };
}

} // namespace ch::studio