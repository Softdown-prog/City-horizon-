# CH_PROCEDURAL_ROAD_CONSTRUCTION_V1

## Purpose

`CH_PROCEDURAL_ROAD_CONSTRUCTION_V1` defines the canonical construction presets used when a procedural road segment is authored as Local, Collector or Arterial.

It is the construction-side companion to `CH_PROCEDURAL_ROAD_CLASS_V1`. Traffic continues to consume road-class metadata; geometry/cost defaults are centralized here so MapForge, runtime placement and future tools do not invent independent widths, lane counts or costs.

The legacy tile `RoadManager` remains the gameplay authority while the procedural road migration is incomplete.

## Runtime source

The implementation lives in:

- `src/procedural_road_construction.h`

`ProceduralRoadConstructionBuilder::add_segment(...)` creates a `ProceduralRoadGraph` segment and assigns its class in `ProceduralRoadClassCatalog` as one operation.

If class assignment fails after graph insertion, the newly created segment is removed again. This keeps graph topology and class metadata synchronized.

`unspecified` is a compatibility state for older/manual routes and is not accepted as an authored construction class.

## Canonical presets

| Road class | Width | Lanes | Subdivisions | Texture repeat | Build cost / world unit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Local | 0.72 | 2 | 24 | 1.0 | 100 |
| Collector | 0.94 | 2 | 32 | 1.0 | 160 |
| Arterial | 1.32 | 4 | 40 | 1.0 | 260 |

These are V1 gameplay/geometry defaults rather than final visual-art approval. They can be tuned through this one profile table without changing traffic code.

## Cost estimate

`ProceduralRoadConstructionBuilder::estimated_build_cost(...)` uses 3D endpoint distance and the selected class's cost per world unit:

`ceil(length_xyz * build_cost_per_world_unit)`

The final production placement system may later use spline arc length instead of endpoint distance. V1 intentionally keeps the deterministic construction estimate small and testable while the placement bridge is being proven.

## MapForge pilot

`C++/MapForge2/src/procedural_road_preview_main.cpp` now creates its demonstration network through the canonical construction builder.

Interactive keys:

- `5` — Local
- `6` — Collector
- `7` — Arterial

Changing class updates the profile-controlled width/subdivision settings and the generated graph segments receive the profile lane count and road-class catalog entry.

The overlay displays the active class, width, lane count and build cost per world unit.

This proves the editor-side class selection path, but it is not yet the production City Horizon road-placement UI.

## Current runtime boundary

The production runtime road tool in `src/main_runtime_impl.cpp` still builds the legacy tile road through `RoadManager::line_between(...)` and `RoadManager::place_segment(...)`.

It does not yet create persistent `ProceduralRoadGraph` segments when the player drags a road.

This is intentional during migration. The next runtime bridge should mirror a valid player road placement into procedural nodes/segments while keeping `RoadManager` authoritative until procedural rendering, traffic, persistence and load/save have all passed their gates.

Do not claim that Local/Collector/Arterial are already player-selectable production roads until that bridge and UI selection are actually integrated.

## Validation

Focused construction test:

- `src/procedural_road_construction_test.cpp`

It covers:

- Local/Collector/Arterial width, lane count and subdivisions;
- class catalog assignment;
- deterministic class-specific build-cost estimation;
- 3D distance handling;
- rejection/rollback of `unspecified` authored roads.

GitHub Actions run `36622907856` (`CH Procedural Road Priority Check`) completed successfully. Its C++20 compile and execution steps passed for priority traffic, road classes and the road construction gate.

The MapForge proof workflow run `36623134717` did not execute a job (`jobs: []`). Therefore it is not evidence of a MapForge compile failure or visual failure, but it also provides no visual proof. A gameplay-scale PNG must still be generated and inspected before the class-aware MapForge presentation is considered visually validated.

## Authority and compatibility

- `RoadManager` remains legacy gameplay/save authority.
- `ProceduralRoadGraph` remains the continuous road topology under validation.
- `ProceduralRoadClassCatalog` owns stable class metadata by segment ID.
- `ProceduralRoadConstructionBuilder` owns construction geometry/cost defaults.
- traffic speed/right-of-way derives from the class contract and must not duplicate construction profile constants.

## Next migration gate

The next production-facing step is a procedural road placement bridge that can take an accepted player road drag and construct/reuse graph nodes plus classified procedural segments in parallel with the legacy tile placement.

That bridge must be deterministic, avoid duplicate coincident nodes, preserve explicit-junction semantics, and remain removable/rebuildable from legacy data until save/load for procedural roads becomes authoritative.
