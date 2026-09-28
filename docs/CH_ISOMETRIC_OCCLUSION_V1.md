# CH_ISOMETRIC_OCCLUSION_V1

City Horizon uses a painter-style 2D isometric world renderer. This contract defines the canonical relationship between terrain, buildings, mobile actors and collision so that every system uses the same ground-plane interpretation.

## World layer order

1. Terrain / water
2. Roads, crosswalks and pedestrian floor
3. World entities (buildings and mobile actors) ordered by isometric ground depth
4. Presentation-only aerial/world FX
5. Weather
6. UI

Buildings and mobile actors are not rendered as two independent layers. The runtime world queue compares their ground depth so a pedestrian can disappear behind a building and reappear when reaching the camera-facing side.

## Depth rule

Depth is `camera_view_point(world).x + camera_view_point(world).y` after the active camera quarter-turn.

Mobile actors use their ground/contact anchor.

A pre-rendered building is a single sprite and therefore receives the depth of the front-most corner of its complete visual footprint. `building_depth_span(...)` records the full back/front interval, while `building_visual_ground_world(...)` resolves the canonical front corner. This rule applies to large footprints as well as 1x1 props and is invariant across SOUTH/WEST/NORTH/EAST camera rotations.

The compile-time guards in `src/ch_core/projection.h` exercise a 5x4 attraction in all four camera rotations so a later camera/depth refactor cannot silently move a large attraction to the wrong side of pedestrians.

## Pedestrian collision

Visual occlusion and collision are separate systems.

`PedestrianCollisionNavigationNetwork` removes every `BuildingManager` occupied tile from the pedestrian graph. Both endpoints of a pedestrian edge are validated against the current building occupancy before the edge is reported connected. Closed fence crossings are also rejected; a road remains vehicle-only except at an active crosswalk portal.

The pedestrian system revalidates the remaining route while walking. If a map edit invalidates it, it attempts one replan and otherwise stops instead of continuing through the obstruction.

## Large-asset limitation

A building currently remains one RGBA sprite. Therefore the renderer cannot interleave a pedestrian between two visual sub-parts of the same sprite. The front-footprint rule is intentionally conservative and correct for normal building/attraction silhouettes. Assets that someday require a person to pass through a visible opening inside one sprite (for example under a bridge or through an arch) must opt into explicit depth slices / occlusion masks rather than adding per-asset depth hacks.

Do not solve those cases by changing the global ground-depth formula or by hardcoding a building ID in the renderer.
