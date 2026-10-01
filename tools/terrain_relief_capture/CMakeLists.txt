cmake_minimum_required(VERSION 3.24)

project(city_horizon_terrain_relief_capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CITY_HORIZON_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")
set(CH_VISITOR_FORGE_PREVIEW OFF CACHE BOOL "Disable unrelated preview packaging for terrain proof" FORCE)
add_subdirectory("${CITY_HORIZON_ROOT}" "${CMAKE_BINARY_DIR}/city-horizon-root")

add_executable(terrain_relief_visual_proof
    "${CITY_HORIZON_ROOT}/src/terrain_relief_visual_proof.cpp"
)
target_include_directories(terrain_relief_visual_proof PRIVATE "${CITY_HORIZON_ROOT}")
target_link_libraries(terrain_relief_visual_proof PRIVATE ch_core ch_render SDL3::SDL3)

if(MSVC)
    target_compile_options(terrain_relief_visual_proof PRIVATE /W4 /permissive-)
else()
    target_compile_options(terrain_relief_visual_proof PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_custom_command(TARGET terrain_relief_visual_proof POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:SDL3::SDL3-shared>"
        "$<TARGET_FILE_DIR:terrain_relief_visual_proof>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CITY_HORIZON_ROOT}/assets"
        "$<TARGET_FILE_DIR:terrain_relief_visual_proof>/assets"
)
