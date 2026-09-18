#pragma once

#include <QColor>
#include <QImage>
#include <QJsonArray>
#include <QJsonObject>
#include <QSize>
#include <QString>

#include <algorithm>
#include <vector>

namespace ch::studio {

enum class BuildingRoofStyle { Gable, Hip, Pyramid, Flat, Shed, Mansard };
enum class BuildingView { South, East, West, North };
enum class BuildingDoorPosition { Left, Center, Right };
enum class BuildingWindowPattern { Single, Pair, Strip };
enum class BuildingWallMaterial { Solid, Plaster, Brick, Concrete, Timber, Stone, MetalPanel, Glass };
enum class BuildingRoofMaterial { Solid, CeramicTile, MetalSeam, AsphaltShingle };
enum class BuildingStreetEdge { South, East, North, West };
enum class BuildingRoadSocketType { LocalStreet, Avenue, ServiceRoad };
enum class BuildingFacadeModuleKind { Window, Door, Storefront, Sign, Awning, DoubleDoor, GarageDoor, Balcony, Marquee, Hvac, Planter };
enum class BuildingTypology {
    Custom,
    SmallHouse,
    SuburbanHouse,
    Cafeteria,
    CornerShop,
    Market,
    Warehouse,
    SmallTownHall,
    School,
    LowRiseResidential,
    LowRiseOffice,
};

enum class BuildingWindowModule { ClassicFramed };
enum class BuildingDoorModule { ClassicWood };
enum class BuildingAwningModule { CanvasCanopy };
enum class BuildingSignModule { FacadePlaque };
enum class BuildingChimneyModule { MasonryCap };
enum class BuildingVisualPreset { CityHorizonClassicTycoon };

struct BuildingFacadeModulePlacement {
    BuildingFacadeModuleKind kind = BuildingFacadeModuleKind::Window;
    BuildingStreetEdge edge = BuildingStreetEdge::South;
    int floor_index = 0;
    float position = 0.50F;
    float width = 0.22F;
    bool enabled = true;
};

struct BuildingComposerSpec {
    BuildingVisualPreset visual_preset = BuildingVisualPreset::CityHorizonClassicTycoon;
    BuildingTypology building_typology = BuildingTypology::Custom;

    int footprint_width_tiles = 2;
    int footprint_depth_tiles = 1;
    int wall_height_px = 82; // legacy single-storey height; renderer uses effectiveWallHeightPx().
    int floor_count = 1;
    int floor_height_px = 82;
    bool floor_bands_enabled = true;
    int roof_height_px = 34;
    BuildingRoofStyle roof_style = BuildingRoofStyle::Gable;

    bool facade_editor_enabled = false;
    std::vector<BuildingFacadeModulePlacement> facade_modules;

    float roof_pitch_degrees = 35.0F;
    float roof_overhang = 0.10F;
    float roof_fascia_thickness_px = 2.8F;
    float roof_ridge_scale = 1.0F;
    bool roof_fascia_enabled = true;
    bool roof_ridge_enabled = true;

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
    static BuildingComposerSpec presetSpec(BuildingVisualPreset preset = BuildingVisualPreset::CityHorizonClassicTycoon) {
        BuildingComposerSpec spec;
        spec.visual_preset = preset;
        return spec;
    }

    static int effectiveWallHeightPx(const BuildingComposerSpec& spec) {
        return std::clamp(spec.floor_count, 1, 8) * std::clamp(spec.floor_height_px, 36, 132);
    }

    static QString visualPresetId(BuildingVisualPreset) { return QStringLiteral("city_horizon_classic_tycoon"); }
    static QString visualPresetName(BuildingVisualPreset) { return QStringLiteral("City Horizon Classic Tycoon"); }

    static QString typologyId(BuildingTypology typology) {
        switch (typology) {
            case BuildingTypology::SmallHouse: return QStringLiteral("small_house");
            case BuildingTypology::SuburbanHouse: return QStringLiteral("suburban_house");
            case BuildingTypology::Cafeteria: return QStringLiteral("cafeteria");
            case BuildingTypology::CornerShop: return QStringLiteral("corner_shop");
            case BuildingTypology::Market: return QStringLiteral("market");
            case BuildingTypology::Warehouse: return QStringLiteral("warehouse");
            case BuildingTypology::SmallTownHall: return QStringLiteral("small_town_hall");
            case BuildingTypology::School: return QStringLiteral("school");
            case BuildingTypology::LowRiseResidential: return QStringLiteral("low_rise_residential");
            case BuildingTypology::LowRiseOffice: return QStringLiteral("low_rise_office");
            case BuildingTypology::Custom: return QStringLiteral("custom");
        }
        return QStringLiteral("custom");
    }

    static QString typologyName(BuildingTypology typology) {
        switch (typology) {
            case BuildingTypology::SmallHouse: return QStringLiteral("Small house");
            case BuildingTypology::SuburbanHouse: return QStringLiteral("Suburban house");
            case BuildingTypology::Cafeteria: return QStringLiteral("Cafeteria");
            case BuildingTypology::CornerShop: return QStringLiteral("Corner shop");
            case BuildingTypology::Market: return QStringLiteral("Market");
            case BuildingTypology::Warehouse: return QStringLiteral("Warehouse");
            case BuildingTypology::SmallTownHall: return QStringLiteral("Small town hall");
            case BuildingTypology::School: return QStringLiteral("School");
            case BuildingTypology::LowRiseResidential: return QStringLiteral("Low-rise residential");
            case BuildingTypology::LowRiseOffice: return QStringLiteral("Low-rise office");
            case BuildingTypology::Custom: return QStringLiteral("Custom");
        }
        return QStringLiteral("Custom");
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

    static QString facadeModuleKindName(BuildingFacadeModuleKind kind) {
        switch (kind) {
            case BuildingFacadeModuleKind::Window: return QStringLiteral("window");
            case BuildingFacadeModuleKind::Door: return QStringLiteral("door");
            case BuildingFacadeModuleKind::Storefront: return QStringLiteral("storefront");
            case BuildingFacadeModuleKind::Sign: return QStringLiteral("sign");
            case BuildingFacadeModuleKind::Awning: return QStringLiteral("awning");
            case BuildingFacadeModuleKind::DoubleDoor: return QStringLiteral("double_door");
            case BuildingFacadeModuleKind::GarageDoor: return QStringLiteral("garage_door");
            case BuildingFacadeModuleKind::Balcony: return QStringLiteral("balcony");
            case BuildingFacadeModuleKind::Marquee: return QStringLiteral("marquee");
            case BuildingFacadeModuleKind::Hvac: return QStringLiteral("hvac");
            case BuildingFacadeModuleKind::Planter: return QStringLiteral("planter");
        }
        return QStringLiteral("window");
    }

    static QString facadeModuleStableId(BuildingFacadeModuleKind kind) {
        switch (kind) {
            case BuildingFacadeModuleKind::Window: return QStringLiteral("window.classic_framed.v1");
            case BuildingFacadeModuleKind::Door: return QStringLiteral("door.classic_wood.v1");
            case BuildingFacadeModuleKind::Storefront: return QStringLiteral("storefront.classic_glass.v1");
            case BuildingFacadeModuleKind::Sign: return QStringLiteral("sign.facade_plaque.v1");
            case BuildingFacadeModuleKind::Awning: return QStringLiteral("awning.canvas_canopy.v1");
            case BuildingFacadeModuleKind::DoubleDoor: return QStringLiteral("door.double_glass.v1");
            case BuildingFacadeModuleKind::GarageDoor: return QStringLiteral("garage.rollup_panel.v1");
            case BuildingFacadeModuleKind::Balcony: return QStringLiteral("balcony.classic_rail.v1");
            case BuildingFacadeModuleKind::Marquee: return QStringLiteral("marquee.flat_canopy.v1");
            case BuildingFacadeModuleKind::Hvac: return QStringLiteral("hvac.wall_unit.v1");
            case BuildingFacadeModuleKind::Planter: return QStringLiteral("planter.facade_box.v1");
        }
        return QStringLiteral("window.classic_framed.v1");
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
        return QJsonObject{
            {"version", QStringLiteral("sidewalk_road_socket_1")},
            {"sidewalk", QJsonObject{
                {"enabled", spec.sidewalk_enabled}, {"integratedWithLot", true}, {"touchesFootprint", true},
                {"depthTiles", static_cast<double>(std::clamp(spec.sidewalk_depth_tiles, 0.0F, 1.0F))},
                {"lateralMarginTiles", static_cast<double>(std::clamp(spec.sidewalk_lateral_margin_tiles, 0.0F, 2.0F))},
                {"exportedIntoBuildingSprite", false}, {"surfaceFamily", QStringLiteral("concrete_01")},
            }},
            {"roadSocket", QJsonObject{
                {"id", roadSocketId(spec)}, {"enabled", spec.road_socket_enabled},
                {"edge", streetEdgeName(spec.road_socket_edge)}, {"type", roadSocketTypeName(spec.road_socket_type)},
                {"position", static_cast<double>(std::clamp(spec.road_socket_position, 0.0F, 1.0F))},
                {"widthTiles", static_cast<double>(std::clamp(spec.road_socket_width_tiles, 0.10F, 2.0F))},
                {"requiresRoadAdjacency", true}, {"rotatesWithBuilding", true},
            }},
            {"placementRule", QStringLiteral("sidewalk_bridges_building_footprint_to_matching_road_socket")},
        };
    }

    static QString windowModuleId(BuildingWindowModule) { return QStringLiteral("window.classic_framed.v1"); }
    static QString doorModuleId(BuildingDoorModule) { return QStringLiteral("door.classic_wood.v1"); }
    static QString awningModuleId(BuildingAwningModule) { return QStringLiteral("awning.canvas_canopy.v1"); }
    static QString signModuleId(BuildingSignModule) { return QStringLiteral("sign.facade_plaque.v1"); }
    static QString chimneyModuleId(BuildingChimneyModule) { return QStringLiteral("chimney.masonry_cap.v1"); }

    static QJsonObject facadeEditorManifest(const BuildingComposerSpec& spec) {
        QJsonArray placements;
        for (const auto& module : spec.facade_modules) {
            placements.append(QJsonObject{
                {"kind", facadeModuleKindName(module.kind)},
                {"moduleId", facadeModuleStableId(module.kind)},
                {"edge", streetEdgeName(module.edge)},
                {"floor", std::clamp(module.floor_index, 0, std::max(0, spec.floor_count - 1))},
                {"position", static_cast<double>(std::clamp(module.position, 0.0F, 1.0F))},
                {"width", static_cast<double>(std::clamp(module.width, 0.06F, 0.90F))},
                {"enabled", module.enabled},
            });
        }
        return QJsonObject{
            {"version", QStringLiteral("facade_editor_2")},
            {"typologyPreset", QJsonObject{
                {"id", typologyId(spec.building_typology)},
                {"name", typologyName(spec.building_typology)},
                {"editableAfterApply", true},
            }},
            {"enabled", spec.facade_editor_enabled},
            {"floorSystem", QJsonObject{
                {"version", QStringLiteral("floor_system_1")},
                {"count", std::clamp(spec.floor_count, 1, 8)},
                {"floorHeightPx", std::clamp(spec.floor_height_px, 36, 132)},
                {"totalWallHeightPx", effectiveWallHeightPx(spec)},
                {"floorBands", spec.floor_bands_enabled},
            }},
            {"placements", placements},
            {"placementCount", static_cast<int>(placements.size())},
        };
    }

    static QJsonObject architecturalModules(const BuildingComposerSpec& spec) {
        QJsonArray active;
        if (spec.windows) active.append(windowModuleId(spec.window_module));
        if (spec.south_door) active.append(doorModuleId(spec.door_module));
        if (spec.south_awning) active.append(awningModuleId(spec.awning_module));
        if (spec.south_sign) active.append(signModuleId(spec.sign_module));
        if (spec.roof_chimney) active.append(chimneyModuleId(spec.chimney_module));
        return QJsonObject{
            {"libraryVersion", QStringLiteral("architectural_modules_2")},
            {"window", windowModuleId(spec.window_module)}, {"door", doorModuleId(spec.door_module)},
            {"awning", awningModuleId(spec.awning_module)}, {"sign", signModuleId(spec.sign_module)},
            {"chimney", chimneyModuleId(spec.chimney_module)}, {"active", active},
            {"streetIntegration", streetIntegration(spec)}, {"facadeEditor", facadeEditorManifest(spec)},
        };
    }

    static QImage renderView(const BuildingComposerSpec& spec, BuildingView view, QSize canvas = QSize(320, 280));
    static QImage renderSpriteSheet(const BuildingComposerSpec& spec, QSize cell = QSize(320, 280));
    static QImage renderReviewSheet(const BuildingComposerSpec& spec, QSize cell = QSize(300, 260));
    static QJsonObject manifest(const BuildingComposerSpec& spec, QSize frame = QSize(320, 280));

    static QString viewName(BuildingView view);
    static QString roofName(BuildingRoofStyle style);
    static QString doorPositionName(BuildingDoorPosition position);
    static QString windowPatternName(BuildingWindowPattern pattern);
    static QString wallMaterialName(BuildingWallMaterial material);
    static QString roofMaterialName(BuildingRoofMaterial material);
};

} // namespace ch::studio
