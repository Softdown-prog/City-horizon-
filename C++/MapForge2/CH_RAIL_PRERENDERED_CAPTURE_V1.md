# CH MapForge rail sprite parity (incremental)

MapForge's `MapForge2MapCapture` now supports the same pre-rendered PNG art source style as City Horizon's runtime train adapters, using `capture.railSprites` in an existing `MAPFORGE_CAPTURE_REQUEST_V1` JSON.

Example additional property under `capture`:

```json
"railSprites": [
  {
    "path": "../../../../assets/rail/prerendered_v1/straight_south.png",
    "world": [2.0, 3.0],
    "anchorPixels": [256.0, 380.0],
    "scale": 1.0,
    "elevationWorld": 0.0
  }
]
```

The `path` is resolved relative to the capture request directory; use the approved runtime asset manifest as authority for the sprite anchor and scale. `world` is a world-space position (not an image pixel or guessed tile origin). The CH_CAMERA_V1 projection and configured rotation/zoom are shared with MapForge. Sprites are depth-sorted by world x+y. A missing or invalid PNG fails the render. No procedural track substitution is made.

**Limitations:** This is *still-image capture support*, not an integrated game-playback video renderer. The approved 18-piece `assets/rail/prerendered_v1` catalog is not fully promoted. A genuine train-on-real-track MP4 must (1) place assets against the same route used by the native rail runtime, (2) validate every track-to-wheel/port junction and its anchors across curves, and (3) render frames/encode after the approved PNGs are present. Do not label a schematic rail line or an unsupported stretched tile as validated real pre-rendered track.
