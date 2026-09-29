# CH Math Worker

`CH_MATH_WORKER_V1` is a deterministic, dependency-free calculation worker for City Horizon agents and project tools.

Its purpose is to move repetitive geometry/projection calculations out of chat reasoning and ad-hoc scripts while keeping every result pinned to the project's canonical contracts. It is **not** a game runtime dependency and it does not replace C++ authority.

## Authority

On every invocation the worker reads `src/ch_core/contracts.h`. It fails closed if the expected `CH_GRID_V1` / `CH_CAMERA_V1` contracts are not present. The formulas mirror `src/ch_core/projection.*` and the procedural road definitions in `src/road_system.*`.

Do not copy camera/tile constants into jobs. Let the worker resolve them from the repository.

## Operations

- `canonical` — current grid/camera/road constants
- `project_world` — batch `(x,y,z)` world to screen projection
- `screen_to_tile` — screen point to logical ground tile
- `bezier_cubic` — cubic Bezier positions, tangents and sampled arc length
- `road_ribbon` — procedural-road ribbon vertices, UVs and triangle indices
- `terrain_bilinear` — bilinear terrain-height sampling

## Usage

Run the dependency-free self-test:

```bash
python tools/ch_math_worker/worker.py --self-test
```

Run a JSON job:

```bash
python tools/ch_math_worker/worker.py tools/ch_math_worker/jobs/procedural_road_probe.job.json
```

Write the deterministic report to a repository path:

```bash
python tools/ch_math_worker/worker.py tools/ch_math_worker/jobs/procedural_road_probe.job.json \
  --output outputs/math/procedural_road_probe.report.json
```

Jobs use `CH_MATH_JOB_V1`; reports use `CH_MATH_REPORT_V1`.

## Agent rule

When an agent needs a supported projection, Bezier, procedural-road, or terrain interpolation calculation, prefer this worker instead of re-deriving the formula in prose or introducing a one-off script. If a required calculation is not supported, extend this worker only when the operation is reusable and belongs to the City Horizon mathematical contract.

The worker must remain:

- deterministic;
- standard-library-only unless a future contract explicitly changes this;
- network-free;
- read-only with respect to gameplay state;
- centered on canonical repository contracts;
- small enough to self-test quickly.

Visual approval and gameplay decisions remain human/runtime responsibilities.
