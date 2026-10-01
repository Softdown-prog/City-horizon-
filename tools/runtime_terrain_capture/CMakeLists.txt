cmake_minimum_required(VERSION 3.24)
project(ch_runtime_terrain_capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(BUILD_TESTING OFF CACHE BOOL "Disable root tests for capture build" FORCE)
set(CH_VISITOR_FORGE_PREVIEW OFF CACHE BOOL "Disable visitor forge preview" FORCE)

add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../.." city_horizon_root)

add_executable(ch_runtime_terrain_visual_capture
    "${CMAKE_CURRENT_LIST_DIR}/runtime_terrain_visual_capture.cpp"
)
target_link_libraries(ch_runtime_terrain_visual_capture PRIVATE ch_core ch_render SDL3::SDL3)
