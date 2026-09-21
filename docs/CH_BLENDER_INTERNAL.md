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

## Agent-first operating model

CH Blender is optimized for repository and CI agents first, not for interactive human UI.

The stable machine interface is:

- manifest: `tools/ch_blender/ch_blender_manifest.json`
- CLI: `tools/ch_blender/ch_blender_cli.py`
- deterministic worker: `tools/ch_blender/agent_worker.py`
- agent rules: `tools/ch_blender/AGENTS.md`
- shared GitHub setup/cache: `.github/actions/setup-ch-blender/action.yml`
- generic queue worker: `.github/workflows/ch-blender-agent-worker.yml`
- queued jobs: `tools/ch_blender/jobs/*.job.json`

Agents should communicate with CH Blender through versioned JSON jobs and JSON reports. Prompts are not part of the execution contract.

Each agent session should use a unique `jobId` and unique job file. This lets multiple ChatGPT, Claude or other agent sessions operate concurrently without sharing mutable prompt state or overwriting a global queue file.

The worker records the Blender identity plus SHA-256 hashes for job inputs and produced files so another agent can audit or reproduce the same operation.

## GitHub cache policy

All new Blender-based workflows must use the repository-local `setup-ch-blender` action instead of implementing their own Blender download/cache block.

The shared action derives its cache identity from:

- the pinned upstream Blender version in the manifest; and
- `cache.revision`.

Therefore the 4.2.3 binary is downloaded only on a cache miss. Changing an asset, worker, Blender script or job does not invalidate the Blender binary cache. A Blender version change or an intentional cache-revision change does.

The action exports `CH_BLENDER_EXE` and `BLENDER_EXE`, giving both agents and legacy scripts one predictable executable contract.

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
- validation warnings for non-canonical settings;
- deterministic agent commands and machine-readable reports.

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
  ch_blender_cli.py
  agent_worker.py
  AGENTS.md
  bootstrap_windows.ps1
  jobs/
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
- agent-first CLI and deterministic JSON worker;
- shared repository-wide GitHub binary cache;
- no renderer modifications;
- no replacement of the official render baseline by a modified CH Blender binary yet;
- establish patch and integration structure;
- then add source-level internal branding/defaults only where they provide concrete value.
