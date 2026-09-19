#pragma once

#include "animation_core.h"

#include <QColor>
#include <QJsonObject>
#include <QSize>
#include <QString>

namespace ch::studio {

enum class CarouselPaletteProfile {
    ClassicRedCream,
    BlueGold,
    GreenIvory,
};

struct CarouselComposerSpec {
    QString asset_id = QStringLiteral("carousel_classic");
    QString clip_id = QStringLiteral("ride_loop");
    QString clip_name = QStringLiteral("Carousel ride loop");

    QSize frame_size = QSize(420, 420);
    QPointF anchor_normalized = QPointF(0.50, 0.90);

    int horse_count = 8;
    float platform_radius_px = 72.0F;
    float isometric_depth_scale = 0.46F;
    float horse_bob_amplitude_px = 9.0F;
    float duration_seconds = 2.4F;
    int frame_count = 16;
    bool clockwise = true;

    bool canopy_enabled = true;
    bool rosettes_enabled = true;
    bool finial_enabled = true;
    int rosette_count = 6;

    CarouselPaletteProfile palette = CarouselPaletteProfile::ClassicRedCream;
};

struct CarouselPalette {
    QString id;
    QColor base;
    QColor platform;
    QColor canopy;
    QColor pole;
    QColor horse_primary;
    QColor horse_secondary;
    QColor ornament;
    QColor outline;
};

class CarouselComposer final {
public:
    static constexpr const char* kVersion = "carousel_composer_1";

    static QString paletteId(CarouselPaletteProfile palette);
    static CarouselPalette palette(CarouselPaletteProfile profile);

    static bool validate(const CarouselComposerSpec& spec, QString* reason = nullptr);
    static AnimatedAssetSpec compose(const CarouselComposerSpec& spec,
                                     QString* reason = nullptr);

    static QJsonObject manifest(const CarouselComposerSpec& spec);
};

} // namespace ch::studio
