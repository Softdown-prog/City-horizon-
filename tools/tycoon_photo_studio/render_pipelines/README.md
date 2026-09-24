# City Horizon render pipelines

This folder separates output resolution classes without forking the art direction.

- `compact_256/` — default 1024 source -> 256 final.
- `large_asset/` — large/landmark output: 2048 source -> 1024 final by default, with an exceptional 4096 source -> 2048 final preset.
- `ch_render_pipelines_v1.json` — machine-readable selection registry.

All presets intentionally keep `id: CH_TYCOON_STUDIO_V1` so they remain compatible with the frozen baker. The `renderClass` field identifies the selected output class while camera, lighting, style and direction contracts remain shared.

Do not duplicate geometry or recipes between pipelines. Choose a different preset and re-render the same canonical source.

See `docs/RENDER_OUTPUT_CLASSES.md` for selection rules.
