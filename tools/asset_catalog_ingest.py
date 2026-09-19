"""Asset Catalog Ingest — TYCOON_ASSET_BAKE_V1 manifest → CH_CONTENT_PACK_V1 converter.

Reads a *_manifest.json produced by the Tycoon bake pipeline and emits a
CH_CONTENT_PACK_V1 JSON entry compatible with MapForge2 Studio's content
catalog.  Also copies the four directional PNGs into the canonical asset
definitions tree.

Usage
-----
    # Emit a content-pack entry and copy PNGs to assets/buildings/<id>/
    python tools/asset_catalog_ingest.py \\
        --manifest out/bake/park_kiosk_1x1/final/park_kiosk_1x1_manifest.json \\
        --pack-out assets/definitions/buildings/park_kiosk_1x1_pack.json \\
        --asset-dir assets/buildings/

    # Only validate the manifest without writing anything
    python tools/asset_catalog_ingest.py \\
        --manifest park_kiosk_1x1_manifest.json --validate-only

    # Overwrite an existing pack entry
    python tools/asset_catalog_ingest.py \\
        --manifest ... --pack-out ... --asset-dir ... --force

Notes
-----
- Never overwrites an existing pack file without --force.
- Emits a WARNING (not an error) when humanApprovalRequired=true so the
  integrator is reminded that the bake is still a visual candidate.
- The emitted CH_CONTENT_PACK_V1 entry follows the stable-ID rules defined
  in CH_STUDIO_ARCHITECTURE_V1.md: lowercase letters, digits, '.', '_', '-'.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INGEST_VERSION = "1.0.0"
REQUIRED_MANIFEST_FIELDS = (
    "contract",
    "assetId",
    "assetType",
    "cameraContract",
    "gridContract",
    "footprint",
    "directionOrder",
    "views",
    "files",
)
CANONICAL_DIRECTION_ORDER = ["south", "east", "west", "north"]
STABLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asset Catalog Ingest — TYCOON_ASSET_BAKE_V1 → CH_CONTENT_PACK_V1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--manifest",
        required=True,
        metavar="PATH",
        help="Path to *_manifest.json produced by the Tycoon bake pipeline",
    )
    parser.add_argument(
        "--pack-out",
        default=None,
        metavar="PATH",
        help=(
            "Output path for the CH_CONTENT_PACK_V1 JSON entry.  "
            "Required unless --validate-only is set."
        ),
    )
    parser.add_argument(
        "--asset-dir",
        default=None,
        metavar="DIR",
        help=(
            "Root directory where PNGs will be copied "
            "(e.g. assets/buildings/).  "
            "Files are placed in <asset-dir>/<assetId>/.  "
            "Required unless --validate-only is set."
        ),
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the manifest; do not write any files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pack file and PNG directory",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def load_and_validate_manifest(path: Path) -> dict:
    """Load the manifest and check structural invariants."""
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))

    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        raise ValueError(f"Manifest is missing required fields: {missing}")

    if manifest["contract"] != "TYCOON_ASSET_BAKE_V1":
        raise ValueError(
            f"Expected contract 'TYCOON_ASSET_BAKE_V1', got '{manifest['contract']}'"
        )
    if manifest["cameraContract"] != "CH_CAMERA_V1":
        raise ValueError(
            f"Expected cameraContract 'CH_CAMERA_V1', got '{manifest['cameraContract']}'"
        )
    if manifest["gridContract"] != "CH_GRID_V1":
        raise ValueError(
            f"Expected gridContract 'CH_GRID_V1', got '{manifest['gridContract']}'"
        )
    if manifest["directionOrder"] != CANONICAL_DIRECTION_ORDER:
        raise ValueError(
            f"directionOrder must be {CANONICAL_DIRECTION_ORDER}, "
            f"got {manifest['directionOrder']}"
        )

    # Validate pivot invariant: all four views must share one pivot
    views = manifest.get("views", [])
    if len(views) != 4:
        raise ValueError(f"Manifest must have exactly 4 views, got {len(views)}")
    pivots = {(v["pivot"]["x"], v["pivot"]["y"]) for v in views}
    if len(pivots) != 1:
        raise ValueError(
            f"Pivot invariant violated: four directions do not share one pivot. "
            f"Found: {sorted(pivots)}"
        )

    return manifest


# ---------------------------------------------------------------------------
# Content-pack generation
# ---------------------------------------------------------------------------


def make_stable_id(asset_id: str) -> str:
    """Convert assetId to a CH_CONTENT_PACK_V1 stable ID."""
    # asset_id may already be in the right format (e.g. 'park_kiosk_1x1')
    # Normalise: lowercase, replace spaces/dots with underscores
    stable = asset_id.lower().replace(" ", "_").replace("-", "_")
    if not STABLE_ID_PATTERN.match(stable):
        raise ValueError(
            f"Cannot derive a valid stable ID from assetId '{asset_id}'. "
            "IDs must match [a-z0-9][a-z0-9._-]*"
        )
    return stable


def build_content_pack_entry(manifest: dict, asset_png_dir: Path | None) -> dict:
    """Build the CH_CONTENT_PACK_V1 JSON entry from the manifest."""
    asset_id = manifest["assetId"]
    stable_id = make_stable_id(asset_id)

    footprint = manifest.get("footprint", {})
    views = manifest.get("views", [])
    shared_pivot = views[0]["pivot"] if views else {}
    atlas = manifest.get("atlas", {})
    post = manifest.get("candidatePostProcess", {})

    # Build per-direction source paths (relative to asset-dir/<assetId>/)
    view_entries = []
    for view in views:
        entry = {
            "direction": view["direction"],
            "quarterTurns": view["quarterTurns"],
            "file": view["file"],
            "pivot": view["pivot"],
            "spriteAlphaBounds": view.get("spriteAlphaBounds"),
        }
        view_entries.append(entry)

    pack_entry = {
        "packVersion": "CH_CONTENT_PACK_V1",
        "ingestVersion": INGEST_VERSION,
        "id": stable_id,
        "displayName": asset_id.replace("_", " ").title(),
        "kind": "building",
        "assetId": asset_id,
        "bakeContract": manifest["contract"],
        "bakeStatus": manifest.get("status", "visual_candidate"),
        "humanApprovalRequired": manifest.get("humanApprovalRequired", True),
        "visualId": stable_id,
        "sourcePath": str(asset_png_dir / asset_id) if asset_png_dir else None,
        "cameraContract": manifest["cameraContract"],
        "gridContract": manifest["gridContract"],
        "projection": manifest.get("projection"),
        "tile": manifest.get("tile", {"width": 128, "height": 64}),
        "footprint": {
            "widthTiles": footprint.get("widthTiles", 1),
            "depthTiles": footprint.get("depthTiles", 1),
            "occupiedCells": footprint.get("occupiedCells", [[0, 0]]),
        },
        "pivot": shared_pivot,
        "directionCount": manifest.get("directionCount", 4),
        "directionOrder": manifest.get("directionOrder", CANONICAL_DIRECTION_ORDER),
        "views": view_entries,
        "atlas": {
            "file": atlas.get("file"),
            "packing": atlas.get("packing"),
            "paddingPx": atlas.get("paddingPx", 2),
            "frames": atlas.get("frames", []),
        },
        "postProcess": {
            "variantId": post.get("variantId"),
            "mode": post.get("mode"),
            "dither": post.get("dither"),
            "status": post.get("status"),
        },
        "files": manifest.get("files", {}),
        "dependencies": [],
    }
    return pack_entry


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def copy_png_assets(
    manifest: dict,
    manifest_dir: Path,
    asset_dir: Path,
    force: bool,
) -> Path:
    """Copy directional PNGs and the atlas into asset_dir/<assetId>/."""
    asset_id = manifest["assetId"]
    dest_dir = asset_dir / asset_id
    if dest_dir.exists() and not force:
        raise FileExistsError(
            f"Asset directory already exists: {dest_dir}. "
            "Use --force to overwrite."
        )
    dest_dir.mkdir(parents=True, exist_ok=True)

    files_node = manifest.get("files", {})
    atlas_node = manifest.get("atlas", {})
    to_copy = list(files_node.values())
    if atlas_node.get("file"):
        to_copy.append(atlas_node["file"])
    # Deduplicate
    to_copy = list(dict.fromkeys(to_copy))

    copied = []
    for fname in to_copy:
        src = manifest_dir / fname
        if src.is_file():
            dest = dest_dir / Path(fname).name
            shutil.copy2(src, dest)
            copied.append(dest.name)
        else:
            print(f"  [WARN] Source PNG not found, skipping: {src}")

    print(f"  Copied {len(copied)} files → {dest_dir}")
    return dest_dir


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()

    print(f"[ingest] Manifest : {manifest_path}")

    # ── Load and validate ──────────────────────────────────────────────────
    try:
        manifest = load_and_validate_manifest(manifest_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    asset_id = manifest["assetId"]
    status = manifest.get("status", "unknown")
    human_approval = manifest.get("humanApprovalRequired", True)

    print(f"[ingest] Asset    : {asset_id}")
    print(f"[ingest] Status   : {status}")

    if human_approval:
        print(
            "[WARN]  humanApprovalRequired=true — "
            "this asset is a VISUAL CANDIDATE and must not be shipped to players "
            "without explicit human visual approval at gameplay scale."
        )

    # Derive stable ID (also validates the format)
    try:
        stable_id = make_stable_id(asset_id)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[ingest] Stable ID: {stable_id}")

    if args.validate_only:
        print("[ingest] --validate-only: manifest is valid. No files written.")
        return 0

    # ── Require output args ────────────────────────────────────────────────
    if not args.pack_out:
        print("[ERROR] --pack-out is required unless --validate-only is set.", file=sys.stderr)
        return 1
    if not args.asset_dir:
        print("[ERROR] --asset-dir is required unless --validate-only is set.", file=sys.stderr)
        return 1

    pack_out = Path(args.pack_out).resolve()
    asset_dir = Path(args.asset_dir).resolve()

    if pack_out.exists() and not args.force:
        print(
            f"[ERROR] Pack file already exists: {pack_out}. "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    # ── Copy PNGs ──────────────────────────────────────────────────────────
    print(f"\n[ingest] Copying PNGs → {asset_dir}")
    try:
        dest_asset_dir = copy_png_assets(
            manifest=manifest,
            manifest_dir=manifest_path.parent,
            asset_dir=asset_dir,
            force=args.force,
        )
    except FileExistsError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    # ── Build and write content-pack entry ────────────────────────────────
    pack_entry = build_content_pack_entry(manifest, asset_dir)
    # Update sourcePath now that we know the real dest
    pack_entry["sourcePath"] = str(dest_asset_dir)

    pack_out.parent.mkdir(parents=True, exist_ok=True)
    pack_out.write_text(json.dumps(pack_entry, indent=2), encoding="utf-8")

    print(f"\n[ingest] ✓ Content pack entry written: {pack_out}")
    print(f"[ingest]   kind        : {pack_entry['kind']}")
    print(f"[ingest]   id          : {pack_entry['id']}")
    print(f"[ingest]   footprint   : {pack_entry['footprint']['widthTiles']}×"
          f"{pack_entry['footprint']['depthTiles']} tiles")
    print(f"[ingest]   directions  : {pack_entry['directionOrder']}")
    print(f"[ingest]   bakeStatus  : {pack_entry['bakeStatus']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
