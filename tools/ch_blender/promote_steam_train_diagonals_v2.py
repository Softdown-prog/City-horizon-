#!/usr/bin/env python3
"""Promote the reviewed CH Blender V2 diagonal sprites from a GitHub Actions artifact.

Never overwrites approved cardinal assets. Fails closed on mismatched review
hashes, missing alpha/quality metadata, or unexpected Blender camera anchors.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[2]
source=Path(sys.argv[1]).resolve()
names=("north_east","east_south","south_west","west_north")
for role,py in (("locomotive",641),("coach",684)):
    folder=source/f"steam_train_diagonal_{role}_v2"/"review"
    report=json.loads((folder/"diagonal_review_report.json").read_text())
    assert report["contract"]=="CH_RAIL_DIAGONAL_REVIEW_V2"
    assert report["role"]==role and report["approvedForRuntime"] is False
    assert report["cardinalSpritesUntouched"] is True
    assert report["allViewsHaveMargin"] is True
    assert report["runtimePixelScaleCompensation"]==1.28
    assert set(v["direction"] for v in report["views"])==set(names)
    target=root/"assets"/"vehicles"/f"steam_train_{role}_01"
    assert target.is_dir()
    old=json.loads((target/"steam_train_unit_runtime.json").read_text())
    assert old["approvedForRuntime"] is True and len(old["views"])==4
    promoted={}
    for v in report["views"]:
        name=v["direction"]
        assert v["pivot"]=={"x":512,"y":py}
        assert v["opaqueSourceMarginPx"]>=40
        image=folder/f"steam_train_{role}_{name}.png"
        assert image.name==Path(v["file"]).name
        data=image.read_bytes()
        assert hashlib.sha256(data).hexdigest()==v["sha256"]
        with Image.open(image) as im:
            assert im.size==(1024,1024) and im.mode=="RGBA"
            assert im.getchannel("A").getbbox()
        shutil.copyfile(image,target/image.name)
        promoted[name]={"file":image.name,"sha256":v["sha256"],
                        "pivot":v["pivot"]}
    manifest={
       "contract":"CH_RAIL_DIAGONAL_RUNTIME_V1",
       "unitRole":role,
       "approvedForRuntime":True,
       "cameraContract":"CH_CAMERA_V1",
       "sourceWorkflowRun":38054190025,
       "sourceArtifactId":11670614740,
       "runtimePixelScaleCompensation":1.28,
       "originalCardinalViewsPreserved":True,
       "views":promoted,
    }
    (target/"steam_train_diagonal_runtime.json").write_text(
       json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("CH_RAIL_DIAGONAL_PROMOTION PASS",role,len(promoted))
