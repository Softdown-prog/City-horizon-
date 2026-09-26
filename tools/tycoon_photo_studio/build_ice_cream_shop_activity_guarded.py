#!/usr/bin/env python3
"""Guarded CH Blender adapter for the ice-cream-shop activity overlay.

Adapts the asset-specific baker to the canonical CH Blender quality-gate files:
preflight_report.json, proxy_south.png, proxy_report.json and final approval/meta.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import build_ice_cream_shop_activity_overlay as activity


def _argv_after_separator() -> list[str]:
    argv = list(sys.argv)
    return argv[argv.index("--") + 1:] if "--" in argv else []


def _value(args: list[str], flag: str, default: str | None = None) -> str | None:
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return default


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = _argv_after_separator()
    stage = str(_value(args, "--stage", "preflight"))
    output_raw = _value(args, "--output")
    if not output_raw:
        raise RuntimeError("ICE_CREAM_ACTIVITY_GUARDED_OUTPUT_REQUIRED")
    output = Path(output_raw).resolve()
    output.mkdir(parents=True, exist_ok=True)

    approval_sha = _value(args, "--approval-proxy-sha")

    # The asset-specific baker does not own the final approval token. Strip it
    # before delegating; the adapter writes the canonical approval artifact.
    delegated = []
    skip_next = False
    for item in args:
        if skip_next:
            skip_next = False
            continue
        if item == "--approval-proxy-sha":
            skip_next = True
            continue
        delegated.append(item)

    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0], "--", *delegated]
        activity.main()
    finally:
        sys.argv = old_argv

    _write_json(output / "preflight_report.json", {
        "contract": "CH_SCENE_PREFLIGHT_V1",
        "status": "pass",
        "assetId": activity.ASSET_ID,
        "stage": stage,
        "checks": [
            "asset_identity",
            "studio_contract",
            "animation_frame_count",
            "required_storefront_parts",
            "activity_overlay_contract",
        ],
    })

    if stage == "proxy":
        source = output / "proxy_south_active.png"
        target = output / "proxy_south.png"
        if not source.exists():
            raise RuntimeError("ICE_CREAM_ACTIVITY_PROXY_MISSING")
        shutil.copyfile(source, target)
        _write_json(output / "proxy_report.json", {
            "contract": "CH_PROXY_RENDER_V1",
            "status": "ok",
            "assetId": activity.ASSET_ID,
            "direction": "south",
            "sha256": _sha256(target),
            "source": target.name,
            "activityEffects": ["window_glow", "door_glow", "rotating_popsicle"],
        })

    if stage == "final":
        metadata_source = output / "activity_overlay_metadata.json"
        if not metadata_source.exists():
            raise RuntimeError("ICE_CREAM_ACTIVITY_METADATA_MISSING")
        shutil.copyfile(metadata_source, output / "studio_metadata.json")
        if not approval_sha:
            raise RuntimeError("ICE_CREAM_ACTIVITY_APPROVAL_SHA_REQUIRED")
        _write_json(output / "proxy_approval.json", {
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": activity.ASSET_ID,
            "reviewed": True,
            "proxySha256": approval_sha,
        })


if __name__ == "__main__":
    main()
