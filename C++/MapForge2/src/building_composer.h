#pragma once

#include <QColor>
#include <QImage>
#include <QJsonObject>
#include <QSize>
#include <QString>

namespace ch::studio {

enum class BuildingRoofStyle {
    Gable,
    Pyramid,
    Flat,
};

enum class BuildingView {
    South,
    East,
    West,
    North,
};

enum class BuildingDoorPosition {
    Left,
    Center,
    Right,
};

enum class BuildingWindowPattern {
    Single,
    Pair,
    Strip,
};

struct BuildingComposerSpec {
    int footprint_width_tiles = 2;
    int footprint_depth_tiles = 1;
    int wall_height_px = 82;
    int roof_height_px = 34;
    BuildingRoofStyle roof_style = BuildingRoofStyle::Gable;

    QColor wall_color = QColor("#d8c3a5");
    QColor roof_color = QColor("#a94e3f");
    QColor trim_color = QColor("#f2eadf");
    QColor glass_color = QColor("#78b9d1");
    QColor door_color = QColor("#6d4c41");
    QColor accent_color = QColor("#d79b38");

    bool windows = true;
    bool south_door = true;
    bool cast_shadow = true;
    BuildingDoorPosition door_position = BuildingDoorPosition::Center;
    BuildingWindowPattern window_pattern = BuildingWindowPattern::Pair;

    // Named socket modules. These are authored once in logical building space
    // and rotate with the same structural definition as the building.
    bool south_awning = false;
    bool south_sign = false;
    bool roof_chimney = false;
};

class BuildingComposer final {
public:
    static QImage renderView(const BuildingComposerSpec& spec, BuildingView view,
                             QSize canvas = QSize(320, 280));
    static QImage renderSpriteSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(320, 280));
    static QImage renderReviewSheet(const BuildingComposerSpec& spec,
                                    QSize cell = QSize(300, 260));
    static QJsonObject manifest(const BuildingComposerSpec& spec, QSize frame = QSize(320, 280));

    static QString viewName(BuildingView view);
    static QString roofName(BuildingRoofStyle style);
    static QString doorPositionName(BuildingDoorPosition position);
    static QString windowPatternName(BuildingWindowPattern pattern);
};

} // namespace ch::studio
