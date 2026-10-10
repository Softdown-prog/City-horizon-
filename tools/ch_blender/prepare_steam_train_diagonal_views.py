#!/usr/bin/env python3
"""Composites only the four new diagonal views using the existing CH Photo Studio.

Called after CH Blender worker jobs; makes review PNGs and a contact sheet.
Never replaces approved runtime PNGs and does not edit the runtime manifest.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"tools"/"tycoon_photo_studio"))
import postprocess as studio_post

DIRECTIONS = ("north_east", "east_south", "south_west", "west_north")
PRESET = ROOT/"tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"

def prepare(role):
    source = ROOT/"out"/"ch_blender_agent"/("steam_train_diagonal_"+role+"_v1")
    metadata_path=source/"diagonal_bake_metadata.json"
    if not metadata_path.exists():
        raise RuntimeError("missing render metadata: "+str(metadata_path))
    meta=json.loads(metadata_path.read_text())
    assert meta["contract"]=="CH_RAIL_DIAGONAL_BAKE_V1" and meta["unit"]==role
    preset=json.loads(PRESET.read_text())
    studio_post.apply_studio_preset(preset)
    output=source/"review"
    output.mkdir(exist_ok=True)
    entries=[]
    board=Image.new("RGBA",(2048,2048),(216,222,212,255))
    painter=ImageDraw.Draw(board)
    for index, direction in enumerate(DIRECTIONS):
        spec=next(v for v in meta["views"] if v["direction"]==direction)
        color=Image.open(source/spec["colorSource"]).convert("RGBA")
        shadow_ref=Image.open(source/spec["shadowSource"]).convert("RGBA")
        shadow=studio_post.derive_shadow(color,shadow_ref)
        color_small=studio_post.downsample(color)
        shadow_small=studio_post.downsample(shadow)
        image=studio_post.composite_shadow(color_small,shadow_small)
        if image.size!=(1024,1024) or image.getchannel("A").getbbox() is None:
            raise RuntimeError("invalid diagonal PNG "+direction)
        name=f"steam_train_{role}_{direction}.png"
        path=output/name
        image.save(path)
        # Actual CH camera origin comes from the authoritative Blender scene.
        origin=spec["groundOriginSourcePx"]
        pivot={"x": round(origin["x"] / color.width * 1024),
               "y": round(origin["y"] / color.height * 1024)}
        entries.append({"direction":direction,"file":"review/"+name,
                        "pivot":pivot,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                        "alphaBounds":list(image.getchannel("A").getbbox())})
        panel=Image.new("RGBA",(1024,1024),(216,222,212,255))
        panel.alpha_composite(image)
        ImageDraw.Draw(panel).text((20,20),role.upper()+"  "+direction.upper(),fill=(23,29,34,255))
        board.alpha_composite(panel,((index%2)*1024,(index//2)*1024))
    board.convert("RGB").save(output/("steam_train_"+role+"_diagonal_contact.jpg"),quality=90)
    report={"contract":"CH_RAIL_DIAGONAL_REVIEW_V1","role":role,
            "approvedForRuntime":False,"cardinalSpritesUntouched":True,"views":entries}
    (output/"diagonal_review_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    for unit in ("locomotive","coach"):
        prepare(unit)
