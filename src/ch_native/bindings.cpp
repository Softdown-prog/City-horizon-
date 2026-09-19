#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"
#include "src/ch_core/semantic_contracts.h"
#include "src/ch_core/semantic_grid.h"
#include "src/ch_core/placement_contracts.h"
#include "src/ch_core/placement_engine.h"
#include "src/ch_core/transaction_contracts.h"
#include "src/ch_core/transaction_manager.h"
#include "src/ch_core/shoreline_contracts.h"
#include "src/ch_core/shoreline_autotile.h"
#include "src/ch_core/terrain_semantics_catalog.h"
#include "src/ch_render/map_renderer.h"

namespace py = pybind11;

PYBIND11_MODULE(city_horizon_native, m) {
    m.doc() = "City Horizon Native C++20 Core Bindings (CH_GRID_V1 / CH_MAP_V1 / CH_RENDER_V1 / CH_SEMANTIC_STATE_V1 / CH_PLACEMENT_V1 / CH_TRANSACTION_V1 / CH_SHORELINE_V1)";

    // Core identity & contract versions
    m.attr("core_version") = "1.0.0";
    m.attr("grid_contract") = ch::contracts::kGridContract;
    m.attr("map_contract") = ch::contracts::kMapContract;
    m.attr("render_contract") = ch::contracts::kRenderContract;
    m.attr("anchor_contract") = ch::kAnchorContract;
    m.attr("footprint_contract") = ch::kFootprintContract;
    m.attr("connector_contract") = ch::kConnectorContract;
    m.attr("semantic_overlay_contract") = ch::kSemanticOverlayContract;
    m.attr("semantic_state_contract") = ch::kSemanticStateContract;
    m.attr("placement_contract") = ch::kPlacementContract;
    m.attr("transaction_contract") = ch::kTransactionContract;
    m.attr("shoreline_contract") = ch::kShorelineContract;

    // Locked constants
    m.attr("kTileWidth") = ch::contracts::kTileWidth;
    m.attr("kTileHeight") = ch::contracts::kTileHeight;
    m.attr("kDiamondRatio") = ch::contracts::kDiamondRatio;
    m.attr("kHorizontalWorldRotationDeg") = ch::contracts::kHorizontalWorldRotationDeg;
    m.attr("kIsometricInclinationDeg") = ch::contracts::kIsometricInclinationDeg;
    m.attr("kMapMin") = ch::contracts::kMapMin;
    m.attr("kMapMax") = ch::contracts::kMapMax;

    // Grid types
    py::class_<ch::GridCoord>(m, "GridCoord")
        .def(py::init<int, int>(), py::arg("x") = 0, py::arg("y") = 0)
        .def_readwrite("x", &ch::GridCoord::x)
        .def_readwrite("y", &ch::GridCoord::y)
        .def("__eq__", &ch::GridCoord::operator==)
        .def("__repr__", [](const ch::GridCoord& c) {
            return "<GridCoord (" + std::to_string(c.x) + ", " + std::to_string(c.y) + ")>";
        });

    py::class_<ch::GridBounds>(m, "GridBounds")
        .def(py::init<>())
        .def_readwrite("min_x", &ch::GridBounds::min_x)
        .def_readwrite("min_y", &ch::GridBounds::min_y)
        .def_readwrite("max_x", &ch::GridBounds::max_x)
        .def_readwrite("max_y", &ch::GridBounds::max_y)
        .def("contains", py::overload_cast<int, int>(&ch::GridBounds::contains, py::const_))
        .def("contains_coord", py::overload_cast<const ch::GridCoord&>(&ch::GridBounds::contains, py::const_));

    m.def("tile_key", &ch::tile_key, py::arg("x"), py::arg("y"));

    // Camera & Projection types
    py::enum_<ch::CameraRotation>(m, "CameraRotation")
        .value("r0", ch::CameraRotation::r0)
        .value("r90", ch::CameraRotation::r90)
        .value("r180", ch::CameraRotation::r180)
        .value("r270", ch::CameraRotation::r270)
        .export_values();

    py::class_<ch::CameraState>(m, "CameraState")
        .def(py::init<>())
        .def_readwrite("pan_x", &ch::CameraState::pan_x)
        .def_readwrite("pan_y", &ch::CameraState::pan_y)
        .def_readwrite("zoom", &ch::CameraState::zoom)
        .def_readwrite("rotation", &ch::CameraState::rotation);

    py::class_<ch::WorldPoint>(m, "WorldPoint")
        .def(py::init<>())
        .def_readwrite("x", &ch::WorldPoint::x)
        .def_readwrite("y", &ch::WorldPoint::y);

    py::class_<ch::ScreenPoint>(m, "ScreenPoint")
        .def(py::init<>())
        .def_readwrite("x", &ch::ScreenPoint::x)
        .def_readwrite("y", &ch::ScreenPoint::y);

    // Projection functions
    m.def("camera_view_point", &ch::camera_view_point, py::arg("x"), py::arg("y"), py::arg("rotation"));
    m.def("logical_world_point", &ch::logical_world_point, py::arg("x"), py::arg("y"), py::arg("rotation"));
    m.def("tile_visual_top_world", &ch::tile_visual_top_world, py::arg("tile_x"), py::arg("tile_y"), py::arg("rotation") = ch::CameraRotation::r0);
    m.def("building_visual_ground_world", &ch::building_visual_ground_world,
          py::arg("tile_x"), py::arg("tile_y"), py::arg("footprint_width"), py::arg("footprint_height"),
          py::arg("rotation") = ch::CameraRotation::r0);
    m.def("camera_depth_key", &ch::camera_depth_key, py::arg("world_x"), py::arg("world_y"), py::arg("camera"));
    m.def("world_to_screen_point", &ch::world_to_screen_point,
          py::arg("world_x"), py::arg("world_y"), py::arg("camera"), py::arg("viewport_w"), py::arg("viewport_h"));
    m.def("screen_to_tile_coord", &ch::screen_to_tile_coord,
          py::arg("screen_x"), py::arg("screen_y"), py::arg("camera"), py::arg("viewport_w"), py::arg("viewport_h"));

    // Read-only MapDocument entry types
    py::class_<ch::TerrainTileEntry>(m, "TerrainTileEntry")
        .def_readonly("tile_x", &ch::TerrainTileEntry::tile_x)
        .def_readonly("tile_y", &ch::TerrainTileEntry::tile_y)
        .def_readonly("texture", &ch::TerrainTileEntry::texture)
        .def_readonly("terrain_definition", &ch::TerrainTileEntry::terrain_definition);

    py::class_<ch::BuildingInstanceEntry>(m, "BuildingInstanceEntry")
        .def_readonly("instance_id", &ch::BuildingInstanceEntry::instance_id)
        .def_readonly("definition_id", &ch::BuildingInstanceEntry::definition_id)
        .def_readonly("tile_x", &ch::BuildingInstanceEntry::tile_x)
        .def_readonly("tile_y", &ch::BuildingInstanceEntry::tile_y)
        .def_readonly("rotation", &ch::BuildingInstanceEntry::rotation);

    py::class_<ch::RoadTileEntry>(m, "RoadTileEntry")
        .def_readonly("tile_x", &ch::RoadTileEntry::tile_x)
        .def_readonly("tile_y", &ch::RoadTileEntry::tile_y);

    // MapDocument
    py::class_<ch::MapDocument>(m, "MapDocument")
        .def(py::init<std::string>(), py::arg("raw_json_content"))
        .def_property_readonly("raw_content", &ch::MapDocument::raw_content)
        .def("terrain_tiles", &ch::MapDocument::terrain_tiles)
        .def("buildings", &ch::MapDocument::buildings)
        .def("roads", &ch::MapDocument::roads)
        .def("get_terrain_at", &ch::MapDocument::get_terrain_at, py::arg("tile_x"), py::arg("tile_y"))
        .def("get_building_at", &ch::MapDocument::get_building_at, py::arg("tile_x"), py::arg("tile_y"))
        .def("is_road_at", &ch::MapDocument::is_road_at, py::arg("tile_x"), py::arg("tile_y"))
        .def("set_terrain_texture_at", &ch::MapDocument::set_terrain_texture_at, py::arg("tile_x"), py::arg("tile_y"), py::arg("texture_path"))
        .def("set_terrain_definition_at", &ch::MapDocument::set_terrain_definition_at, py::arg("tile_x"), py::arg("tile_y"), py::arg("terrain_def_id"), py::arg("texture_path") = "")
        .def_static("load_from_file", &ch::MapDocument::load_from_file, py::arg("filepath"))
        .def_static("create_empty", &ch::MapDocument::create_empty, py::arg("name") = "Untitled City", py::arg("width") = 32, py::arg("height") = 32);

    // BuildingCatalog & BuildingManager (Game Runtime representation)
    py::class_<BuildingCatalog>(m, "BuildingCatalog")
        .def(py::init<>())
        .def("load_from_directory", [](BuildingCatalog& self, const std::string& dir) {
            return self.load_from_directory(dir);
        }, py::arg("directory"));

    py::class_<BuildingManager>(m, "BuildingManager")
        .def(py::init<int, int>(), py::arg("map_min") = ch::contracts::kMapMin, py::arg("map_max") = ch::contracts::kMapMax)
        .def("restore_instance", [](BuildingManager& self, const BuildingCatalog& catalog, const std::string& def_id, int x, int y, int rot) {
            const BuildingDefinition* def = catalog.find(def_id);
            if (def == nullptr) return false;
            BuildingInstance inst;
            inst.instance_id = self.next_instance_id();
            inst.definition_id = def_id;
            inst.tile_x = x;
            inst.tile_y = y;
            inst.rotation = static_cast<BuildingRotation>(rot);
            return self.restore_instance(*def, inst);
        }, py::arg("catalog"), py::arg("definition_id"), py::arg("tile_x"), py::arg("tile_y"), py::arg("rotation") = 0);

    // Validation Report & Function
    py::class_<ch::MapValidationReport>(m, "MapValidationReport")
        .def_readonly("valid", &ch::MapValidationReport::valid)
        .def_readonly("errors", &ch::MapValidationReport::errors)
        .def_readonly("warnings", &ch::MapValidationReport::warnings)
        .def_readonly("legacy_debt", &ch::MapValidationReport::legacy_debt);

    m.def("validate_map_document", &ch::validate_map_document, py::arg("document"));

    m.def("compute_document_geometry_signature",
          py::overload_cast<const ch::MapDocument&, const BuildingCatalog&, const ch::CameraState&, float, float>(&ch::MapRenderer::compute_geometry_signature),
          py::arg("document"), py::arg("catalog"), py::arg("camera"), py::arg("viewport_w"), py::arg("viewport_h"));

    m.def("compute_game_geometry_signature",
          py::overload_cast<const BuildingManager&, const BuildingCatalog&, const ch::CameraState&, float, float>(&ch::MapRenderer::compute_geometry_signature),
          py::arg("manager"), py::arg("catalog"), py::arg("camera"), py::arg("viewport_w"), py::arg("viewport_h"));

    // Geometry Records, Signatures & Diff
    py::class_<ch::RenderGeometryRecord>(m, "RenderGeometryRecord")
        .def(py::init<>())
        .def_readwrite("layer", &ch::RenderGeometryRecord::layer)
        .def_readwrite("asset_id", &ch::RenderGeometryRecord::asset_id)
        .def_readwrite("grid_x", &ch::RenderGeometryRecord::grid_x)
        .def_readwrite("grid_y", &ch::RenderGeometryRecord::grid_y)
        .def_readwrite("screen_x", &ch::RenderGeometryRecord::screen_x)
        .def_readwrite("screen_y", &ch::RenderGeometryRecord::screen_y)
        .def_readwrite("dest_w", &ch::RenderGeometryRecord::dest_w)
        .def_readwrite("dest_h", &ch::RenderGeometryRecord::dest_h)
        .def_readwrite("anchor_x", &ch::RenderGeometryRecord::anchor_x)
        .def_readwrite("anchor_y", &ch::RenderGeometryRecord::anchor_y)
        .def_readwrite("art_scale", &ch::RenderGeometryRecord::art_scale)
        .def_readwrite("depth_key", &ch::RenderGeometryRecord::depth_key)
        .def_readwrite("footprint_w", &ch::RenderGeometryRecord::footprint_w)
        .def_readwrite("footprint_h", &ch::RenderGeometryRecord::footprint_h);

    py::class_<ch::RenderGeometryDiff>(m, "RenderGeometryDiff")
        .def(py::init<>())
        .def_readwrite("match", &ch::RenderGeometryDiff::match)
        .def_readwrite("report", &ch::RenderGeometryDiff::report);

    py::class_<ch::RenderGeometrySignature>(m, "RenderGeometrySignature")
        .def(py::init<>())
        .def_readwrite("records", &ch::RenderGeometrySignature::records)
        .def("compute_hash", &ch::RenderGeometrySignature::compute_hash);

    m.def("compare_signatures", &ch::compare_signatures, py::arg("game_sig"), py::arg("forge_sig"));

    py::enum_<ch::Season>(m, "Season")
        .value("NORMAL", ch::Season::Normal)
        .value("SPRING", ch::Season::Spring)
        .value("SUMMER", ch::Season::Summer)
        .value("AUTUMN", ch::Season::Autumn)
        .value("WINTER", ch::Season::Winter)
        .export_values();

    py::class_<ch::RenderContext>(m, "RenderContext")
        .def(py::init<>())
        .def_readwrite("season", &ch::RenderContext::season)
        .def_readwrite("snow_coverage", &ch::RenderContext::snow_coverage)
        .def_readwrite("wetness", &ch::RenderContext::wetness)
        .def_readwrite("diagnostic_overlay", &ch::RenderContext::diagnostic_overlay);

    // Native SDL3 Viewport
    py::class_<ch::MapForgeNativeViewport>(m, "MapForgeNativeViewport")
        .def(py::init<>())
        .def("initialize", [](ch::MapForgeNativeViewport& self, std::uintptr_t hwnd, int w, int h, const std::string& root) {
            return self.initialize(reinterpret_cast<void*>(hwnd), w, h, root);
        }, py::arg("win32_hwnd"), py::arg("physical_width"), py::arg("physical_height"), py::arg("asset_root"))
        .def("initialize_offscreen", &ch::MapForgeNativeViewport::initialize_offscreen, py::arg("physical_width"), py::arg("physical_height"), py::arg("asset_root"))
        .def("save_frame_to_png", &ch::MapForgeNativeViewport::save_frame_to_png, py::arg("filepath"))
        .def("resize", &ch::MapForgeNativeViewport::resize, py::arg("physical_width"), py::arg("physical_height"))
        .def("set_camera", &ch::MapForgeNativeViewport::set_camera, py::arg("camera"))
        .def("load_map_document", &ch::MapForgeNativeViewport::load_map_document, py::arg("document"))
        .def("set_render_context", &ch::MapForgeNativeViewport::set_render_context, py::arg("context"))
        .def("render_context", &ch::MapForgeNativeViewport::render_context)
        .def("set_prop_phase", &ch::MapForgeNativeViewport::set_prop_phase, py::arg("phase"))
        .def("prop_phase", &ch::MapForgeNativeViewport::prop_phase)
        .def("load_overlay_manifest", [](ch::MapForgeNativeViewport& self, const std::string& path) {
            return self.overlay_catalog().load_manifest(path);
        }, py::arg("path"))
        .def("load_overlay_directory", [](ch::MapForgeNativeViewport& self, const std::string& path) {
            return self.overlay_catalog().load_directory(path);
        }, py::arg("path"))
        .def("load_animated_prop_manifest", [](ch::MapForgeNativeViewport& self, const std::string& path) {
            return self.animated_prop_catalog().load_manifest(path);
        }, py::arg("path"))
        .def("load_animated_prop_directory", [](ch::MapForgeNativeViewport& self, const std::string& path) {
            return self.animated_prop_catalog().load_directory(path);
        }, py::arg("path"))
        .def("reload_asset_catalogs", &ch::MapForgeNativeViewport::reload_asset_catalogs)
        .def("set_hover_tile", &ch::MapForgeNativeViewport::set_hover_tile, py::arg("tile_x"), py::arg("tile_y"), py::arg("enabled"))
        .def("set_hover_brush_radius", &ch::MapForgeNativeViewport::set_hover_brush_radius, py::arg("radius"))
        .def("render_frame", &ch::MapForgeNativeViewport::render_frame)
        .def("compute_geometry_signature", &ch::MapForgeNativeViewport::compute_geometry_signature, py::arg("catalog"))
        .def("shutdown", &ch::MapForgeNativeViewport::shutdown)
        .def("is_initialized", &ch::MapForgeNativeViewport::is_initialized)
        .def("set_view_mode", &ch::MapForgeNativeViewport::set_view_mode, py::arg("mode"))
        .def("view_mode", &ch::MapForgeNativeViewport::view_mode)
        .def("set_active_channels", &ch::MapForgeNativeViewport::set_active_channels, py::arg("channel_bitmask"))
        .def("active_channels", &ch::MapForgeNativeViewport::active_channels)
        .def("set_channel_opacity", &ch::MapForgeNativeViewport::set_channel_opacity, py::arg("opacity"))
        .def("channel_opacity", &ch::MapForgeNativeViewport::channel_opacity);

    py::enum_<ch::AnimationDriver>(m, "AnimationDriver")
        .value("TIME", ch::AnimationDriver::Time)
        .value("ROTATION", ch::AnimationDriver::Rotation)
        .value("OSCILLATE", ch::AnimationDriver::Oscillate)
        .value("PATH", ch::AnimationDriver::Path)
        .value("STATE", ch::AnimationDriver::State)
        .value("DISTANCE", ch::AnimationDriver::Distance)
        .export_values();

    py::enum_<ch::VisualPresentation>(m, "VisualPresentation")
        .value("TRANSFORM_ROTATION", ch::VisualPresentation::TransformRotation)
        .value("ATLAS_PHASE", ch::VisualPresentation::AtlasPhase)
        .export_values();

    enum class PaintMode { VisualOnly, VisualAndSemantics };
    py::enum_<PaintMode>(m, "PaintMode")
        .value("VISUAL_ONLY", PaintMode::VisualOnly)
        .value("VISUAL_AND_SEMANTICS", PaintMode::VisualAndSemantics)
        .export_values();

    py::class_<ch::TerrainSemanticsDefinition>(m, "TerrainSemanticsDefinition")
        .def(py::init<>())
        .def_readwrite("id", &ch::TerrainSemanticsDefinition::id)
        .def_readwrite("surface", &ch::TerrainSemanticsDefinition::surface)
        .def_readwrite("buildable", &ch::TerrainSemanticsDefinition::buildable)
        .def_readwrite("water", &ch::TerrainSemanticsDefinition::water)
        .def_readwrite("pedestrian_traversable", &ch::TerrainSemanticsDefinition::pedestrian_traversable)
        .def_readwrite("navigation_type", &ch::TerrainSemanticsDefinition::navigation_type);

    py::class_<ch::TerrainSemanticsCatalog>(m, "TerrainSemanticsCatalog")
        .def(py::init<>())
        .def("load_manifest", [](ch::TerrainSemanticsCatalog& self, const std::string& path) {
            return self.load_manifest(path);
        }, py::arg("manifest_path"))
        .def("find", &ch::TerrainSemanticsCatalog::find, py::arg("terrain_def_id"), py::return_value_policy::reference)
        .def_static("global_instance", &ch::TerrainSemanticsCatalog::global_instance, py::return_value_policy::reference)
        .def_static("set_global_instance", &ch::TerrainSemanticsCatalog::set_global_instance, py::arg("catalog"));

    m.def("paint_tile", [](ch::MapDocument& doc, int tile_x, int tile_y, const std::string& texture_path, const std::string& terrain_def_id, PaintMode mode) {
        if (mode == PaintMode::VisualOnly) {
            doc.set_terrain_texture_at(tile_x, tile_y, texture_path);
        } else {
            doc.set_terrain_definition_at(tile_x, tile_y, terrain_def_id, texture_path);
        }
    }, py::arg("doc"), py::arg("tile_x"), py::arg("tile_y"), py::arg("texture_path"), py::arg("terrain_def_id"), py::arg("mode"));

    // Phase D — Semantic Grid & Governance Bindings
    py::enum_<ch::SemanticState>(m, "SemanticState")
        .value("VALID", ch::SemanticState::valid)
        .value("INVALID", ch::SemanticState::invalid)
        .value("NOT_DECLARED", ch::SemanticState::not_declared)
        .value("NOT_APPLICABLE", ch::SemanticState::not_applicable)
        .export_values();

    py::enum_<ch::AnchorType>(m, "AnchorType")
        .value("GROUND_ANCHOR", ch::AnchorType::ground_anchor)
        .value("TRUNK_CONTACT", ch::AnchorType::trunk_contact)
        .value("FEET_CONTACT", ch::AnchorType::feet_contact)
        .value("TILE_CENTER", ch::AnchorType::tile_center)
        .value("LAND_WATER_CONNECTOR", ch::AnchorType::land_water_connector)
        .export_values();

    py::enum_<ch::ConnectorType>(m, "ConnectorType")
        .value("ROAD_N", ch::ConnectorType::road_n)
        .value("ROAD_E", ch::ConnectorType::road_e)
        .value("ROAD_S", ch::ConnectorType::road_s)
        .value("ROAD_W", ch::ConnectorType::road_w)
        .value("SIDEWALK", ch::ConnectorType::sidewalk)
        .value("ENTRANCE", ch::ConnectorType::entrance)
        .value("GROUND", ch::ConnectorType::ground)
        .value("WATER_EDGE", ch::ConnectorType::water_edge)
        .value("PEDESTRIAN", ch::ConnectorType::pedestrian)
        .value("SERVICE", ch::ConnectorType::service)
        .export_values();

    py::class_<ch::TileSemanticInfo>(m, "TileSemanticInfo")
        .def(py::init<>())
        .def_readwrite("tile", &ch::TileSemanticInfo::tile)
        .def_readwrite("terrain_type", &ch::TileSemanticInfo::terrain_type)
        .def_readwrite("footprint_state", &ch::TileSemanticInfo::footprint_state)
        .def_readwrite("occupancy_state", &ch::TileSemanticInfo::occupancy_state)
        .def_readwrite("buildable_state", &ch::TileSemanticInfo::buildable_state)
        .def_readwrite("road_state", &ch::TileSemanticInfo::road_state)
        .def_readwrite("sidewalk_state", &ch::TileSemanticInfo::sidewalk_state)
        .def_readwrite("water_state", &ch::TileSemanticInfo::water_state)
        .def_readwrite("pivot_state", &ch::TileSemanticInfo::pivot_state)
        .def_readwrite("entrance_state", &ch::TileSemanticInfo::entrance_state)
        .def_readwrite("connector_state", &ch::TileSemanticInfo::connector_state)
        .def_readwrite("no_build_state", &ch::TileSemanticInfo::no_build_state)
        .def_readwrite("navigation_state", &ch::TileSemanticInfo::navigation_state)
        .def_readwrite("region_state", &ch::TileSemanticInfo::region_state)
        .def_readwrite("occupied_by_asset", &ch::TileSemanticInfo::occupied_by_asset)
        .def_readwrite("footprint_width", &ch::TileSemanticInfo::footprint_width)
        .def_readwrite("footprint_height", &ch::TileSemanticInfo::footprint_height);

    py::class_<ch::SemanticDivergence>(m, "SemanticDivergence")
        .def(py::init<>())
        .def_readwrite("object_id", &ch::SemanticDivergence::object_id)
        .def_readwrite("tile", &ch::SemanticDivergence::tile)
        .def_readwrite("contract", &ch::SemanticDivergence::contract)
        .def_readwrite("field", &ch::SemanticDivergence::field)
        .def_readwrite("expected", &ch::SemanticDivergence::expected)
        .def_readwrite("actual", &ch::SemanticDivergence::actual)
        .def_readwrite("delta", &ch::SemanticDivergence::delta)
        .def_readwrite("status", &ch::SemanticDivergence::status)
        .def("to_formatted_string", &ch::SemanticDivergence::to_formatted_string);

    m.def("inspect_tile_channels", [](const ch::MapDocument& doc, int tile_x, int tile_y) {
        ch::SemanticWorldView world;
        world.map_document = &doc;
        return ch::SemanticGrid::inspect_tile_channels(world, ch::GridCoord(tile_x, tile_y));
    }, py::arg("document"), py::arg("tile_x"), py::arg("tile_y"));

    m.def("inspect_tile_channels_with_terrain_catalog", [](const ch::MapDocument& doc, int tile_x, int tile_y,
                                                              const std::string& catalog_json) {
        ch::TerrainSemanticCatalog catalog(catalog_json);
        ch::SemanticWorldView world;
        world.map_document = &doc;
        world.terrain_catalog = &catalog;
        return ch::SemanticGrid::inspect_tile_channels(world, ch::GridCoord(tile_x, tile_y));
    }, py::arg("document"), py::arg("tile_x"), py::arg("tile_y"), py::arg("catalog_json"));

    struct BuildingCatalogAdapter : public ch::IAssetCatalogView {
        const BuildingCatalog& catalog;
        explicit BuildingCatalogAdapter(const BuildingCatalog& c) : catalog(c) {}
        ch::AssetFootprintInfo get_footprint(std::string_view asset_id) const override {
            const BuildingDefinition* def = catalog.find(std::string(asset_id));
            if (!def) return {1, 1, false};
            return {def->footprint_width, def->footprint_height, true};
        }
    };

    m.def("validate_map_semantics", [](const ch::MapDocument& doc, const BuildingCatalog& catalog) {
        ch::SemanticWorldView world;
        world.map_document = &doc;
        BuildingCatalogAdapter adapter(catalog);
        return ch::SemanticGrid::validate_map_semantics(world, adapter);
    }, py::arg("document"), py::arg("catalog"));

    // Phase E — Deterministic Placement Engine Bindings
    py::enum_<ch::PlacementCategory>(m, "PlacementCategory")
        .value("BUILDING", ch::PlacementCategory::building)
        .value("ROAD", ch::PlacementCategory::road)
        .value("TREE", ch::PlacementCategory::tree)
        .value("DECORATION", ch::PlacementCategory::decoration)
        .value("WATER_STRUCTURE", ch::PlacementCategory::water_structure)
        .export_values();

    py::enum_<ch::PlacementViolation>(m, "PlacementViolation")
        .value("CH_PLACE_BOUNDS", ch::PlacementViolation::bounds_exceeded)
        .value("CH_PLACE_OCCUPIED", ch::PlacementViolation::occupied)
        .value("CH_PLACE_TERRAIN", ch::PlacementViolation::terrain_incompatible)
        .value("CH_PLACE_ANCHOR", ch::PlacementViolation::anchor_invalid)
        .value("CH_PLACE_CONNECTOR", ch::PlacementViolation::connector_missing)
        .value("CH_PLACE_ROAD_REQUIRED", ch::PlacementViolation::road_required)
        .value("CH_PLACE_WATER_REQUIRED", ch::PlacementViolation::water_required)
        .value("CH_PLACE_CATEGORY_RULE", ch::PlacementViolation::category_rule)
        .export_values();

    py::class_<ch::PlacementRequest>(m, "PlacementRequest")
        .def(py::init<>())
        .def_readwrite("object_id", &ch::PlacementRequest::object_id)
        .def_readwrite("category", &ch::PlacementRequest::category)
        .def_readwrite("origin", &ch::PlacementRequest::origin)
        .def_readwrite("rotation", &ch::PlacementRequest::rotation);

    py::class_<ch::PlacementResult>(m, "PlacementResult")
        .def(py::init<>())
        .def_readwrite("object_id", &ch::PlacementResult::object_id)
        .def_readwrite("state", &ch::PlacementResult::state)
        .def_readwrite("violations", &ch::PlacementResult::violations)
        .def_readwrite("affected_tiles", &ch::PlacementResult::affected_tiles)
        .def_readwrite("resolved_origin", &ch::PlacementResult::resolved_origin)
        .def_readwrite("conflicting_tile", &ch::PlacementResult::conflicting_tile)
        .def_readwrite("expected_connector", &ch::PlacementResult::expected_connector)
        .def("to_formatted_string", &ch::PlacementResult::to_formatted_string);

    m.def("can_place", [](const ch::MapDocument& doc, const BuildingCatalog& catalog, const ch::PlacementRequest& req) {
        ch::SemanticWorldView world;
        world.map_document = &doc;
        BuildingCatalogAdapter adapter(catalog);
        return ch::PlacementEngine::can_place(req, world, adapter);
    }, py::arg("document"), py::arg("catalog"), py::arg("request"));

    // Phase F — Transaction Engine Bindings
    py::class_<ch::TransactionManager>(m, "TransactionManager")
        .def(py::init<std::size_t>(), py::arg("max_depth") = 100)
        .def("begin_transaction", &ch::TransactionManager::begin_transaction, py::arg("description"))
        .def("commit_transaction", &ch::TransactionManager::commit_transaction)
        .def("cancel_transaction", &ch::TransactionManager::cancel_transaction)
        .def("can_undo", &ch::TransactionManager::can_undo)
        .def("can_redo", &ch::TransactionManager::can_redo)
        .def("clear_history", &ch::TransactionManager::clear_history)
        .def("undo_stack_size", &ch::TransactionManager::undo_stack_size)
        .def("redo_stack_size", &ch::TransactionManager::redo_stack_size)
        .def("is_in_batch", &ch::TransactionManager::is_in_batch);

    // Phase H — Shoreline Autotiling Engine Bindings
    py::enum_<ch::ShorelinePiece>(m, "ShorelinePiece")
        .value("BORDER_NORTH", ch::ShorelinePiece::border_north)
        .value("BORDER_EAST", ch::ShorelinePiece::border_east)
        .value("BORDER_SOUTH", ch::ShorelinePiece::border_south)
        .value("BORDER_WEST", ch::ShorelinePiece::border_west)
        .value("OUTER_NE", ch::ShorelinePiece::outer_ne)
        .value("OUTER_SE", ch::ShorelinePiece::outer_se)
        .value("OUTER_SW", ch::ShorelinePiece::outer_sw)
        .value("OUTER_NW", ch::ShorelinePiece::outer_nw)
        .value("INNER_NE", ch::ShorelinePiece::inner_ne)
        .value("INNER_SE", ch::ShorelinePiece::inner_se)
        .value("INNER_SW", ch::ShorelinePiece::inner_sw)
        .value("INNER_NW", ch::ShorelinePiece::inner_nw)
        .export_values();

    py::class_<ch::ShorelineRecipe>(m, "ShorelineRecipe")
        .def(py::init<>())
        .def_readwrite("pieces", &ch::ShorelineRecipe::pieces)
        .def("normalize", &ch::ShorelineRecipe::normalize);

    py::class_<ch::ShorelineEdit>(m, "ShorelineEdit")
        .def(py::init<>())
        .def_readwrite("tile", &ch::ShorelineEdit::tile)
        .def_readwrite("recipe", &ch::ShorelineEdit::recipe);

    py::class_<ch::AutotileResult>(m, "AutotileResult")
        .def(py::init<>())
        .def_readwrite("edits", &ch::AutotileResult::edits);

    m.def("resolve_shoreline", &ch::ShorelineAutotiler::resolve_shoreline, py::arg("mask"));

    m.def("evaluate_shoreline", [](const ch::MapDocument& doc, int min_x, int min_y, int max_x, int max_y) {
        ch::SemanticWorldView world;
        world.map_document = &doc;
        ch::GridBounds bounds;
        bounds.min_x = min_x; bounds.min_y = min_y;
        bounds.max_x = max_x; bounds.max_y = max_y;
        return ch::ShorelineAutotiler::evaluate_shoreline(world, bounds);
    }, py::arg("document"), py::arg("min_x") = -24, py::arg("min_y") = -24, py::arg("max_x") = 23, py::arg("max_y") = 23);
}

