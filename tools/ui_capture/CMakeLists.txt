cmake_minimum_required(VERSION 3.24)

project(city_builder_ui_capture LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CITY_HORIZON_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")
# UI capture only needs the production UI/runtime code. Visitor Forge preview
# packaging is unrelated and can fail when the root project is configured as a
# subdirectory because CMAKE_SOURCE_DIR points at tools/ui_capture.
set(CH_VISITOR_FORGE_PREVIEW OFF CACHE BOOL "Disable Visitor Forge packaging for UI capture" FORCE)
add_subdirectory("${CITY_HORIZON_ROOT}" "${CMAKE_BINARY_DIR}/city-horizon-root")

function(add_city_horizon_ui_capture target_name source_name)
    add_executable(${target_name}
        "${CITY_HORIZON_ROOT}/src/${source_name}"
        "${CITY_HORIZON_ROOT}/src/ui_manager.cpp"
        "${CITY_HORIZON_ROOT}/src/fence_system.cpp"
        "${CITY_HORIZON_ROOT}/src/fence_placement_controller.cpp"
        "${CMAKE_CURRENT_LIST_DIR}/weather_ui_capture_stub.cpp"
    )
    target_include_directories(${target_name} PRIVATE "${CITY_HORIZON_ROOT}")
    target_link_libraries(${target_name} PRIVATE ch_core SDL3::SDL3)

    if(MSVC)
        target_compile_options(${target_name} PRIVATE /W4 /permissive-)
    else()
        target_compile_options(${target_name} PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_custom_command(TARGET ${target_name} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:SDL3::SDL3-shared>"
            "$<TARGET_FILE_DIR:${target_name}>"
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CITY_HORIZON_ROOT}/assets"
            "$<TARGET_FILE_DIR:${target_name}>/assets"
    )
endfunction()

add_city_horizon_ui_capture(city_builder_ui_capture ui_visual_capture.cpp)
add_city_horizon_ui_capture(city_builder_ui_modal_capture ui_modal_visual_capture.cpp)
