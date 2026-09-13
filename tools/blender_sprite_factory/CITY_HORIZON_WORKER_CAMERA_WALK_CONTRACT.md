# City Horizon worker: camera and walk contract

This is a Blender-production contract only. It does not alter the SDL3 camera,
`world_to_screen`, road geometry, or NavigationNetwork.

## Camera

- Orthographic projection
- 2:1 isometric projection
- 45 degrees around the vertical axis
- 35.264 degrees of elevation
- Locked source vector from subject target: `(6, -6, 6)`

## Owned walk v1

Four poses, one 32-frame source cycle:

1. Frame 25: left-foot contact
2. Frame 1: passing
3. Frame 9: right-foot contact
4. Frame 17: passing

The source scene has a small hip bob and opposing arm swing. It is a new,
isolated authored action; it is not a replacement for `CANONICAL_WALK` until
its rendered movement passes visual review.
