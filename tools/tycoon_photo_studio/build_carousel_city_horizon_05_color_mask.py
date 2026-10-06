#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import bpy

import build_carousel_city_horizon_05_guarded as base


def mask_material(name, rgba):
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    nodes=m.node_tree.nodes
    links=m.node_tree.links
    nodes.clear()
    out=nodes.new("ShaderNodeOutputMaterial")
    emit=nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value=rgba
    emit.inputs["Strength"].default_value=1.0
    links.new(emit.outputs["Emission"],out.inputs["Surface"])
    return m


def main():
    a=base.args()
    recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=base.CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V5 recipe")

    studio=base.bs.load_json(a.studio_preset)
    out=Path(a.output).resolve()
    out.mkdir(parents=True,exist_ok=True)

    scene,root,ground,authored=base.build(recipe,studio,out)
    profile=base.scene_gate.load_profile(a.preflight_profile)
    pre=base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=base.ASSET_ID,
        report_path=out/"preflight_report.json",
    )
    base.scene_gate.require_pass(pre)

    primary=mask_material("CarouselMaskPrimary",(1.0,0.0,0.0,1.0))
    secondary=mask_material("CarouselMaskSecondary",(0.0,1.0,0.0,1.0))

    # Mask ONLY the striped canopy wedges. Everything else is excluded.
    roof=[]
    for obj in bpy.context.scene.objects:
        if obj.type!="MESH":
            continue
        if obj.name.startswith("Roof_"):
            roof.append(obj)
            idx=int(obj.name.split("_")[-1])
            obj.hide_render=False
            obj.data.materials.clear()
            obj.data.materials.append(primary if idx%2==0 else secondary)
        else:
            obj.hide_render=True

    if len(roof)!=int(recipe["geometry"]["canopySegments"]):
        raise RuntimeError(f"Expected {recipe['geometry']['canopySegments']} roof wedges, got {len(roof)}")

    scene.render.film_transparent=True
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"

    # set_direction() guards the fixed CH studio, including color management.
    # Keep the studio untouched while rotating. Switch to linear mask output
    # only for the render itself, then restore before the next direction.
    original_view={
        "look": scene.view_settings.look,
        "view_transform": scene.view_settings.view_transform,
        "exposure": scene.view_settings.exposure,
        "gamma": scene.view_settings.gamma,
    }

    def set_mask_view():
        scene.view_settings.look="None"
        scene.view_settings.view_transform="Standard"
        scene.view_settings.exposure=0
        scene.view_settings.gamma=1

    def restore_studio_view():
        scene.view_settings.view_transform=original_view["view_transform"]
        scene.view_settings.look=original_view["look"]
        scene.view_settings.exposure=original_view["exposure"]
        scene.view_settings.gamma=original_view["gamma"]

    reports={}
    for direction in base.bs.DIRECTIONS:
        restore_studio_view()
        base.bs.set_direction(root,direction)
        bpy.context.view_layer.update()
        did=direction["id"]
        path=out/f"mask_{did}.png"
        set_mask_view()
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        restore_studio_view()
        reports[did]={"file":path.name,"primary":"R","secondary":"G"}

    # Satisfy the generic proxy worker contract without changing mask semantics.
    south=out/"mask_south.png"
    proxy=out/"proxy_south.png"
    proxy.write_bytes(south.read_bytes())
    (out/"proxy_report.json").write_text(json.dumps({
        "contract":"CH_COLOR_MASK_RENDER_REPORT_V1",
        "assetId":"park_carousel_01",
        "primaryMeaning":"red canopy stripes",
        "secondaryMeaning":"cream canopy stripes",
        "coverage":"canopy stripes only",
        "directions":reports
    },indent=2),encoding="utf-8")
    (out/"color_mask_manifest.json").write_text(json.dumps({
        "contract":"CH_COLOR_MASK_V1",
        "assetId":"park_carousel_01",
        "channels":{"R":"primary","G":"secondary"},
        "alpha":"coverage",
        "primaryMeaning":"red canopy stripes",
        "secondaryMeaning":"cream canopy stripes",
        "directionOrder":[d["id"] for d in base.bs.DIRECTIONS],
        "files":{d["id"]:f"mask_{d['id']}.png" for d in base.bs.DIRECTIONS}
    },indent=2),encoding="utf-8")

    base.bs.set_direction(root,base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()


if __name__=="__main__":
    main()
