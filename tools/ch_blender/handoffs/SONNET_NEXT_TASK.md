# Handoff — Sonnet / CH Blender next task

You are taking over the next task for the City Horizon internal CH Blender tool.

## Working rules

- Work directly on `main`; do not create a branch.
- Read `tools/ch_blender/AGENTS.md` and `tools/ch_blender/ch_blender_manifest.json` first.
- Treat repository contracts as authoritative. Do not invent a parallel pipeline.
- Keep Blender frozen at `v4.2.3` unless the task explicitly requires otherwise.
- Do not modify Cycles/Eevee/render internals for this task.
- Do not bypass the quality gates.
- Avoid unrelated rebuilds/tests; only run what is needed for this task.

## Current state

The fail-fast path is implemented and validated:

`preflight -> proxy SOUTH -> human review -> final four-direction bake`

For `prop.raspadinha_vendor.01`:

- first preflight correctly rejected the scene with `CH_PREFLIGHT_DETACHED_BODY_PART`;
- the head-parenting bug was fixed;
- second preflight passed with zero violations;
- SOUTH proxy completed successfully at 256x256 using `BLENDER_EEVEE_NEXT`;
- the proxy has been visually reviewed and approved by the project owner.

Approved proxy SHA-256:

`f401bacf15fa67d09d54f9f7e651fb67119896808bb065330047bf0d85c7c1a7`

Relevant builder:

`tools/tycoon_photo_studio/build_raspadinha_vendor_guarded.py`

Relevant agent worker/gates:

- `tools/ch_blender/agent_worker.py`
- `tools/ch_blender/scene_gate.py`
- `tools/ch_blender/preflight_profiles/ch_asset_default_v1.json`
- `.github/workflows/ch-blender-agent-worker.yml`

## Your task

Execute the next allowed stage: the **final guarded four-direction bake** for `prop.raspadinha_vendor.01`, using the already-approved proxy as provenance.

1. Inspect the current guarded-job contract in `AGENTS.md` / `ch_blender_cli.py` rather than guessing fields.
2. Create a unique final job under `tools/ch_blender/jobs/` using `qualityStage: "final"`.
3. Record explicit approval exactly through the supported job contract:
   - `proxyReviewed: true`
   - `approvedProxySha256: "f401bacf15fa67d09d54f9f7e651fb67119896808bb065330047bf0d85c7c1a7"`
4. Commit the job directly to `main` so the CH Blender Agent Worker executes it.
5. Let the existing worker/cache/pipeline perform the final bake; do not add a special-case workflow.
6. Verify the final gate actually validates the reviewed proxy provenance before allowing expensive render work.
7. If the final job fails, fix only the specific reported cause and rerun the same guarded path. Do not fall back to an unguarded Blender script.
8. On success, inspect the generated final artifact/report and confirm:
   - all four canonical directions exist (`SOUTH`, `EAST`, `WEST`, `NORTH`);
   - RGBA/transparency contract is preserved;
   - canonical camera/lights remain fixed while `AssetRoot` rotates;
   - postprocess/final packaging completed;
   - output hashes are recorded by the worker.
9. Do **not** automatically classify/promote the asset into runtime/Map Forge catalogs. Final artistic/runtime promotion remains a separate owner-approved step.

## Important intent

This task is also the first end-to-end validation of Stage 3 of the new CH Blender fail-fast system. Prefer fixing the reusable tool contract if a generic final-stage issue is exposed; avoid asset-specific hacks unless the problem truly belongs to this asset.

When finished, leave a short machine-friendly summary in the commit message or a small report file stating the final job id, workflow run id, final status, and artifact name/hash.