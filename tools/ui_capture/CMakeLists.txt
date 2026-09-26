cmake_minimum_required(VERSION 3.24)

project(city_builder_ui_capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CITY_HORIZON_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")
add_subdirectory("${CITY_HORIZON_ROOT}" "${CMAKE_BINARY_DIR}/city-horizon-root")

add_executable(city_builder_ui_capture
    "${CITY_HORIZON_ROOT}/src/ui_visual_capture.cpp"
    "${CITY_HORIZON_ROOT}/src/ui_manager.cpp"
    "${CITY_HORIZON_ROOT}/src/fence_system.cpp"
    "${CITY_HORIZON_ROOT}/src/fence_placement_controller.cpp"
)
target_include_directories(city_builder_ui_capture PRIVATE "${CITY_HORIZON_ROOT}")
target_link_libraries(city_builder_ui_capture PRIVATE ch_core SDL3::SDL3)

if(MSVC)
    target_compile_options(city_builder_ui_capture PRIVATE /W4 /permissive-)
else()
    target_compile_options(city_builder_ui_capture PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_custom_command(TARGET city_builder_ui_capture POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:SDL3::SDL3-shared>"
        "$<TARGET_FILE_DIR:city_builder_ui_capture>"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "${CITY_HORIZON_ROOT}/assets"
        "$<TARGET_FILE_DIR:city_builder_ui_capture>/assets"
)
