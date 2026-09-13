import bpy
import json
import os

fbx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'input', 'mixamo_walk_test.fbx'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=True)
report = {}
for material in bpy.data.materials:
    report[material.name] = {
        'use_nodes': material.use_nodes,
        'nodes': [node.type for node in material.node_tree.nodes] if material.use_nodes else [],
        'image_nodes': [node.image.filepath if node.image else None for node in material.node_tree.nodes if node.type == 'TEX_IMAGE'] if material.use_nodes else [],
        'diffuse_color': list(material.diffuse_color),
    }
print('MATERIAL_REPORT=' + json.dumps(report, indent=2))
