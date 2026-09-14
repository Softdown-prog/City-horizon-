# CH_STUDIO_ARCHITECTURE_V1

Status: FOUNDATION / NOT YET FROZEN

## Purpose

City Horizon Studio is the deterministic authoring and homologation environment for City Horizon. It is not a general-purpose game engine. It exists to let one developer plus software agents create, inspect, validate and eventually preview City Horizon content without encoding visual decisions directly in C++.

## Core rule

**C++ defines capabilities. Data combines those capabilities. Studio edits and validates the data.**

New content must not require new C++ when it can be represented using capabilities already registered by the engine.

Examples that should become data-driven: terrain choices, building definitions, footprints, anchors, rotations, access points, prices, capacities, visual IDs, animation IDs, scenario composition and UI layouts.

Examples that can legitimately require C++: a new simulation capability, a new renderer feature, a new navigation model, a new behavior family, or a new runtime system.

## Process boundaries

- Qt6 owns Studio desktop chrome, inspector panels, catalog lists, dialogs and editing input.
- Qt6 must not become a second game renderer or a second simulation implementation.
- `ch_core` remains the source of truth for world rules, placement and canonical state.
- `ch_render` remains the source of truth for final world presentation.
- Future `ch_ui` must render both game UI and Studio UI previews from the same runtime definitions.
- Play/preview should initially run the City Horizon runtime in a separate process so a game crash cannot destroy unsaved editor work.

## First content contract: CH_CONTENT_PACK_V1

A content pack is a deterministic set of definitions. The first implementation intentionally supports only generic identity and dependency metadata. Specialized contracts for buildings, actors, UI, roads and scenarios will layer on top later.

Every definition has:

- stable immutable `id`
- human-facing `displayName`
- `kind`
- optional engine `behaviorId`
- optional `visualId`
- optional `sourcePath`
- zero or more dependency IDs

Supported first-layer kinds:

- terrain
- road
- sidewalk
- building
- decoration
- actor
- vehicle
- ui_layout
- scenario

## ID invariant

Persistent IDs are structural references, not labels. A user-visible name may change freely; an ID must not be casually renamed after content ships or appears in scenarios.

Valid IDs use lowercase letters, digits, `.`, `_` and `-` only.

Example:

`building.cafe.small.01`

A future rename of a persistent ID must be an explicit migration operation with dependency analysis, never a normal inspector text edit.

## Validation invariant

Studio must validate data before integration. Initial `CH_CONTENT_PACK_V1` validation checks:

- contract version
- package ID format
- content ID format
- duplicate IDs
- unknown kinds
- self-dependencies
- malformed/duplicate dependencies
- catalog ID collisions
- unresolved dependencies across loaded packs

Specialized validators will later add footprint, anchor, rotation, asset existence, behavior registration, collision, road access, pedestrian access, animation and semantic gates.

## Homologation flow

The intended long-term flow is:

1. Open a known validation world in Studio.
2. Load or create a content pack, e.g. a Circus expansion.
3. Visually place and inspect the content against canonical City Horizon scale and systems.
4. Run deterministic validators.
5. Fix all structural errors in Studio.
6. Save the authoritative data definition.
7. Runtime consumes the same definitions directly whenever possible.

During migration, an agent may translate an already-homologated Studio document into older runtime structures, but the agent must not re-decide scale, IDs, footprint, orientation or access from screenshots.

## Compilation rule

Editing content should eventually require **zero engine recompilation**. Recompilation is reserved for new engine capabilities. Hot reload is therefore a planned architectural feature for content definitions, visual assets and UI layouts.

## Non-goals

City Horizon Studio will not become a Unity/Unreal replacement. Do not add generic 3D editing, arbitrary game genres, generic physics graphs, general scripting IDE features or unrelated engine systems unless City Horizon itself requires them.

## Current implementation

The first native layer introduces a Qt-independent `mapforge2_studio_core` with typed content definitions, catalog registration, stable-ID validation and dependency diagnostics. A Qt adapter loads `CH_CONTENT_PACK_V1` JSON and a Studio tab exposes validation results without enabling production scenario Save.
