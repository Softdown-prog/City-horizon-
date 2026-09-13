# City Horizon Map Forge — Single-Authority C++20 + SDL3 Architecture

## 1. Architectural Contract & Authority

The core mathematical, geometrical, and visual authority of **City Horizon** and **City Horizon Map Forge** is strictly centralized in C++20 and SDL3. Python (PySide6) operates exclusively as a productivity client interface.

```
                         CITY HORIZON ARCHITECTURE
                         
                            ┌───────────────────┐
                            │  ch_core (C++20)  │
                            │  Zero SDL / UI    │
                            │  - Grid Math      │
                            │  - Projection     │
                            │  - Map Document   │
                            │  - Validation     │
                            └─────────┬─────────┘
                                      │
                                      ▼
                            ┌───────────────────┐
                            │ ch_render (C++20) │
                            │ - SDL3 Renderer   │
                            │ - Camera & Depth  │
                            │ - Asset Textures  │
                            │ - Geometry Sign.  │
                            └────┬─────────┬────┘
                                 │         │
                 ┌───────────────┘         └───────────────┐
                 ▼                                         ▼
   ┌───────────────────────────┐             ┌───────────────────────────┐
   │    city_builder (C++20)   │             │   Map Forge (Python)      │
   │ - Gameplay & Simulation   │             │ - PySide6 GUI Client      │
   │ - Domain Managers         │             │ - Native Viewport HWND    │
   │ - Audio & UI              │             │ - city_horizon_native     │
   └─────────────────────────--┘             └───────────────────────────┘
```

---

## 2. Dependency Audit & Scoping

- **`ch_core`**: Zero SDL3, zero UI. Pure C++20 mathematical grid coordinate projection, map parsing (`MapDocument`), and validation logic.
- **`ch_render`**: Depends on `ch_core` and `SDL3::SDL3`. Contains renderer routines (`MapRenderer`, `MapForgeNativeViewport`) and layout data structures (`building_system`, `road_system`, `sidewalk_system`, `farming_system`, `land_system`, `road_visual_catalog`). Decoupled from gameplay simulation (`economy_system`, `power_system`, `population_system`, `resource_system`, `vehicle_system`, `mission_system` are excluded).
- **`city_builder.exe`**: Links `ch_core`, `ch_render`, `SDL3`, `SDL3_mixer`, and all gameplay simulation modules.
- **`city_horizon_native` (pybind11 module)**: Links `ch_core` and `ch_render` directly. Exposes native math, validation, document parsing, viewport control, and geometry signature calculation to Python.

---

## 3. Projection & Camera Conventions (`CH_GRID_V1`)

- **Logical Tile Dimensions**: 128 × 64 pixels (diamond ratio 2:1).
- **Horizontal World Rotation**: 45°.
- **Canonical Isometric Inclination**: 35.264°.
- **Logical Coordinates**: Integer grid (`tile_x`, `tile_y`).
- **Physical Pixel Contract (`CH_VIEWPORT_PIXEL_V1`)**: Rendering and coordinate mapping use physical screen output pixels (`SDL_GetRenderOutputSize` / `devicePixelRatio()`) to guarantee DPI scaling immutability (100%, 125%, 150%).
