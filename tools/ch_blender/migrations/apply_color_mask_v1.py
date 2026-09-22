#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"CH_COLOR_MASK_PATCH_MISMATCH: {path}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


build = ROOT / "tools/tycoon_photo_studio/build_scene.py"
replace_once(
    build,
    '''except Exception:\n    _mat_lib = None\n    _MAT_LIB_AVAILABLE = False\n\nDIRECTIONS = (''',
    '''except Exception:\n    _mat_lib = None\n    _MAT_LIB_AVAILABLE = False\n\nimport ch_color_mask as _mask_lib\n\nDIRECTIONS = (''',
)

replace_once(
    build,
    '''    materials = {}\n    for key, spec in asset.get("materials", {}).items():\n        materials[key] = make_material(\n            spec.get("name", key),\n            spec["rgba"],\n            float(spec.get("roughness", 0.72)),\n            float(spec.get("metallic", 0.0)),\n            recipe=spec.get("recipe"),          # GAP 4: None → solid fallback\n            seed=int(spec.get("seed", 0)),\n            strength=float(spec.get("strength", 1.0)),\n        )''',
    '''    materials = {}\n    for key, spec in asset.get("materials", {}).items():\n        material = make_material(\n            spec.get("name", key),\n            spec["rgba"],\n            float(spec.get("roughness", 0.72)),\n            float(spec.get("metallic", 0.0)),\n            recipe=spec.get("recipe"),          # GAP 4: None → solid fallback\n            seed=int(spec.get("seed", 0)),\n            strength=float(spec.get("strength", 1.0)),\n        )\n        if spec.get("maskRole"):\n            _mask_lib.tag_material(material, spec["maskRole"])\n        materials[key] = material''',
)

for kind, fn in (("blend_import", "import_blend_collection"), ("fbx_import", "import_fbx"), ("glb_import", "import_glb")):
    if kind == "blend_import":
        old = '''        elif kind == "blend_import":\n            objs = import_blend_collection(part, asset_config_path)\n            authored.extend(objs)'''
        new = '''        elif kind == "blend_import":\n            objs = import_blend_collection(part, asset_config_path)\n            _mask_lib.tag_imported_objects(objs, part.get("maskRole"))\n            authored.extend(objs)'''
    elif kind == "fbx_import":
        old = '''        elif kind == "fbx_import":\n            objs = import_fbx(part, asset_config_path)\n            authored.extend(objs)'''
        new = '''        elif kind == "fbx_import":\n            objs = import_fbx(part, asset_config_path)\n            _mask_lib.tag_imported_objects(objs, part.get("maskRole"))\n            authored.extend(objs)'''
    else:
        old = '''        elif kind == "glb_import":\n            objs = import_glb(part, asset_config_path)\n            authored.extend(objs)'''
        new = '''        elif kind == "glb_import":\n            objs = import_glb(part, asset_config_path)\n            _mask_lib.tag_imported_objects(objs, part.get("maskRole"))\n            authored.extend(objs)'''
    replace_once(build, old, new)

replace_once(
    build,
    '''    authored = build_asset(asset, asset_config_path=args.asset_config)\n    root = create_asset_root(authored)\n\n    # Footprint scale sanity check''',
    '''    authored = build_asset(asset, asset_config_path=args.asset_config)\n    root = create_asset_root(authored)\n    mask_spec = _mask_lib.normalize_spec(asset)\n    mask_assignment = _mask_lib.assignment_summary(authored, mask_spec) if mask_spec else None\n\n    # Footprint scale sanity check''',
)

replace_once(
    build,
    '''        color_name = f"{asset_id}_{direction_id}_color_source.png"\n        shadow_name = f"{asset_id}_{direction_id}_shadow_source.png"\n        render_color_pass(scene, authored, ground, os.path.join(output_dir, color_name))\n        render_shadow_pass(scene, authored, ground, os.path.join(output_dir, shadow_name))\n        direction_metadata.append({\n            **direction,\n            "colorSource": color_name,\n            "shadowSource": shadow_name,\n            "groundOriginSourcePx": ground_origin_source_px(scene),\n        })''',
    '''        color_name = f"{asset_id}_{direction_id}_color_source.png"\n        shadow_name = f"{asset_id}_{direction_id}_shadow_source.png"\n        mask_name = f"{asset_id}_{direction_id}_mask_source.png" if mask_spec else None\n        render_color_pass(scene, authored, ground, os.path.join(output_dir, color_name))\n        render_shadow_pass(scene, authored, ground, os.path.join(output_dir, shadow_name))\n        if mask_spec:\n            _mask_lib.render_mask_pass(\n                scene, authored, ground, os.path.join(output_dir, mask_name), mask_spec\n            )\n        direction_record = {\n            **direction,\n            "colorSource": color_name,\n            "shadowSource": shadow_name,\n            "groundOriginSourcePx": ground_origin_source_px(scene),\n        }\n        if mask_name:\n            direction_record["maskSource"] = mask_name\n        direction_metadata.append(direction_record)''',
)

replace_once(
    build,
    '''        "postProcess": studio["postProcess"],\n        "shadowMode": "Cycles shadow catcher with object hidden from camera",''',
    '''        "postProcess": studio["postProcess"],\n        "colorMask": _mask_lib.metadata(mask_spec, mask_assignment) if mask_spec else {"enabled": False},\n        "shadowMode": "Cycles shadow catcher with object hidden from camera",''',
)

post = ROOT / "tools/tycoon_photo_studio/postprocess.py"
replace_once(
    post,
    '''def make_direction_review(candidates, pivots):\n    board = Image.new("RGBA", (4 * 300, 380), (247, 245, 239, 255))\n    draw = ImageDraw.Draw(board)\n    draw.text((20, 14), "Tycoon Asset Baker V1 - four rotations, one source, frozen studio", fill=(32, 32, 32, 255))''',
    '''def make_direction_review(candidates, pivots, title="Tycoon Asset Baker V1 - four rotations, one source, frozen studio"):\n    board = Image.new("RGBA", (4 * 300, 380), (247, 245, 239, 255))\n    draw = ImageDraw.Draw(board)\n    draw.text((20, 14), title, fill=(32, 32, 32, 255))''',
)

replace_once(
    post,
    '''    if tuple(metadata.get("directionOrder", [])) != DIRECTION_ORDER:\n        raise RuntimeError(f"Direction order must be {DIRECTION_ORDER}, got {metadata.get('directionOrder')}")\n\n\n    candidates = {}''',
    '''    if tuple(metadata.get("directionOrder", [])) != DIRECTION_ORDER:\n        raise RuntimeError(f"Direction order must be {DIRECTION_ORDER}, got {metadata.get('directionOrder')}")\n\n    mask_meta = metadata.get("colorMask") or {}\n    mask_enabled = bool(mask_meta.get("enabled", False))\n\n    candidates = {}''',
)

replace_once(
    post,
    '''    all_variants = {}\n    view_records = []''',
    '''    all_variants = {}\n    masks = {}\n    view_records = []''',
)

replace_once(
    post,
    '''        candidate.save(output_dir / f"{asset_id}_{direction}.png")\n\n        candidates[direction] = candidate\n        pivots[direction] = pivot\n        all_variants[direction] = variants\n        view_records.append({\n            "direction": direction,\n            "quarterTurns": meta["quarterTurns"],\n            "rotationDegrees": meta["rotationDegrees"],\n            "file": f"{asset_id}_{direction}.png",\n            "colorPass": f"{asset_id}_{direction}_color_pass.png",\n            "shadowPass": f"{asset_id}_{direction}_shadow_pass.png",\n            "pivot": pivot,\n            "objectAlphaBounds": alpha_bounds(color_small),\n            "spriteAlphaBounds": alpha_bounds(candidate),\n        })''',
    '''        candidate.save(output_dir / f"{asset_id}_{direction}.png")\n\n        mask_small = None\n        if mask_enabled:\n            mask_source_name = meta.get("maskSource")\n            if not mask_source_name:\n                raise RuntimeError(f"Mask-enabled asset is missing maskSource for {direction}")\n            mask_source = Image.open(input_dir / mask_source_name).convert("RGBA")\n            if mask_source.size != color_source.size:\n                raise RuntimeError(\n                    f"Color/mask source size mismatch for {direction}: "\n                    f"{color_source.size} vs {mask_source.size}"\n                )\n            mask_small = downsample(mask_source)\n            mask_small.save(output_dir / f"{asset_id}_{direction}_mask.png")\n            masks[direction] = mask_small\n\n        candidates[direction] = candidate\n        pivots[direction] = pivot\n        all_variants[direction] = variants\n        view_record = {\n            "direction": direction,\n            "quarterTurns": meta["quarterTurns"],\n            "rotationDegrees": meta["rotationDegrees"],\n            "file": f"{asset_id}_{direction}.png",\n            "colorPass": f"{asset_id}_{direction}_color_pass.png",\n            "shadowPass": f"{asset_id}_{direction}_shadow_pass.png",\n            "pivot": pivot,\n            "objectAlphaBounds": alpha_bounds(color_small),\n            "spriteAlphaBounds": alpha_bounds(candidate),\n        }\n        if mask_small is not None:\n            view_record["maskPass"] = f"{asset_id}_{direction}_mask.png"\n            view_record["maskAlphaBounds"] = alpha_bounds(mask_small)\n        view_records.append(view_record)''',
)

replace_once(
    post,
    '''    context = make_context_board(candidates, pivots)\n    context.save(output_dir / f"{asset_id}_4dir_context.png")\n    context.save(output_dir / "tycoon_photo_studio_in_game_context.png")\n\n    manifest = {''',
    '''    context = make_context_board(candidates, pivots)\n    context.save(output_dir / f"{asset_id}_4dir_context.png")\n    context.save(output_dir / "tycoon_photo_studio_in_game_context.png")\n    if mask_enabled:\n        make_fixed_sheet(masks).save(output_dir / f"{asset_id}_mask_4view.png")\n        make_direction_review(\n            masks, pivots, "CH_COLOR_MASK_V1 - R/G/B semantic roles, alpha coverage"\n        ).save(output_dir / f"{asset_id}_mask_review.png")\n\n    manifest = {''',
)

replace_once(
    post,
    '''    manifest_text = json.dumps(manifest, indent=2)''',
    '''    if mask_enabled:\n        manifest["colorMask"] = {\n            **mask_meta,\n            "postProcess": "downsample_only_no_palette_no_dither",\n            "files": {\n                direction: f"{asset_id}_{direction}_mask.png"\n                for direction in DIRECTION_ORDER\n            },\n            "fourView": f"{asset_id}_mask_4view.png",\n            "review": f"{asset_id}_mask_review.png",\n        }\n        manifest["files"]["colorMask4View"] = f"{asset_id}_mask_4view.png"\n        manifest["files"]["colorMaskReview"] = f"{asset_id}_mask_review.png"\n\n    manifest_text = json.dumps(manifest, indent=2)''',
)

print("CH_COLOR_MASK_V1_PATCH_OK")
