#pragma once

#include <QColor>
#include <QImage>
#include <QJsonArray>
#include <QJsonObject>
#include <QSize>
#include <QString>

#include <algorithm>

namespace ch::studio {

enum class BuildingRoofStyle {
    Gable,
    Hip,
    Pyramid,
    Flat,
    Shed,
    Mansard,
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

enum class BuildingWallMaterial {
    Solid,
    Plaster,
    Brick,
    Concrete,
    Timber,
    Stone,
    MetalPanel,
    Glass,
};

enum class BuildingRoofMaterial {
    Solid,
    CeramicTile,
    MetalSeam,
    AsphaltShingle,
};

enum class BuildingStreetEdge {
    South,
    East,
    North,
    West,
};

enum class BuildingRoadSocketType {
    LocalStreet,
    Avenue,
    ServiceRoad,
};

// Canonical reusable architectural modules. A module describes the authored
// component recipe; placement remains controlled by sockets/patterns in the
// building spec. New buildings should reference these stable IDs instead of
// duplicating the drawing recipe.
enum class BuildingWindowModule {
    ClassicFramed,
};

enum class BuildingDoorModule {
    ClassicWood,
};

enum class BuildingAwningModule {
    CanvasCanopy,
};

enum class BuildingSignModule {
    FacadePlaque,
};

enum class BuildingChimneyModule {
    MasonryCap,
};

// Global art-direction preset. This is intentionally separate from the
// architectural/detail presets (Residence, Small shop, Utility / depot): those
// can vary modules while this preset keeps the City Horizon visual language.
enum class BuildingVisualPreset {
    CityHorizonClassicTycoon,
};

struct BuildingComposerSpec {
    BuildingVisualPreset visual_preset = BuildingVisualPreset::CityHorizonClassicTycoon;

    int footprint_width_tiles = 2;
    int footprint_depth_tiles = 1;
    int wall_height_px = 82;
    int roof_height_px = 34;
    BuildingRoofStyle roof_style = BuildingRoofStyle::Gable;

    // Roof editor parameters are style-independent where possible. Pitch is a
    // visual multiplier over the authored roof height, while overhang/fascia/
    // ridge controls keep a single parametric roof definition for all 4 views.
    float roof_pitch_degrees = 35.0F;
    float roof_overhang = 0.10F;
    float roof_fascia_thickness_px = 2.8F;
    float roof_ridge_scale = 1.0F;
    bool roof_fascia_enabled = true;
    bool roof_ridge_enabled = true;

    // Street integration is authored in logical building space and rotates with
    // the building. The sidewalk is a placement/context contract, not pixels in
    // the transparent building sprite.
    bool sidewalk_enabled = true;
    float sidewalk_depth_tiles = 0.30F;
    float sidewalk_lateral_margin_tiles = 0.55F;
    bool road_socket_enabled = true;
    BuildingStreetEdge road_socket_edge = BuildingStreetEdge::South;
    BuildingRoadSocketType road_socket_type = BuildingRoadSocketType::LocalStreet;
    float road_socket_position = 0.50F;
    float road_socket_width_tiles = 0.36F;

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

    BuildingWindowModule window_module = BuildingWindowModule::ClassicFramed;
    BuildingDoorModule door_module = BuildingDoorModule::ClassicWood;
    BuildingAwningModule awning_module = BuildingAwningModule::CanvasCanopy;
    BuildingSignModule sign_module = BuildingSignModule::FacadePlaque;
    BuildingChimneyModule chimney_module = BuildingChimneyModule::MasonryCap;

    BuildingWallMaterial wall_material = BuildingWallMaterial::Plaster;
    BuildingRoofMaterial roof_material = BuildingRoofMaterial::CeramicTile;
    float material_strength = 0.45F;
    float material_scale = 1.0F;
    float material_variation = 0.35F;
    float material_contrast = 0.45F;
    int material_seed = 17;

    bool south_awning = false;
    bool south_sign = false;
    bool roof_chimney = false;
};

class BuildingComposer final {
public:
    static BuildingComposerSpec presetSpec(
        BuildingVisualPreset preset = BuildingVisualPreset::CityHorizonClassicTycoon) {
        BuildingComposerSpec spec;
        spec.visual_preset = preset;
        return spec;
    }

    static QString visualPresetId(BuildingVisualPreset preset) {
        switch (preset) {
            case BuildingVisualPreset::CityHorizonClassicTycoon:
                return QStringLiteral("city_horizon_classic_tycoon");
        }
        return QStringLiteral("city_horizon_classic_tycoon");
    }

    static QString visualPresetName(BuildingVisualPreset preset) {
        switch (preset) {
            case BuildingVisualPreset::CityHorizonClassicTycoon:
                return QStringLiteral("City Horizon Classic Tycoon");
        }
        return QStringLiteral("City Horizon Classic Tycoon");
    }

    static QString streetEdgeName(BuildingStreetEdge edge) {
        switch (edge) {
            case BuildingStreetEdge::South: return QStringLiteral("south");
            case BuildingStreetEdge::East: return QStringLiteral("east");
            case BuildingStreetEdge::North: return QStringLiteral("north");
            case BuildingStreetEdge::West: return QStringLiteral("west");
        }
        return QStringLiteral("south");
    }

    static QString roadSocketTypeName(BuildingRoadSocketType type) {
        switch (type) {
            case BuildingRoadSocketType::LocalStreet: return QStringLiteral("local_street");
            case BuildingRoadSocketType::Avenue: return QStringLiteral("avenue");
            case BuildingRoadSocketType::ServiceRoad: return QStringLiteral("service_road");
        }
        return QStringLiteral("local_street");
    }

    static QString roadSocketId(const BuildingComposerSpec& spec) {
        return QStringLiteral("road_access_%1").arg(streetEdgeName(spec.road_socket_edge));
    }

    static QJsonObject streetIntegration(const BuildingComposerSpec& spec) {
        const double sidewalk_depth = static_cast<double>(
            std::clamp(spec.sidewalk_depth_tiles, 0.0F, 1.0F));
        const double sidewalk_margin = static_cast<double>(
            std::clamp(spec.sidewalk_lateral_margin_tiles, 0.0F, 2.0F));
        const double socket_position = static_cast<double>(
            std::clamp(spec.road_socket_position, 0.0F, 1.0F));
        const double socket_width = static_cast<double>(
            std::clamp(spec.road_socket_width_tiles, 0.10F, 2.0F));

        return QJsonObject{
            {"version", QStringLiteral("sidewalk_road_socket_1")},
            {"sidewalk", QJsonObject{
                {"enabled", spec.sidewalk_enabled},
                {"integratedWithLot", true},
                {"touchesFootprint", true},
                {"depthTiles", sidewalk_depth},
                {"lateralMarginTiles", sidewalk_margin},
                {"exportedIntoBuildingSprite", false},
                {"surfaceFamily", QStringLiteral("concrete_01")},
            }},
            {"roadSocket", QJsonObject{
                {"id", roadSocketId(spec)},
                {"enabled", spec.road_socket_enabled},
                {"edge", streetEdgeName(spec.road_socket_edge)},
                {"type", roadSocketTypeName(spec.road_socket_type)},
                {"position", socket_position},
                {"widthTiles", socket_width},
                {"requiresRoadAdjacency", true},
                {"rotatesWithBuilding", true},
            }},
            {"placementRule", QStringLiteral("sidewalk_bridges_building_footprint_to_matching_road_socket")},
        };
    }

    static QString windowModuleId(BuildingWindowModule module) {
        switch (module) {
            case BuildingWindowModule::ClassicFramed:
                return QStringLiteral("window.classic_framed.v1");
        }
        return QStringLiteral("window.classic_framed.v1");
    }

    static QString doorModuleId(BuildingDoorModule module) {
        switch (module) {
            case BuildingDoorModule::ClassicWood:
                return QStringLiteral("door.classic_wood.v1");
        }
        return QStringLiteral("door.classic_wood.v1");
    }

    static QString awningModuleId(BuildingAwningModule module) {
        switch (module) {
            case BuildingAwningModule::CanvasCanopy:
                return QStringLiteral("awning.canvas_canopy.v1");
        }
        return QStringLiteral("awning.canvas_canopy.v1");
    }

    static QString signModuleId(BuildingSignModule module) {
        switch (module) {
            case BuildingSignModule::FacadePlaque:
                return QStringLiteral("sign.facade_plaque.v1");
        }
        return QStringLiteral("sign.facade_plaque.v1");
    }

    static QString chimneyModuleId(BuildingChimneyModule module) {
        switch (module) {
            case BuildingChimneyModule::MasonryCap:
                return QStringLiteral("chimney.masonry_cap.v1");
        }
        return QStringLiteral("chimney.masonry_cap.v1");
    }

    static QJsonObject architecturalModules(const BuildingComposerSpec& spec) {
        QJsonArray active;
        if (spec.windows) active.append(windowModuleId(spec.window_module));
        if (spec.south_door) active.append(doorModuleId(spec.door_module));
        if (spec.south_awning) active.append(awningModuleId(spec.awning_module));
        if (spec.south_sign) active.append(signModuleId(spec.sign_module));
        if (spec.roof_chimney) active.append(chimneyModuleId(spec.chimney_module));

        return QJsonObject{
            {"libraryVersion", QStringLiteral("architectural_modules_1")},
            {"window", windowModuleId(spec.window_module)},
            {"door", doorModuleId(spec.door_module)},
            {"awning", awningModuleId(spec.awning_module)},
            {"sign", signModuleId(spec.sign_module)},
            {"chimney", chimneyModuleId(spec.chimney_module)},
            {"active", active},
            {"streetIntegration", streetIntegration(spec)},
        };
    }

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
    static QString wallMaterialName(BuildingWallMaterial material);
    static QString roofMaterialName(BuildingRoofMaterial material);
};

} // namespace ch::studio
