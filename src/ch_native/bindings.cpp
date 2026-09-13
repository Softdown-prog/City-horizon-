#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "src/ch_core/contracts.h"
#include "src/ch_core/grid.h"
#include "src/ch_core/projection.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"

namespace py = pybind11;

PYBIND11_MODULE(city_horizon_native, m) {
    m.doc() = "City Horizon Native C++20 Core Bindings (CH_GRID_V1 / CH_MAP_V1 / CH_RENDER_V1)";

    // Core identity & contract versions
    m.attr("core_version") = "1.0.0";
    m.attr("grid_contract") = ch::contracts::kGridContract;
    m.attr("map_contract") = ch::contracts::kMapContract;
    m.attr("render_contract") = ch::contracts::kRenderContract;

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
        .def_readonly("texture", &ch::TerrainTileEntry::texture);

    py::class_<ch::BuildingInstanceEntry>(m, "BuildingInstanceEntry")
        .def_readonly("instance_id", &ch::BuildingInstanceEntry::instance_id)
        .def_readonly("definition_id", &ch::BuildingInstanceEntry::definition_id)
        .def_readonly("tile_x", &ch::BuildingInstanceEntry::tile_x)
        .def_readonly("tile_y", &ch::BuildingInstanceEntry::tile_y)
        .def_readonly("rotation", &ch::BuildingInstanceEntry::rotation);

    py::class_<ch::RoadTileEntry>(m, "RoadTileEntry")
        .def_readonly("tile_x", &ch::RoadTileEntry::tile_x)
        .def_readonly("tile_y", &ch::RoadTileEntry::tile_y);

    // MapDocument (Read-Only)
    py::class_<ch::MapDocument>(m, "MapDocument")
        .def(py::init<std::string>(), py::arg("raw_json_content"))
        .def_property_readonly("raw_content", &ch::MapDocument::raw_content)
        .def("terrain_tiles", &ch::MapDocument::terrain_tiles)
        .def("buildings", &ch::MapDocument::buildings)
        .def("roads", &ch::MapDocument::roads)
        .def("get_terrain_at", &ch::MapDocument::get_terrain_at, py::arg("tile_x"), py::arg("tile_y"))
        .def("get_building_at", &ch::MapDocument::get_building_at, py::arg("tile_x"), py::arg("tile_y"))
        .def("is_road_at", &ch::MapDocument::is_road_at, py::arg("tile_x"), py::arg("tile_y"))
        .def_static("load_from_file", &ch::MapDocument::load_from_file, py::arg("filepath"));

    // Validation Report & Function
    py::class_<ch::MapValidationReport>(m, "MapValidationReport")
        .def_readonly("valid", &ch::MapValidationReport::valid)
        .def_readonly("errors", &ch::MapValidationReport::errors)
        .def_readonly("warnings", &ch::MapValidationReport::warnings)
        .def_readonly("legacy_debt", &ch::MapValidationReport::legacy_debt);

    m.def("validate_map_document", &ch::validate_map_document, py::arg("document"));
}
