# AGENTS.md — CH Math Worker

This folder owns `CH_MATH_WORKER_V1`.

For supported mathematical work, use `worker.py` rather than duplicating formulas in agent reasoning or creating throwaway scripts. The worker must derive canonical constants from the repository and must not become a second source of truth.

Safe scope: camera/grid projection, screen/tile conversion, Bezier sampling, procedural-road mesh math, reusable interpolation and other deterministic geometry operations.

Do not put asset generation, visual approval, gameplay policy, mutable simulation state, networking, Blender orchestration or unrelated automation in this worker.

New operations require:
1. deterministic inputs/outputs;
2. finite-number validation;
3. a reusable City Horizon use case;
4. a self-test or existing self-test extension;
5. documentation in `contract.json` and this folder's README.
