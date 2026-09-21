# CH Blender — Agent Interface

This directory is designed primarily for AI/code agents operating City Horizon through the repository and GitHub Actions. Interactive Blender UI is not required for normal automated production.

## Authority

Agents must read `tools/ch_blender/ch_blender_manifest.json` before changing Blender integration. The repository contracts remain authoritative; do not encode a second copy of camera, studio, style, bake, footprint or direction rules inside an agent prompt.

Frozen base: Blender `v4.2.3`.

## Stable CLI

Use:

```bash
python tools/ch_blender/ch_blender_cli.py print-contract
python tools/ch_blender/ch_blender_cli.py doctor
python tools/ch_blender/ch_blender_cli.py run-job --job tools/ch_blender/jobs/<id>.job.json --report out/ch_blender_agent/reports/<id>.report.json
```

The CLI emits JSON. Treat JSON status and process exit code as the machine contract. Do not scrape prose from Blender logs to decide whether the operation succeeded.

Binary resolution order:

1. `--blender <path>`
2. `CH_BLENDER_EXE`
3. `BLENDER_EXE`
4. `blender` from `PATH`

The executable must identify as Blender 4.2.3 while the manifest remains pinned to `v4.2.3`.

## Job contract

Every job uses `CH_BLENDER_AGENT_JOB_V1` and has a unique `jobId`.

### Canonical source bake

```json
{
  "contract": "CH_BLENDER_AGENT_JOB_V1",
  "jobId": "building.example.001",
  "operation": "canonical_bake",
  "assetConfig": "tools/tycoon_photo_studio/assets/example.source.json",
  "studioPreset": "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json",
  "outputDir": "out/ch_blender_agent/building.example.001",
  "postprocess": true
}
```

This delegates scene/render work to canonical `build_scene.py` and final packaging to canonical `postprocess.py`.

### Repository Blender script

```json
{
  "contract": "CH_BLENDER_AGENT_JOB_V1",
  "jobId": "prop.example.001",
  "operation": "blender_script",
  "script": "tools/tycoon_photo_studio/build_example_blender.py",
  "args": ["--output", "out/ch_blender_agent/prop.example.001/source"],
  "expectedOutputs": ["out/ch_blender_agent/prop.example.001/source/studio_metadata.json"],
  "outputDir": "out/ch_blender_agent/prop.example.001"
}
```

`args` is an ordered string array. This avoids shell interpolation ambiguity and makes the job diff easy for another agent to audit.

## GitHub queue convention

For repository-driven execution, create a unique file:

```text
tools/ch_blender/jobs/<unique-job-id>.job.json
```

A push of `*.job.json` triggers `.github/workflows/ch-blender-agent-worker.yml`. The workflow executes changed jobs and uploads `out/ch_blender_agent` as a review artifact.

Do not reuse one global `active.job.json`: multiple ChatGPT/Claude/other agent sessions may be working concurrently. Unique immutable-ish job files reduce collisions and preserve provenance.

After an asset is approved, jobs may be retained for provenance or removed in a later housekeeping commit. Generated `out/` data is not committed by this contract.

## Shared Blender cache

GitHub workflows should use:

```yaml
- uses: ./.github/actions/setup-ch-blender
```

The action reads the pinned version from `ch_blender_manifest.json`, restores the repository-wide binary cache, downloads Blender only on cache miss, validates the version, and exports both `CH_BLENDER_EXE` and `BLENDER_EXE`.

Cache identity changes only when:

- `upstream.tag` changes; or
- `cache.revision` changes intentionally.

Do not add independent Blender download/cache blocks to new workflows.

## Determinism rules

- use repository-relative paths;
- keep all job inputs inside the checked-out repository;
- use the frozen studio preset unless the task explicitly changes the studio contract;
- do not silently move camera or lights per direction;
- do not auto-promote art because CI is green;
- record output hashes from the worker report;
- use unique job IDs for concurrent agent sessions;
- keep official 4.2.3 available as the baseline until the internal CH Blender build passes equivalence gates;
- do not change Cycles/render internals merely to solve an asset-specific art problem.

## Exit codes

The CLI exposes the exact map through `print-contract`. Stable categories include invalid job/contract, Blender missing/version mismatch, Blender execution failure, postprocess failure and expected-output failure.

An agent should stop on a non-zero code, inspect the JSON `error.code`, make one targeted correction, and rerun the same job contract rather than improvising a parallel pipeline.
