#!/usr/bin/env python3
"""Fail closed on partial, corrupt or unapproved Blender turntable promotions.

Runtime is allowed to use the old procedural platform if no manifest is
installed; a present manifest must have all 4*25 plus 4 base RGBA images.
No 102-image runtime set is ever inferred from a bare screenshot/proxy.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "assets/rail/turntable_7m2_01"
SOURCE_SHA = "89cbd2228b688ecbde7cdc5f10126854f0c39d1c524c4fe2b545f522ba8a6046"
CONTRACT = "CH_RAIL_TURNTABLE_RUNTIME_V1"
DIRECTIONS = ("south","east","west","north")
FRAMES = 25

def check() -> None:
    index=ASSET/"runtime_manifest.json"
    if not index.is_file():
        print("CH_RAIL_TURNTABLE_RUNTIME: no installed manifest; procedural fallback remains")
        return
    doc=json.loads(index.read_text(encoding="utf-8"))
    if (doc.get("contract")!=CONTRACT or
        doc.get("approvedProxySha256")!=SOURCE_SHA or
        doc.get("cameraContract")!="CH_CAMERA_V1" or
        doc.get("diameterMetres")!=7.2 or
        doc.get("frameCount")!=FRAMES or
        doc.get("baseResolution")!=1024 or
        doc.get("bridgeResolution")!=512 or
        doc.get("finalBakeQualityGate")!="pass" or
        doc.get("userApprovedForRuntime") is not True):
        raise ValueError("turntable runtime contract/provenance mismatch")
    files=doc.get("files",{})
    required={f"rail_turntable_base_{direction}.png"
              for direction in DIRECTIONS}
    required.update(f"rail_turntable_bridge_{direction}_phase_{frame:02d}.png"
                    for direction in DIRECTIONS for frame in range(FRAMES))
    if set(files)!=required:raise ValueError("turntable asset incomplete, extra or missing frames")
    for name in sorted(required):
        path=ASSET/name
        data=path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data)<100:
            raise ValueError(f"invalid PNG: {name}")
        width,height,depth,ctype=struct.unpack(">IIBB",data[16:26])
        expected=1024 if name.startswith("rail_turntable_base_") else 512
        if (width,height,depth,ctype)!=(expected,expected,8,6):
            raise ValueError(f"wrong 8bit RGBA frame size: {name}, {width}x{height} type {ctype}")
        sha=hashlib.sha256(data).hexdigest()
        if sha!=files[name]:raise ValueError(f"corrupted or replaced frame: {name}")
    for direction in DIRECTIONS:
        unique={files[f"rail_turntable_bridge_{direction}_phase_{i:02d}.png"]
                for i in range(FRAMES)}
        if len(unique)<18:
            raise ValueError(f"bridge angle frames repeated / frozen: {direction}")
    print("CH_RAIL_TURNTABLE_RUNTIME_V1: PASS 104 RGBA files, approved provenance, 4 views x 25 bridge phases")

if __name__=="__main__":
    try:check()
    except Exception as exc:
        print(f"CH_RAIL_TURNTABLE_RUNTIME: FAIL {exc}",file=sys.stderr)
        sys.exit(1)
