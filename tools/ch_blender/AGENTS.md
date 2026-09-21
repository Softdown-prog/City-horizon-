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

## Mandatory fail-fast path for new agent-authored assets

New Blender authoring created by agents must use `guarded_blender_script`. The required sequence is:

```text
preflight
  -> proxy SOUTH
  -> human visual review
  -> final four-direction bake
```

Do not go directly from new geometry to a final Cycles bake.

### Stage 1 — preflight

`qualityStage: "preflight"` builds the scene but does not render the expensive final package. The Blender-side gate writes `CH_SCENE_PREFLIGHT_V1`.

Stable rejection codes include:

- `CH_PREFLIGHT_ASSET_ROOT`
- `CH_PREFLIGHT_CAMERA`
- `CH_PREFLIGHT_ALPHA`
- `CH_PREFLIGHT_EMPTY`
- `CH_PREFLIGHT_FOOTPRINT`
- `CH_PREFLIGHT_MISSING_BODY_PART`
- `CH_PREFLIGHT_BODY_LAYOUT`
- `CH_PREFLIGHT_DETACHED_BODY_PART`
- `CH_PREFLIGHT_GROUND_CONTACT`
- `CH_PREFLIGHT_CAMERA_CROP`

An agent must stop on failure and make one targeted correction.

### Stage 2 — SOUTH proxy

After preflight passes, run the same guarded builder with `qualityStage: "proxy"`.

The proxy is intentionally cheap: gameplay-sized, one direction, and uses the preflight profile's proxy renderer. It exists to judge silhouette, proportions, pose, composition and obvious occlusion before spending on four-direction final output.

The builder writes:

- `preflight_report.json`
- `proxy_south.png`
- `proxy_report.json` (`CH_PROXY_RENDER_V1`, including SHA-256)

A green proxy job is not artistic approval.

### Stage 3 — final

Final is rejected by the worker unless the job records explicit review:

```json
{
  "qualityStage": "final",
  "approval": {
    "proxyReviewed": true,
    "approvedProxySha256": "<sha256 from reviewed proxy_report.json>"
  }
}
```

This is provenance for the human review. It prevents an agent from accidentally paying the cost of a final bake immediately after authoring new geometry.

Default gate tuning is versioned in:

`tools/ch_blender/preflight_profiles/ch_asset_default_v1.json`

## Job contract

Every job uses `CH_BLENDER_AGENT_JOB_V1` and has a unique `jobId`.

### Guarded Blender script — preferred for new assets

```json
{
  "contract": "CH_BLENDER_AGENT_JOB_V1",
  "jobId": "prop.example.preflight.001",
  "operation": "guarded_blender_script",
  "script": "tools/tycoon_photo_studio/build_example_guarded.py",
  "qualityStage": "preflight",
  "args": [
    "--studio-preset",
    "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json",
    "--output",
    "out/ch_blender_agent/prop.example.001"
  ],
  "outputDir": "out/ch_blender_agent/prop.example.001"
}
```

The worker owns `--stage`, `--preflight-profile` and `--approval-proxy-sha`; do not place those switches manually in `args`.

### Canonical source bake

`canonical_bake` remains available for established canonical sources and compatibility. New agent-authored direct Blender geometry should prefer the guarded operation until the generic canonical baker itself is migrated to the same three-stage gate.

### Repository Blender script

`blender_script` remains available as an unguarded compatibility escape hatch for established automation. Do not use it to introduce a new visual asset and immediately final-render it.

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
- do not change Cycles/render internals merely to solve an asset-specific art problem;
- new agent-authored visual assets must not skip preflight and SOUTH proxy review.

## Exit codes

The CLI exposes the exact map through `print-contract`. Stable categories include invalid job/contract, Blender missing/version mismatch, quality-gate approval required, Blender execution failure, postprocess failure and expected-output failure.

An agent should stop on a non-zero code, inspect the JSON `error.code`, make one targeted correction, and rerun the same job contract rather than improvising a parallel pipeline.
