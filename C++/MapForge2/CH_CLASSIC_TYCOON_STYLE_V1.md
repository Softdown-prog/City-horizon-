# CH_CLASSIC_TYCOON_STYLE_V1

Status: LOCKED FOR CAROUSEL PRODUCTION CANDIDATES

This guide defines the visual language for City Horizon animated props. It targets the readability and material discipline of classic late-1990s/early-2000s PC tycoon games without copying proprietary artwork.

## Camera and scale
- Use `CH_CAMERA_V1` only.
- Orthographic dimetric 2:1 ground, 45 degree yaw, 30 degree camera elevation.
- Author and review at actual gameplay scale first. Enlarged previews are diagnostic only.
- Silhouette must remain readable at 50% preview scale.

## Edges
- Structural dark edge: 1.0-1.5 px at game scale.
- Never use thick black cartoon outlines.
- Internal material seams: 0.5-1.0 px and lower contrast than silhouette edges.

## Three-tone material ramp
Every important material uses a controlled light/mid/shadow ramp.
- Light: +12% to +20% value from mid.
- Mid: base material.
- Shadow: -22% to -32% value from mid.
- Contact AO is separate and localized; it must not replace the material shadow tone.

## Shadow language
- Ground shadow: soft, neutral/cool dark, target alpha 18-32% near contact and softer at the edge.
- AO: only under canopy, platform lip, horse contact/pole junctions, and base/ground contact.
- No ambient dark wash over the whole asset.

## Materials
### Painted wood
Warm mid tone, darker end grain / recesses, narrow light lip. Grain is sparse and directional; never procedural noise over the whole surface.

### Painted metal
Clean three-tone ramp with narrow highlights and small dark contact seams. Avoid glossy PBR reflections.

### Canopy cloth
Broad soft value changes between panels, visible ribs, darker underside and hem. No plastic shine.

### Gold / ornament
Muted brass-gold, not neon yellow. Small bright highlight, warm mid, brown-gold shadow.

### Painted carousel horses
Readable anatomy first. Body uses a warm ivory or restrained color ramp; saddle and harness use stronger accent colors. Hooves, mane, tack and poles remain separable at gameplay scale.

## Saturation
- General surfaces should stay below roughly 72% HSV saturation.
- Small accents may exceed that limit, but never dominate the sprite.
- Main production palette: Heritage Red / Cream / Brass.
- Alternative palette: Slate Blue / Ivory / Brass.

## Production palettes

### Heritage Red / Cream / Brass
- Deep outline: `#3A332F`
- Heritage red shadow/mid/light: `#75332F` / `#A9433F` / `#C45A50`
- Cream shadow/mid/light: `#CBB788` / `#EAD9B2` / `#F5E7C6`
- Brass shadow/mid/light: `#8F6827` / `#C99839` / `#E3BD63`
- Wood shadow/mid/light: `#70472F` / `#9B6A3F` / `#B98250`

### Slate Blue / Ivory / Brass
- Deep outline: `#33383C`
- Blue shadow/mid/light: `#355463` / `#4D7187` / `#698DA1`
- Ivory shadow/mid/light: `#C8BA98` / `#E7DCC1` / `#F3E9D3`
- Brass shadow/mid/light: `#8F6827` / `#C99839` / `#E3BD63`

## Approval examples by material
The official carousel candidate library is the first reference specimen:
- painted wood: `base.png.b64` / `platform.png.b64`
- painted metal / pole: `center_pole.png.b64`
- canopy cloth: `canopy.png.b64`
- brass ornament: `finial.png.b64` / `rosette.png.b64`
- painted horse: `horse_e/s/w/n.png.b64`

## Rejection rules
Reject an asset if it reads like a flat icon, vector mascot, clip-art, low-poly render, thick-outline cartoon, or untextured shape at gameplay scale.
A build or export success is never a visual approval.
