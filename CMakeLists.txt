cmake_minimum_required(VERSION 3.24)

project(city_builder LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(MSVC)
    file(GLOB_RECURSE CITY_BUILDER_SOURCE_FILES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")
    file(GLOB_RECURSE CITY_BUILDER_HEADER_FILES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.h")
    set_source_files_properties(${CITY_BUILDER_SOURCE_FILES}
        PROPERTIES OBJECT_DEPENDS "${CITY_BUILDER_HEADER_FILES}")
endif()

include(FetchContent)

# SDL 3.4 added SDL_LoadPNG, so the prototype needs no separate SDL_image layer.
FetchContent_Declare(
    SDL3
    GIT_REPOSITORY https://github.com/libsdl-org/SDL.git
    GIT_TAG release-3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(SDL3)

# SDL_mixer 3 provides OGG/Vorbis decoding and mixing on top of SDL3.
# Keep it static and vendor only its decoder dependencies for a self-contained game build.
set(BUILD_SHARED_LIBS OFF)
set(SDLMIXER_VENDORED ON CACHE BOOL "Use vendored SDL_mixer dependencies" FORCE)
set(SDLMIXER_DEPS_SHARED OFF CACHE BOOL "Link SDL_mixer dependencies statically" FORCE)
# This project currently ships only OGG UI effects; avoid compiling decoders it does not use.
set(SDLMIXER_AIFF OFF CACHE BOOL "Disable unused AIFF decoder" FORCE)
set(SDLMIXER_AU OFF CACHE BOOL "Disable unused AU decoder" FORCE)
set(SDLMIXER_FLAC OFF CACHE BOOL "Disable unused FLAC decoder" FORCE)
set(SDLMIXER_GME OFF CACHE BOOL "Disable unused GME decoder" FORCE)
set(SDLMIXER_MIDI OFF CACHE BOOL "Disable unused MIDI decoder" FORCE)
set(SDLMIXER_MOD OFF CACHE BOOL "Disable unused MOD decoder" FORCE)
set(SDLMIXER_MP3 OFF CACHE BOOL "Disable unused MP3 decoder" FORCE)
set(SDLMIXER_OPUS OFF CACHE BOOL "Disable unused Opus decoder" FORCE)
set(SDLMIXER_VOC OFF CACHE BOOL "Disable unused VOC decoder" FORCE)
set(SDLMIXER_WAVE OFF CACHE BOOL "Disable unused WAV decoder" FORCE)
set(SDLMIXER_WAVPACK OFF CACHE BOOL "Disable unused WavPack decoder" FORCE)
set(SDLMIXER_VORBIS_STB OFF CACHE BOOL "Use libvorbisfile for OGG decoding" FORCE)
set(SDLMIXER_VORBIS_VORBISFILE ON CACHE BOOL "Enable OGG Vorbis decoding" FORCE)
set(SDLMIXER_VORBIS_VORBISFILE_SHARED OFF CACHE BOOL "Link Vorbis decoder statically" FORCE)
set(SDLMIXER_SAMPLES OFF CACHE BOOL "Do not build SDL_mixer samples" FORCE)
set(SDLMIXER_TESTS OFF CACHE BOOL "Do not build SDL_mixer tests" FORCE)
FetchContent_Declare(
    SDL3_mixer
    GIT_REPOSITORY https://github.com/libsdl-org/SDL_mixer.git
    GIT_TAG release-3.2.4
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(SDL3_mixer)

FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.12.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(pybind11)

add_library(ch_core STATIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src/ch_core/projection.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/ch_core/map_document.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/src/ch_core/validation.cpp
)
target_include_directories(ch_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

pybind11_add_module(city_horizon_native
    ${CMAKE_CURRENT_SOURCE_DIR}/src/ch_native/bindings.cpp
)
target_link_libraries(city_horizon_native PRIVATE ch_core)
set_target_properties(city_horizon_native PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/map_forge_native"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/map_forge_native"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/map_forge_native"
)

add_executable(city_builder
    src/main.cpp
    src/audio_manager.cpp
    src/building_system.cpp
    src/economy_system.cpp
    src/farming_system.cpp
    src/land_system.cpp
    src/mission_system.cpp
    src/mobile_animation.cpp
    src/mobile_entity.h
    src/navigation_network.cpp
    src/pedestrian_system.cpp
    src/population_system.cpp
    src/power_system.cpp
    src/road_system.cpp
    src/road_visual_catalog.cpp
    src/resource_system.cpp
    src/save_manager.cpp
    src/simulation_clock.cpp
    src/simulation_scheduler.cpp
    src/sidewalk_system.cpp
    src/ui_manager.cpp
    src/vehicle_system.cpp
)
target_link_libraries(city_builder PRIVATE ch_core SDL3::SDL3 SDL3_mixer::SDL3_mixer)

include(CTest)
if(BUILD_TESTING)
    add_executable(ch_core_test
        ${CMAKE_CURRENT_SOURCE_DIR}/src/ch_core/ch_core_test.cpp
    )
    target_link_libraries(ch_core_test PRIVATE ch_core)
    add_test(
        NAME ch_core_test
        COMMAND ch_core_test "${CMAKE_SOURCE_DIR}/assets/scenarios/initial_city.json"
    )
    add_executable(building_system_test
        src/building_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )
    add_test(
        NAME building_system_test
        COMMAND building_system_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(audio_manager_test
        src/audio_manager_test.cpp
        src/audio_manager.cpp
    )
    target_link_libraries(audio_manager_test PRIVATE SDL3::SDL3 SDL3_mixer::SDL3_mixer)
    add_test(
        NAME audio_manager_test
        COMMAND audio_manager_test "${CMAKE_SOURCE_DIR}/assets/audio"
    )
    set_tests_properties(audio_manager_test PROPERTIES ENVIRONMENT "SDL_AUDIO_DRIVER=dummy")

    add_executable(economy_simulation_test
        src/economy_simulation_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    # The normal target name stays stable; this avoids a file-lock collision
    # with a previously interrupted test process on this Windows session.
    set_target_properties(economy_simulation_test PROPERTIES OUTPUT_NAME economy_simulation_test_run)
    add_test(
        NAME economy_simulation_test
        COMMAND economy_simulation_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(road_visual_catalog_test
        src/road_visual_catalog_test.cpp
        src/road_visual_catalog.cpp
    )
    add_test(
        NAME road_visual_catalog_test
        COMMAND road_visual_catalog_test "${CMAKE_SOURCE_DIR}/assets/definitions/road_visual_catalog.json"
    )

    add_executable(sidewalk_topology_test
        src/sidewalk_topology_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )
    add_test(
        NAME sidewalk_topology_test
        COMMAND sidewalk_topology_test
    )

    add_executable(mobile_animation_test
        src/mobile_animation_test.cpp
        src/mobile_animation.cpp
    )
    add_test(
        NAME mobile_animation_test
        COMMAND mobile_animation_test "${CMAKE_SOURCE_DIR}/assets/definitions/animations"
    )

    add_executable(navigation_network_test
        src/navigation_network_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/navigation_network.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )
    add_test(
        NAME navigation_network_test
        COMMAND navigation_network_test
    )

    add_executable(pedestrian_system_test
        src/pedestrian_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/navigation_network.cpp
        src/pedestrian_system.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )
    add_test(
        NAME pedestrian_system_test
        COMMAND pedestrian_system_test
    )

    add_executable(land_system_test
        src/land_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/land_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    # Keep this target separate from an interrupted legacy process that can
    # retain its former executable on Windows.
    set_target_properties(land_system_test PROPERTIES OUTPUT_NAME land_system_test_run)
    add_test(
        NAME land_system_test
        COMMAND land_system_test_run "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(save_manager_test
        src/save_manager_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/land_system.cpp
        src/mission_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/save_manager.cpp
        src/sidewalk_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    set_target_properties(save_manager_test PROPERTIES OUTPUT_NAME save_manager_test_run)
    add_test(
        NAME save_manager_test
        COMMAND save_manager_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(population_system_test
        src/population_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    set_target_properties(population_system_test PROPERTIES OUTPUT_NAME population_system_test_run)
    add_test(
        NAME population_system_test
        COMMAND population_system_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(power_system_test
        src/power_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mission_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    set_target_properties(power_system_test PROPERTIES OUTPUT_NAME power_system_test_run)
    add_test(
        NAME power_system_test
        COMMAND power_system_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(mission_system_test
        src/mission_system_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/land_system.cpp
        src/mission_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/simulation_clock.cpp
        src/vehicle_system.cpp
    )
    set_target_properties(mission_system_test PROPERTIES OUTPUT_NAME mission_system_test_run)
    add_test(
        NAME mission_system_test
        COMMAND mission_system_test "${CMAKE_SOURCE_DIR}/assets/definitions"
    )

    add_executable(ui_manager_test
        src/ui_manager_test.cpp
        src/ui_manager.cpp
    )
    target_link_libraries(ui_manager_test PRIVATE SDL3::SDL3)
    add_test(
        NAME ui_manager_test
        COMMAND ui_manager_test
    )
endif()

if(MSVC)
    target_compile_options(city_builder PRIVATE /W4 /permissive-)
    target_compile_options(ch_core PRIVATE /W4 /permissive-)
else()
    target_compile_options(city_builder PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(ch_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Keep the runtime asset path independent from the IDE's working directory.
add_custom_command(TARGET city_builder POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:SDL3::SDL3-shared>"
        "$<TARGET_FILE_DIR:city_builder>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CMAKE_SOURCE_DIR}/assets"
        "$<TARGET_FILE_DIR:city_builder>/assets"
)
