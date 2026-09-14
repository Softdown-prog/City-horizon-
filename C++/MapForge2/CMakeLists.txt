cmake_minimum_required(VERSION 3.24)

project(MapForge2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Widgets)

include(FetchContent)
set(SDL_TESTS OFF CACHE BOOL "Disable SDL tests for the Studio build" FORCE)
set(SDL_EXAMPLES OFF CACHE BOOL "Disable SDL examples for the Studio build" FORCE)
FetchContent_Declare(
    SDL3
    GIT_REPOSITORY https://github.com/libsdl-org/SDL.git
    GIT_TAG release-3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(SDL3)

get_filename_component(CH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)

# Canonical game-side state required by ch_render.  This standalone Studio
# build compiles the same source files instead of introducing Qt copies.
add_library(mapforge2_canonical STATIC
    ${CH_ROOT}/src/ch_core/projection.cpp
    ${CH_ROOT}/src/ch_core/map_document.cpp
    ${CH_ROOT}/src/ch_core/validation.cpp
    ${CH_ROOT}/src/ch_core/semantic_grid.cpp
    ${CH_ROOT}/src/ch_core/placement_engine.cpp
    ${CH_ROOT}/src/ch_core/transaction_manager.cpp
    ${CH_ROOT}/src/ch_core/shoreline_autotile.cpp
)
target_include_directories(mapforge2_canonical PUBLIC ${CH_ROOT})

# Canonical City Horizon renderer.  Qt never reimplements game artwork.
add_library(mapforge2_render STATIC
    ${CH_ROOT}/src/ch_render/map_renderer.cpp
    ${CH_ROOT}/src/ch_render/semantic_renderer.cpp
    ${CH_ROOT}/src/ch_render/economy_stubs.cpp
    ${CH_ROOT}/src/ch_render/shoreline_catalog.cpp
    ${CH_ROOT}/src/building_system.cpp
    ${CH_ROOT}/src/farming_system.cpp
    ${CH_ROOT}/src/land_system.cpp
    ${CH_ROOT}/src/road_system.cpp
    ${CH_ROOT}/src/road_visual_catalog.cpp
    ${CH_ROOT}/src/sidewalk_system.cpp
)
target_include_directories(mapforge2_render PUBLIC ${CH_ROOT})
target_link_libraries(mapforge2_render PUBLIC mapforge2_canonical SDL3::SDL3)

# Qt-independent first layer of the future City Horizon Studio.
# C++ defines stable capabilities/contracts; the Qt editor is only a visual client.
add_library(mapforge2_studio_core STATIC
    src/studio_content.cpp
)
target_include_directories(mapforge2_studio_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

add_library(mapforge2_editor STATIC
    src/editor_document.cpp
    src/editor_history.cpp
    src/canonical_viewport.cpp
    src/editor_canvas.cpp
    src/content_pack_qt.cpp
    src/studio_panel.cpp
    src/production_studio_panel.cpp
    src/main_window.cpp
)
target_include_directories(mapforge2_editor PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CH_ROOT}
)
target_link_libraries(mapforge2_editor PUBLIC
    mapforge2_canonical
    mapforge2_render
    mapforge2_studio_core
    SDL3::SDL3
    Qt6::Widgets
)

add_executable(MapForge2 WIN32
    src/main.cpp
)
target_link_libraries(MapForge2 PRIVATE mapforge2_editor Qt6::Widgets)

if(MSVC)
    target_compile_options(mapforge2_canonical PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(mapforge2_render PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(mapforge2_studio_core PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(mapforge2_editor PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(MapForge2 PRIVATE /W4 /permissive- /utf-8)
else()
    target_compile_options(mapforge2_canonical PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapforge2_render PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapforge2_studio_core PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapforge2_editor PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(MapForge2 PRIVATE -Wall -Wextra -Wpedantic)
endif()

# A compiled Studio artifact must carry the exact assets consumed by ch_render.
# Keeping them next to the executable also makes the IDE working directory irrelevant.
add_custom_command(TARGET MapForge2 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CH_ROOT}/assets"
        "$<TARGET_FILE_DIR:MapForge2>/assets"
)
if(TARGET SDL3::SDL3-shared)
    add_custom_command(TARGET MapForge2 POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:SDL3::SDL3-shared>"
            "$<TARGET_FILE_DIR:MapForge2>"
    )
endif()

install(TARGETS MapForge2 RUNTIME DESTINATION .)
