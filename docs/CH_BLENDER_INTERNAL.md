# CH Blender — Internal City Horizon Build

## Purpose

City Horizon uses an internal, project-specific Blender build derived from the official Blender 4.2.3 LTS source. Its purpose is to make asset authoring deterministic and aligned with the existing City Horizon asset pipeline.

This is an internal development tool only. It is not an official Blender Foundation LTS release and must not be represented as one.

## Frozen upstream base

- upstream project: Blender
- upstream source: https://projects.blender.org/blender/blender.git
- upstream tag: `v4.2.3`
- internal product name: `CH Blender 4.2.3`
- role: offline asset authoring/rendering for City Horizon
- runtime: City Horizon remains a 2D PNG/SDL3 game

The existing GitHub Actions production pipeline remains pinned to the official Blender 4.2.3 binary until an internal build passes equivalence review.

## License / distribution rule

The internal fork is based on GPL-licensed Blender source and is intended only for private/internal use by the City Horizon project.

Do not redistribute an internal CH Blender binary outside the project without first reviewing and satisfying the applicable GPL source-distribution obligations and bundled third-party licenses.

Generated City Horizon artwork and PNG outputs remain project assets; using Blender to create them does not make the artwork part of Blender's GPL source code.

## Design rule

Do not fork Blender merely to duplicate settings already expressed by City Horizon's repository contracts.

Keep project-specific artistic settings data-driven whenever possible:

- `CH_CAMERA_V1`
- `CH_TYCOON_STUDIO_V1`
- `CH_STYLIZED_PRERENDER_V1`
- four canonical directions: SOUTH / EAST / WEST / NORTH
- transparent RGBA output
- existing `build_scene.py` and `postprocess.py` production path

The internal Blender build is the host/tool. The repository remains the authority for City Horizon visual contracts.

## Modification layers

### Layer 0 — baseline

Official Blender 4.2.3 LTS, unmodified. This remains the visual reference used for A/B comparison.

### Layer 1 — startup and project integration

Prefer Python/configuration/add-on changes for:

- City Horizon workspace/panel;
- loading the canonical studio preset;
- creating/validating `ASSET_ROOT`;
- locking or restoring the canonical camera and lights;
- four-direction render commands;
- export/review commands;
- validation warnings for non-canonical settings.

### Layer 2 — small source patches

Use C/C++ source patches only when the behavior cannot be implemented robustly through Blender's Python API or repository-side tooling.

Good candidates include:

- internal product branding/version suffix;
- startup defaults that must be enforced before Python tooling loads;
- narrow UI/workflow restrictions;
- deterministic hooks required by the asset studio.

Each source patch must be small, documented, reversible and stored separately from upstream source.

### Layer 3 — renderer changes

Do not modify Cycles, color-management math, shading math, sampling algorithms or Blender's rendering internals without a concrete visual defect that cannot be solved in Layer 1 or Layer 2.

Renderer patches create the highest maintenance and equivalence risk.

## Source layout

Do not vendor the full Blender source tree into the City Horizon repository.

Use:

```text
tools/ch_blender/
  ch_blender_manifest.json
  bootstrap_windows.ps1
  patches/
  scripts/
```

The bootstrap script clones/checks out the frozen upstream tag into an external local working directory. Project-owned patches and integration scripts stay versioned in City Horizon.

## Equivalence gate

Before CH Blender replaces the official binary anywhere in production:

1. render the same accepted `.blend`/asset source with official Blender 4.2.3;
2. render it with CH Blender;
3. compare camera, framing, alpha, shadows, color transform, direction rotation and output dimensions;
4. require no unexplained visual divergence;
5. keep the official Blender path available as fallback.

A successful build is not artistic approval.

## Initial scope

The first CH Blender milestone is intentionally small:

- reproducible checkout of Blender `v4.2.3`;
- private/internal build workspace;
- no renderer modifications;
- no replacement of GitHub Actions production Blender yet;
- establish patch and integration structure;
- then add the City Horizon authoring UI/workspace as a separate step.
