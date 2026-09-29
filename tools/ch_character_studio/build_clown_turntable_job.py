#!/usr/bin/env python3
"""Create the guarded CH Blender job for the clown four-direction turntable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from character_studio import REPO_ROOT, validate_spec

JOB_CONTRACT = "CH_BLENDER_AGENT_JOB_V1"
SCRIPT = "tools/ch_character_studio/blender_clown_turntable.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=Path("tools/ch_character_studio/specs/clown_01.character.json"))
    parser.add_argument("--out-job", type=Path, default=Path("out/ch_character_studio/clown_01/jobs/turntable_proxy.job.json"))
    parser.add_argument("--stage", choices=("preflight", "proxy"), default="proxy")
    args = parser.parse_args()

    spec_path = args.spec if args.spec.is_absolute() else (REPO_ROOT / args.spec).resolve()
    spec = validate_spec(spec_path)
    if spec.get("characterId") != "clown_01":
        raise RuntimeError("turntable job currently expects clown_01")

    output_dir = "out/ch_character_studio/clown_01/turntable_proxy"
    spec_rel = spec_path.relative_to(REPO_ROOT).as_posix()
    job = {
        "contract": JOB_CONTRACT,
        "jobId": f"character.clown_01.turntable.{args.stage}.001",
        "operation": "guarded_blender_script",
        "script": SCRIPT,
        "qualityStage": args.stage,
        "args": [
            "--character-spec", spec_rel,
            "--output", output_dir,
            "--stage", args.stage
        ],
        "outputDir": output_dir,
        "expectedOutputs": [
            f"{output_dir}/s/underlay.png",
            f"{output_dir}/e/underlay.png",
            f"{output_dir}/n/underlay.png",
            f"{output_dir}/w/underlay.png",
            f"{output_dir}/s/underlay.json",
            f"{output_dir}/e/underlay.json",
            f"{output_dir}/n/underlay.json",
            f"{output_dir}/w/underlay.json",
            f"{output_dir}/turntable_report.json"
        ],
        "metadata": {
            "purpose": "cross_direction_identity_lock",
            "geometryAuthority": "CH_Blender_single_proxy",
            "paintAuthority": "CH_Character_Studio",
            "runtimeExportAllowed": False,
            "requiresHumanVisualReview": True
        }
    }

    out_path = args.out_job if args.out_job.is_absolute() else (REPO_ROOT / args.out_job).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(job, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
