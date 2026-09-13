# City Horizon assets

`assets/` is the canonical source asset directory. The build copies this directory to
`build/assets/` after a successful build; do not author or update game assets only in
the build output.

Building progressions use the existing `*_lvl1.png` through `*_lvl5.png` files when a
definition supports five visual phases. Keep all phases together when replacing or
adding a building family.

Before accepting a new building export, run:

```powershell
python tools/clean_building_export_guides.py --validate
```

The command enforces [`buildings/export_contract.json`](buildings/export_contract.json):
RGBA output only, no high-saturation near-transparent matte residue, and no long thin
debug guide touching the bottom of a sprite. A violation exits with a nonzero status.
Use `--write` only to sanitize a known bad local export, then validate again.

For a declared single-tile source render (never for arbitrary buildings or
foliage), the same tool also supports stricter, opt-in geometry checks. For
example, the prepared-soil tile has a fixed lower content boundary and must
not retain labels or layout rulers below it:

```powershell
python tools/clean_building_export_guides.py --file assets/farming/prepared_soil/prepared_soil_01.png --max-content-y 916 --validate
```

`--keep-largest-component` and `--clip-largest-component-bounds` are likewise
single-tile-only checks; use them only when a contract explicitly guarantees
that detached visual components are invalid.

Ground tiles use a separate zero-tolerance geometric contract. It compares
the canvas and the renderer-critical alpha bounds against the current
canonical grass, prepared-soil and coast tile families:

```powershell
python tools/validate_ground_tiles.py --all --debug
```

Any one-pixel drift is reported as `[GROUND TILE REJECTED]` with the exact
canvas, bounds or content-row reason, and causes a nonzero exit status.
