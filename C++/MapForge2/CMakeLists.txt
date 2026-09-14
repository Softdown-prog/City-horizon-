cmake_minimum_required(VERSION 3.24)

project(MapForge2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Widgets)

get_filename_component(CH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)

add_library(mapforge2_canonical STATIC
    ${CH_ROOT}/src/ch_core/projection.cpp
    ${CH_ROOT}/src/ch_core/map_document.cpp
)
target_include_directories(mapforge2_canonical PUBLIC ${CH_ROOT})

add_library(mapforge2_editor STATIC
    src/editor_document.cpp
    src/editor_history.cpp
    src/editor_canvas.cpp
    src/main_window.cpp
)
target_include_directories(mapforge2_editor PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CH_ROOT}
)
target_link_libraries(mapforge2_editor PUBLIC
    mapforge2_canonical
    Qt6::Widgets
)

add_executable(MapForge2 WIN32
    src/main.cpp
)
target_link_libraries(MapForge2 PRIVATE mapforge2_editor Qt6::Widgets)

if(MSVC)
    target_compile_options(mapforge2_canonical PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(mapforge2_editor PRIVATE /W4 /permissive- /utf-8)
    target_compile_options(MapForge2 PRIVATE /W4 /permissive- /utf-8)
else()
    target_compile_options(mapforge2_canonical PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapforge2_editor PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(MapForge2 PRIVATE -Wall -Wextra -Wpedantic)
endif()

install(TARGETS MapForge2 RUNTIME DESTINATION .)
