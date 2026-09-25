# CH_PROCEDURAL_2D_PRIMITIVES_V1

Status: ACTIVE FOUNDATION

This document defines the semantic drawing vocabulary used by City Horizon's deterministic 2D procedural authoring tools. The goal is to let agents author clean game assets without repeatedly reconstructing low-level `QPainter` geometry.

The library lives in:

- `src/procedural_2d_primitives.h`
- `src/procedural_2d_primitives.cpp`

It is infrastructure, not a separate renderer. Building Composer, prop generators, decoration tools, vehicle/cart generators and future terrain/detail authoring may call the same primitives.

## Why this layer exists

Small or less-capable models often fail when one prompt implicitly requires all of these at once: projection, point ordering, winding, line weight, bevel logic, local shadow, material breakup and silhouette polish. The primitive layer gives those operations stable names and implementations.

Prefer a semantic primitive over raw `QPainter` calls whenever the requested shape matches one of the vocabulary items below. Raw painting remains available for genuinely new geometry.

## Geometry helpers

- `lerp` — stable interpolation between two screen-space points.
- `quadraticPoint` — sample a quadratic curve.
- `insetQuad` — create a smaller four-point panel inside a projected quad.
- `offsetQuad` — move a projected quad by a screen-space offset.
- `extrudedSide` — construct a side face from an edge and depth vector.

## Basic shape tools

- `polygon` — filled/stroked polygon with consistent cap/join configuration.
- `polyline` — open or closed linework.
- `roundedRect` — soft rectangular plaques, UI-like panels and simple body parts.
- `ellipse` / `circle` — lamps, bolts, finials, wheels, bushes and rounded ornaments.
- `capsule` — pipes, rails, posts, bumpers, handles and rounded bars.
- `star` — reusable multi-point ornament.

## Depth and architectural tools

- `beveledQuad` — projected panel with light/shadow bevel faces.
- `insetPanel` — framed recess such as a door panel, window insert, sign face or machine panel.
- `extrudedQuad` — shallow screen-space depth for counters, ledges, canopies, signs and trim.
- `contactShadow` — restrained layered contact shadow under a footprint or attached detail.

## Pattern and fabric tools

- `stripedQuad` — alternating stripes across a projected four-point surface.
- `quadraticRibbon` — curved filled strip for fabric, banners, decorative trims and soft fascia.
- `scallopedEdge` — repeated curved edge for awnings, valances and ornamental trim.

## Agent authoring guidance

When drawing a new object, work from large to small:

1. silhouette / primary volume;
2. projected faces;
3. major inset or extruded components;
4. material/pattern breakup;
5. restrained contact shadows;
6. ornaments and micro-details only if they survive gameplay scale.

Do not begin with texture noise. Do not solve depth by adding thick black outlines. Do not paint a separate rotation when the object can be represented structurally and projected into canonical views.

For building-like assets, logical parts belong to physical faces/edges and must rotate with the object. SOUTH/EAST/WEST/NORTH are outputs of one definition, not four unrelated illustrations.

## Likely next primitive families

The current foundation intentionally covers the highest-frequency operations first. Future additions should be demand-driven and reusable. Likely candidates include:

- segmented arch / masonry ring;
- roof-course and shingle/tile pattern helper;
- brick/stone course helper;
- projected cylinder / tapered post;
- wheel + axle helper for carts and small vehicles;
- fence/rail repetition helper;
- stair/step stack;
- foliage clump / crown silhouette helper;
- cable/rope spline;
- decal/label placement with projection-safe inset;
- deterministic wear/variation masks that never alter silhouette;
- 56 px NPC scale-reference overlay for architecture review.

Every new helper should remove repeated custom geometry from at least one real asset family before it is promoted into this shared vocabulary.
