#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tools/ch_blender/ch_blender_manifest.json"
SERIES = REPO_ROOT / "tools/ch_blender/patches/series.json"
STATE_CONTRACT = "CH_BLENDER_SOURCE_STATE_V1"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(args: list[str], cwd: Path, capture: bool = False) -> str:
    p = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=capture)
    return (p.stdout or "").strip()


def patchset_id() -> str:
    m = load_json(MANIFEST)
    s = load_json(SERIES)
    h = hashlib.sha256()
    h.update(str(m["upstream"]["commit"]).encode())
    for item in s["patches"]:
        p = REPO_ROOT / item["path"]
        h.update(item["id"].encode())
        h.update(sha256(p).encode())
    return h.hexdigest()


def prepare(workspace: Path, offline: bool) -> dict:
    m = load_json(MANIFEST)
    s = load_json(SERIES)
    expected = m["upstream"]["commit"]
    if s["upstreamCommit"] != expected:
        raise RuntimeError("Patch series upstream commit does not match manifest")

    src = workspace / "blender-src"
    workspace.mkdir(parents=True, exist_ok=True)
    if not (src / ".git").exists():
        if offline:
            raise RuntimeError("Offline mode requested but Blender source is absent")
        run(["git", "clone", "--filter=blob:none", "--no-checkout", m["upstream"]["repository"], str(src)], workspace)

    try:
        run(["git", "cat-file", "-e", f"{expected}^{{commit}}"], src)
    except subprocess.CalledProcessError:
        if offline:
            raise
        run(["git", "fetch", "origin", m["upstream"]["tag"]], src)

    run(["git", "checkout", "--detach", expected], src)
    run(["git", "reset", "--hard", expected], src)
    run(["git", "clean", "-ffd"], src)

    applied = []
    for item in s["patches"]:
        patch = REPO_ROOT / item["path"]
        run(["git", "apply", "--check", str(patch)], src)
        run(["git", "apply", str(patch)], src)
        applied.append({"id": item["id"], "path": item["path"], "sha256": sha256(patch)})

    marker = m["internalBuild"]["identityMarker"]
    branded = src / "source/blender/blenkernel/intern/blender.cc"
    if marker not in branded.read_text(encoding="utf-8"):
        raise RuntimeError("Internal identity marker was not applied")

    diff = run(["git", "diff", "--binary"], src, capture=True)
    state = {
        "contract": STATE_CONTRACT,
        "status": "ok",
        "upstreamTag": m["upstream"]["tag"],
        "upstreamCommit": expected,
        "head": run(["git", "rev-parse", "HEAD"], src, capture=True),
        "patchsetId": patchset_id(),
        "patches": applied,
        "diffSha256": hashlib.sha256(diff.encode()).hexdigest(),
        "identityMarker": marker,
        "rendererModified": False,
        "blendFileFormatModified": False,
        "sourceDir": str(src),
    }
    (workspace / "ch_blender_source_state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pid = sub.add_parser("patchset-id")
    pid.add_argument("--plain", action="store_true")
    prep = sub.add_parser("prepare")
    prep.add_argument("--workspace", required=True)
    prep.add_argument("--offline", action="store_true")
    prep.add_argument("--report")
    a = p.parse_args()
    if a.cmd == "patchset-id":
        value = patchset_id()
        print(value if a.plain else json.dumps({"contract": "CH_BLENDER_PATCHSET_ID_V1", "patchsetId": value}))
        return 0
    state = prepare(Path(a.workspace).resolve(), a.offline)
    if a.report:
        rp = Path(a.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
