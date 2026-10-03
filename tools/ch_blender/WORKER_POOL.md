# CH Blender Worker Pool

`worker_pool.py` adds bounded parallel execution on top of the existing CH Blender agent worker. It does not replace `agent_worker.py`, the job contract, or the preflight/proxy/final quality gate.

## Contract

- pool contract: `CH_BLENDER_WORKER_POOL_V1`
- aggregate report: `CH_BLENDER_WORKER_POOL_REPORT_V1`
- job contract remains: `CH_BLENDER_AGENT_JOB_V1`
- per-job report remains: `CH_BLENDER_AGENT_REPORT_V1`

Every queued job is validated before any Blender process is started. The pool rejects duplicate `jobId` values and duplicate `outputDir` values so concurrent workers cannot overwrite one another.

## Default size

The default is **2 concurrent Blender workers**. This is intentionally conservative because Cycles/Blender jobs can consume substantial RAM and CPU.

Configuration order:

1. `--workers N`
2. `CH_BLENDER_POOL_SIZE`
3. default `2`

Allowed range: `1..8`.

## Usage

Run explicit jobs:

```bash
python tools/ch_blender/worker_pool.py \
  --job tools/ch_blender/jobs/asset.a.proxy.job.json \
  --job tools/ch_blender/jobs/asset.b.proxy.job.json \
  --workers 2
```

Run a queue file containing one repository-relative job path per line:

```bash
python tools/ch_blender/worker_pool.py \
  --jobs-file /tmp/ch_blender_jobs.txt \
  --workers 2
```

Run every active job in the default queue directory:

```bash
python tools/ch_blender/worker_pool.py
```

Reports are written by default to:

```text
out/ch_blender_agent/reports/<jobId>.report.json
out/ch_blender_agent/pool_report.json
```

The aggregate pool report preserves input ordering even though jobs finish out of order.

## Failure behavior

A render failure in one worker does **not** cancel sibling jobs. Every scheduled job is allowed to finish and write its own machine report. The pool exits non-zero if any job fails.

Quality rules remain unchanged:

```text
preflight -> SOUTH proxy -> human review -> final
```

Parallel execution never bypasses explicit proxy approval or source fingerprint checks.

## GitHub Actions

`.github/workflows/ch-blender-agent-worker.yml` now sends all selected changed jobs to the worker pool instead of executing them serially. Manual dispatch exposes `pool_size`; push-triggered runs default to 2 workers.

Keep the pool conservative on ordinary GitHub-hosted runners. Increasing worker count can improve throughput for lightweight preflight/proxy jobs, but final Cycles renders may become memory- or CPU-bound.
