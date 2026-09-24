# Large-asset pipeline

High-resolution City Horizon render class for landmarks and assets that lose readability when forced through the compact 256 path.

Use this pipeline for major attractions, tall/large buildings, skyline landmarks and assets with thin structural elements (spokes, trusses, railings, open steelwork) that visibly soften or disappear after compact downsampling.

Shared visual rules do not change: same `CH_CAMERA_V1`, same `CH_TYCOON_STUDIO_V1` lighting/camera contract, transparent RGBA, same four canonical directions and same human visual gate.

Two presets are provided:

- `studio_1024.json`: source 2048×2048 -> final 1024×1024. This is the default large-asset path.
- `studio_2048.json`: source 4096×4096 -> final 2048×2048. Use only for exceptionally large assets when 1024 is proven insufficient.

Do not create a 2048 asset just because the model can be rendered that large. First inspect the 1024 result in MapForge/runtime context. Large output carries real memory, disk, atlas and runtime costs.

Never upscale a 256 runtime sprite to enter this pipeline. Re-render from the original Blender/procedural source using the selected large preset.
