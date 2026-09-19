"""Blender Bake Runner — generic TYCOON_ASSET_BAKE_V1 pipeline orchestrator.

Reads a contract JSON (e.g. tycoon_asset_bake_contract.json), drives Blender
headlessly through the four-direction bake, applies the canonical post-process
and validates the resulting package.  One deterministic invocation produces the
full game-asset package for any asset that conforms to the contract.

Usage
-----
    python tools/blender_bake_runner.py \\
        --contract C++/MapForge2/presets/tycoon_asset_bake_contract.json \\
        --scene    tools/tycoon_photo_studio/build_scene.py \\
        --blender  /path/to/blender \\
        --output-dir out/bake/park_kiosk_1x1

Dry-run (validates inputs without invoking Blender):
    python tools/blender_bake_runner.py --dry-run --contract ... --scene ...

The runner writes bake_run_report.json to the output directory with the result
of every pipeline stage.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIPELINE_STAGES = ("blender_bake", "postprocess", "validate", "runtime_placement_gate", "promote")
REQUIRED_CONTRACT_FIELDS = (
    "id",
    "renderer",
    "camera",
    "rotationPolicy",
    "postProcess",
    "pivot",
    "footprint",
    "outputs",
)
DIRECTION_ORDER = ("south", "east", "west", "north")
RUNNER_VERSION = "1.1.0"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Blender Bake Runner — TYCOON_ASSET_BAKE_V1 pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--contract",
        required=True,
        metavar="PATH",
        help="Path to the bake contract JSON (e.g. tycoon_asset_bake_contract.json)",
    )
    parser.add_argument(
        "--asset-config",
        required=True,
        metavar="PATH",
        help="Declarative TYCOON_ASSET_SOURCE_V1 JSON to bake.",
    )
    parser.add_argument(
        "--studio-preset",
        required=True,
        metavar="PATH",
        help="Frozen CH_TYCOON_STUDIO_V1 JSON used by every pipeline stage.",
    )
    parser.add_argument(
        "--scene",
        default=None,
        metavar="PATH",
        help=(
            "Path to the Blender Python scene script (default: tools/tycoon_photo_studio/build_scene.py "
            "relative to this script's parent directory)"
        ),
    )
    parser.add_argument(
        "--blender",
        default=None,
        metavar="EXE",
        help="Path to the Blender executable (default: $BLENDER_EXE env var or 'blender' on PATH)",
    )
    parser.add_argument(
        "--output-dir",
        default="out/bake",
        metavar="DIR",
        help="Output directory for all bake artefacts (default: out/bake)",
    )
    parser.add_argument(
        "--postprocess",
        default=None,
        metavar="PATH",
        help=(
            "Path to postprocess.py (default: tools/tycoon_photo_studio/postprocess.py "
            "relative to this script's parent directory)"
        ),
    )
    parser.add_argument(
        "--validate",
        default=None,
        metavar="PATH",
        help=(
            "Path to validate_package.py (default: tools/tycoon_photo_studio/validate_package.py "
            "relative to this script's parent directory)"
        ),
    )
    parser.add_argument(
        "--golden-fingerprint",
        default=None,
        metavar="PATH",
        help="Optional TYCOON_GOLDEN_FINGERPRINT_V1 used by the validation stage.",
    )
    parser.add_argument(
        "--golden-mean-abs-tolerance",
        type=float,
        default=6.0,
        help="Mean absolute-difference tolerance for --golden-fingerprint (default: 6.0).",
    )
    parser.add_argument(
        "--promote-asset-dir",
        default=None,
        metavar="DIR",
        help="Optional canonical asset directory, e.g. assets/buildings.",
    )
    parser.add_argument(
        "--promote-pack-out",
        default=None,
        metavar="PATH",
        help="Optional CH_CONTENT_PACK_V1 destination.",
    )
    parser.add_argument(
        "--promote-force",
        action="store_true",
        help="Allow promotion to replace an existing asset package.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print the pipeline plan without invoking Blender",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip the package validation stage (useful for local iteration)",
    )
    parser.add_argument(
        "--xvfb",
        action="store_true",
        help="Wrap Blender invocation with xvfb-run (Linux CI headless)",
    )
    parser.add_argument(
        "--blender-extra-args",
        nargs=argparse.REMAINDER,
        default=[],
        metavar="ARG",
        help="Extra arguments forwarded verbatim to Blender after '--'",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Contract loading and validation
# ---------------------------------------------------------------------------


def load_contract(path: Path) -> dict:
    """Load and perform structural validation of the bake contract."""
    if not path.is_file():
        raise FileNotFoundError(f"Contract not found: {path}")
    contract = json.loads(path.read_text(encoding="utf-8"))
    missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in contract]
    if missing:
        raise ValueError(f"Contract {path.name} is missing required fields: {missing}")

    # Camera contract checks
    camera = contract["camera"]
    if camera.get("contract") != "CH_CAMERA_V1":
        raise ValueError(
            f"Contract camera.contract must be 'CH_CAMERA_V1', got '{camera.get('contract')}'"
        )
    if camera.get("projection") != "orthographic_dimetric_2_to_1":
        raise ValueError(
            f"Contract camera.projection must be 'orthographic_dimetric_2_to_1', got '{camera.get('projection')}'"
        )

    # Rotation policy checks
    rotation = contract["rotationPolicy"]
    actual_order = tuple(rotation.get("directionOrder", []))
    if actual_order != DIRECTION_ORDER:
        raise ValueError(
            f"Contract rotationPolicy.directionOrder must be {DIRECTION_ORDER}, got {actual_order}"
        )
    if not rotation.get("assetRootRotates"):
        raise ValueError("Contract rotationPolicy.assetRootRotates must be true")
    if not rotation.get("lightsRemainWorldFixed"):
        raise ValueError("Contract rotationPolicy.lightsRemainWorldFixed must be true")

    # Pivot invariant
    pivot = contract["pivot"]
    if not pivot.get("mustBeIdenticalAcrossDirections"):
        raise ValueError("Contract pivot.mustBeIdenticalAcrossDirections must be true")

    return contract


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


def _tools_dir(args_value: str | None, relative_name: str) -> Path:
    """Return path to a pipeline tool, defaulting to sibling of this script."""
    if args_value:
        return Path(args_value)
    here = Path(__file__).parent
    candidate = here / relative_name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"Cannot locate '{relative_name}'. "
        f"Pass the path explicitly with the appropriate --flag."
    )


def resolve_blender(blender_arg: str | None) -> str:
    """Return the Blender executable path (string for subprocess)."""
    if blender_arg:
        return blender_arg
    env_val = os.environ.get("BLENDER_EXE", "")
    if env_val:
        return env_val
    found = shutil.which("blender")
    if found:
        return found
    raise FileNotFoundError(
        "Blender executable not found. "
        "Pass --blender /path/to/blender or set the BLENDER_EXE environment variable."
    )


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def run_blender_bake(
    blender_exe: str,
    scene_script: Path,
    asset_config: Path,
    studio_preset: Path,
    output_source_dir: Path,
    xvfb: bool,
    extra_args: list[str],
) -> dict:
    """Run Blender headlessly and produce the raw per-direction source renders."""
    output_source_dir.mkdir(parents=True, exist_ok=True)

    cmd = []
    if xvfb:
        cmd += ["xvfb-run", "-a"]
    cmd += [
        blender_exe,
        "--background",
        "--factory-startup",
        "--python",
        str(scene_script),
        "--",
        "--output",
        str(output_source_dir),
        "--asset-config",
        str(asset_config),
        "--studio-preset",
        str(studio_preset),
    ]
    if extra_args:
        cmd += extra_args

    print(f"\n[blender_bake] Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=False, text=True)
    elapsed = time.monotonic() - t0

    if result.returncode != 0:
        return {
            "stage": "blender_bake",
            "status": "failed",
            "returncode": result.returncode,
            "elapsed_s": round(elapsed, 2),
        }

    # Verify expected source outputs
    missing = []
    for direction in DIRECTION_ORDER:
        for suffix in ("color_source", "shadow_source"):
            fname = f"{_infer_asset_id(output_source_dir)}_{direction}_{suffix}.png"
            if not (output_source_dir / fname).is_file():
                missing.append(fname)
    if not (output_source_dir / "studio_metadata.json").is_file():
        missing.append("studio_metadata.json")

    return {
        "stage": "blender_bake",
        "status": "passed" if not missing else "failed",
        "returncode": result.returncode,
        "elapsed_s": round(elapsed, 2),
        "missing_files": missing,
    }


def _infer_asset_id(source_dir: Path) -> str:
    """Infer asset ID from studio_metadata.json if present, else fallback."""
    meta_path = source_dir / "studio_metadata.json"
    if meta_path.is_file():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8")).get(
                "sourceObject", "asset"
            )
        except Exception:
            pass
    return "asset"


def run_postprocess(
    postprocess_script: Path,
    source_dir: Path,
    final_dir: Path,
    studio_preset: Path,
) -> dict:
    """Apply the canonical post-process pipeline to the Blender source renders."""
    final_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(postprocess_script),
        "--input",
        str(source_dir),
        "--output",
        str(final_dir),
        "--studio-preset",
        str(studio_preset),
    ]

    print(f"\n[postprocess] Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=False, text=True)
    elapsed = time.monotonic() - t0

    return {
        "stage": "postprocess",
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "elapsed_s": round(elapsed, 2),
    }


def run_validate(
    validate_script: Path,
    final_dir: Path,
    asset_config: Path,
    studio_preset: Path,
    golden_fingerprint: Path | None,
    golden_tolerance: float,
) -> dict:
    """Validate the completed package against the TYCOON_ASSET_BAKE_V1 contract."""
    # Find the manifest produced by postprocess
    manifests = list(final_dir.glob("*_manifest.json"))
    # Prefer the asset-specific manifest over studio manifest aliases
    preferred = [m for m in manifests if "studio" not in m.name]
    if preferred:
        manifest_path = preferred[0]
    elif manifests:
        manifest_path = manifests[0]
    else:
        return {
            "stage": "validate",
            "status": "failed",
            "error": f"No manifest JSON found in {final_dir}",
        }

    cmd = [
        sys.executable,
        str(validate_script),
        "--manifest",
        str(manifest_path),
        "--asset-config",
        str(asset_config),
        "--studio-preset",
        str(studio_preset),
    ]
    if golden_fingerprint:
        cmd += [
            "--golden-fingerprint", str(golden_fingerprint),
            "--golden-mean-abs-tolerance", str(golden_tolerance),
        ]

    print(f"\n[validate] Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=False, text=True)
    elapsed = time.monotonic() - t0

    return {
        "stage": "validate",
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "elapsed_s": round(elapsed, 2),
        "manifest": str(manifest_path),
    }


def run_runtime_gate(gate_script: Path, final_dir: Path) -> dict:
    """Render a deterministic road/sidewalk/terrain placement board from the final package."""
    manifests = sorted(final_dir.glob("*_manifest.json"))
    if len(manifests) != 1:
        return {"stage": "runtime_placement_gate", "status": "failed",
                "error": f"Expected exactly one asset manifest in {final_dir}, found {len(manifests)}"}
    cmd = [sys.executable, str(gate_script), "--manifest", str(manifests[0]), "--output", str(final_dir)]
    print(f"\n[runtime_placement_gate] Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=False, text=True)
    return {"stage": "runtime_placement_gate",
            "status": "passed" if result.returncode == 0 else "failed",
            "returncode": result.returncode, "elapsed_s": round(time.monotonic() - t0, 2)}


def run_promotion(ingest_script: Path, final_dir: Path, asset_dir: Path, pack_out: Path, force: bool) -> dict:
    """Promote an already validated bake through the canonical content-pack ingest."""
    manifests = sorted(final_dir.glob("*_manifest.json"))
    if len(manifests) != 1:
        return {"stage": "promote", "status": "failed",
                "error": f"Expected exactly one asset manifest in {final_dir}, found {len(manifests)}"}
    cmd = [sys.executable, str(ingest_script), "--manifest", str(manifests[0]),
           "--asset-dir", str(asset_dir), "--pack-out", str(pack_out)]
    if force:
        cmd.append("--force")
    print(f"\n[promote] Running: {' '.join(cmd)}")
    t0 = time.monotonic()
    result = subprocess.run(cmd, capture_output=False, text=True)
    return {"stage": "promote", "status": "passed" if result.returncode == 0 else "failed",
            "returncode": result.returncode, "elapsed_s": round(time.monotonic()-t0, 2),
            "asset_dir": str(asset_dir), "pack_out": str(pack_out)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_report(output_dir: Path, contract: dict, stage_results: list[dict]) -> Path:
    """Write bake_run_report.json summarising all pipeline stages."""
    all_passed = all(r.get("status") == "passed" for r in stage_results)
    report = {
        "runnerVersion": RUNNER_VERSION,
        "contractId": contract.get("id"),
        "contractStatus": contract.get("status"),
        "cameraContract": contract.get("camera", {}).get("contract"),
        "gridContract": contract.get("footprint", {}).get("gridContract"),
        "overallStatus": "passed" if all_passed else "failed",
        "stages": stage_results,
        "promotionRule": contract.get("promotionRule", ""),
    }
    report_path = output_dir / "bake_run_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()

    # ── Resolve paths ──────────────────────────────────────────────────────
    contract_path = Path(args.contract).resolve()
    output_dir = Path(args.output_dir).resolve()
    source_dir = output_dir / "source"
    final_dir = output_dir / "final"

    try:
        scene_script = _tools_dir(args.scene, "tycoon_photo_studio/build_scene.py")
        postprocess_script = _tools_dir(
            args.postprocess, "tycoon_photo_studio/postprocess.py"
        )
        validate_script = _tools_dir(
            args.validate, "tycoon_photo_studio/validate_package.py"
        )
        ingest_script = _tools_dir(None, "asset_catalog_ingest.py")
        runtime_gate_script = _tools_dir(None, "tycoon_photo_studio/runtime_placement_gate.py")
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    # ── Load & validate contract ───────────────────────────────────────────
    print(f"[runner] Contract : {contract_path}")
    try:
        contract = load_contract(contract_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] Contract validation failed: {exc}", file=sys.stderr)
        return 1

    asset_config = Path(args.asset_config).resolve()
    studio_preset = Path(args.studio_preset).resolve()
    golden_fingerprint = Path(args.golden_fingerprint).resolve() if args.golden_fingerprint else None
    if not asset_config.is_file() or not studio_preset.is_file():
        print("[ERROR] Asset config or studio preset does not exist.", file=sys.stderr)
        return 1
    if golden_fingerprint and not golden_fingerprint.is_file():
        print(f"[ERROR] Golden fingerprint not found: {golden_fingerprint}", file=sys.stderr)
        return 1
    if bool(args.promote_asset_dir) != bool(args.promote_pack_out):
        print("[ERROR] --promote-asset-dir and --promote-pack-out must be provided together.", file=sys.stderr)
        return 1

    renderer = contract["renderer"]
    print(f"[runner] Asset bake contract '{contract['id']}' loaded and validated")
    print(f"         Camera   : {contract['camera']['contract']} "
          f"({contract['camera']['projection']})")
    print(f"         Renderer : {renderer['backend']} {renderer.get('version', '')} "
          f"/ {renderer['engine']} / {'headless' if renderer.get('headless') else 'interactive'}")
    print(f"         Pivot    : projected world origin (0,0,0), "
          f"identical across all {len(DIRECTION_ORDER)} directions")

    if args.dry_run:
        print("\n[runner] --dry-run: all inputs validated — Blender NOT invoked.")
        print(f"         Scene    : {scene_script}")
        print(f"         Asset    : {asset_config}")
        print(f"         Studio   : {studio_preset}")
        print(f"         Post     : {postprocess_script}")
        print(f"         Validate : {validate_script}")
        print(f"         Output   : {output_dir}")
        return 0

    # ── Resolve Blender executable ─────────────────────────────────────────
    try:
        blender_exe = resolve_blender(args.blender)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"[runner] Blender  : {blender_exe}")
    print(f"[runner] Output   : {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Blender bake ─────────────────────────────────────────────
    stage_results: list[dict] = []

    bake_result = run_blender_bake(
        blender_exe=blender_exe,
        scene_script=scene_script,
        asset_config=asset_config,
        studio_preset=studio_preset,
        output_source_dir=source_dir,
        xvfb=args.xvfb,
        extra_args=args.blender_extra_args,
    )
    stage_results.append(bake_result)
    if bake_result["status"] != "passed":
        print(
            f"\n[ERROR] Blender bake failed (exit {bake_result.get('returncode')}).",
            file=sys.stderr,
        )
        write_report(output_dir, contract, stage_results)
        return 1

    # ── Stage 2: Post-process ──────────────────────────────────────────────
    pp_result = run_postprocess(postprocess_script, source_dir, final_dir, studio_preset)
    stage_results.append(pp_result)
    if pp_result["status"] != "passed":
        print(
            f"\n[ERROR] Post-process failed (exit {pp_result.get('returncode')}).",
            file=sys.stderr,
        )
        write_report(output_dir, contract, stage_results)
        return 1

    # ── Stage 3: Validate ─────────────────────────────────────────────────
    if not args.skip_validate:
        val_result = run_validate(
            validate_script, final_dir, asset_config, studio_preset,
            golden_fingerprint, args.golden_mean_abs_tolerance
        )
        stage_results.append(val_result)
        if val_result["status"] != "passed":
            print(
                f"\n[ERROR] Package validation failed.",
                file=sys.stderr,
            )
            write_report(output_dir, contract, stage_results)
            return 1
    else:
        stage_results.append({"stage": "validate", "status": "skipped"})
        print("\n[validate] Skipped (--skip-validate).")

    # ── Stage 4: gameplay-scale placement review ──────────────────────────
    if not args.skip_validate:
        gate_result = run_runtime_gate(runtime_gate_script, final_dir)
        stage_results.append(gate_result)
        if gate_result["status"] != "passed":
            print("\n[ERROR] Runtime placement gate failed.", file=sys.stderr)
            write_report(output_dir, contract, stage_results)
            return 1

    # ── Optional canonical promotion ───────────────────────────────────────
    if args.promote_asset_dir:
        promotion_result = run_promotion(
            ingest_script, final_dir, Path(args.promote_asset_dir).resolve(),
            Path(args.promote_pack_out).resolve(), args.promote_force
        )
        stage_results.append(promotion_result)
        if promotion_result["status"] != "passed":
            print("\n[ERROR] Promotion failed.", file=sys.stderr)
            write_report(output_dir, contract, stage_results)
            return 1

    # ── Write report ──────────────────────────────────────────────────────
    report_path = write_report(output_dir, contract, stage_results)
    total_elapsed = sum(r.get("elapsed_s", 0) for r in stage_results)

    print(f"\n[runner] ✓ All pipeline stages passed in {total_elapsed:.1f}s")
    print(f"[runner] Report : {report_path}")
    print(f"[runner] Final  : {final_dir}")

    human_approval = contract.get("postProcess", {}).get("humanApprovalRequired", True)
    if human_approval:
        print(
            "\n[runner] NOTE: humanApprovalRequired=true — "
            "this bake is a VISUAL CANDIDATE and must not be promoted to production "
            "without explicit human visual approval at gameplay scale."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
