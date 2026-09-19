"""
CH_MASK_V1 Mask System Test Suite.
Verifies contract rules, fail-closed validations, linear RGB shading, byte-identical alpha preservation,
unmasked pixel preservation, texture mode sampling, and SHA-256 output reproducibility.
Pure PIL / Standard Python implementation.
"""

import unittest
import os
import shutil
import json
import tempfile
from PIL import Image

from tools.asset_masks.mask_contract import (
    MaskAssetManifest, VariantConfig, SidecarMetadata,
    kMaskContract, compute_file_sha256
)
from tools.asset_masks.validate_mask_asset import validate_mask_asset, MaskValidationError
from tools.asset_masks.apply_mask_variant import apply_variant_to_image, process_mask_manifest


class TestMaskSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.w, self.h = 32, 32
        num_pixels = self.w * self.h

        # Create dummy base image (RGBA): top half opaque plaster wall, bottom half transparent
        base_bytes = bytearray(num_pixels * 4)
        for y in range(self.h):
            for x in range(self.w):
                offset = (y * self.w + x) * 4
                if y < 16:
                    base_bytes[offset] = 200     # R
                    base_bytes[offset + 1] = 190 # G
                    base_bytes[offset + 2] = 180 # B
                    base_bytes[offset + 3] = 255 # Alpha
                else:
                    base_bytes[offset + 3] = 0   # Transparent

        self.base_path = os.path.join(self.test_dir, "test_base.png")
        Image.frombytes("RGBA", (self.w, self.h), bytes(base_bytes)).save(self.base_path)

        # Create valid 8-bit grayscale region mask (mode: "L")
        # ID 0 = unmasked, ID 1 = wall (left top), ID 2 = roof (right top)
        mask_bytes = bytearray(num_pixels)
        for y in range(16):
            for x in range(self.w):
                idx = y * self.w + x
                if x < 16:
                    mask_bytes[idx] = 1 # wall
                else:
                    mask_bytes[idx] = 2 # roof

        self.mask_path = os.path.join(self.test_dir, "test_semantic_mask.png")
        Image.frombytes("L", (self.w, self.h), bytes(mask_bytes)).save(self.mask_path)

        # Create seamless material texture for testing texture mode (16x16 RGB)
        mat_bytes = bytearray(16 * 16 * 3)
        for i in range(16 * 16):
            mat_bytes[i * 3] = 120
            mat_bytes[i * 3 + 1] = 140
            mat_bytes[i * 3 + 2] = 160
        self.material_path = os.path.join(self.test_dir, "test_material.png")
        Image.frombytes("RGB", (16, 16), bytes(mat_bytes)).save(self.material_path)

        # Create valid manifest
        self.manifest_dict = {
            "contract": "CH_MASK_V1",
            "assetId": "test_building",
            "base": "test_base.png",
            "semanticMask": "test_semantic_mask.png",
            "regions": {
                "wall": 1,
                "roof": 2
            },
            "variants": [
                {
                    "id": "recolor_test",
                    "region_recipes": {
                        "wall": {
                            "mode": "recolor",
                            "targetRGB": [100, 150, 220]
                        },
                        "roof": {
                            "mode": "recolor",
                            "targetRGB": [220, 100, 100]
                        }
                    },
                    "wear": 0.10
                },
                {
                    "id": "texture_test",
                    "region_recipes": {
                        "wall": {
                            "mode": "texture",
                            "texture": "test_material.png",
                            "preserveShading": True
                        }
                    }
                }
            ]
        }
        self.manifest_path = os.path.join(self.test_dir, "test_variants.json")
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest_dict, f, indent=2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_contracts_and_manifest(self):
        manifest = MaskAssetManifest.from_dict(self.manifest_dict, self.test_dir)
        self.assertEqual(manifest.contract, kMaskContract)
        self.assertEqual(manifest.asset_id, "test_building")
        self.assertEqual(len(manifest.variants), 2)
        self.assertEqual(manifest.regions["wall"], 1)

    def test_02_dimension_mismatch_fails(self):
        # Create mask with wrong dimensions (16x16 instead of 32x32)
        bad_mask = Image.new("L", (16, 16), 0)
        bad_mask.save(self.mask_path)

        manifest = MaskAssetManifest.from_dict(self.manifest_dict, self.test_dir)
        with self.assertRaises(MaskValidationError) as ctx:
            validate_mask_asset(manifest)
        self.assertIn("Dimension mismatch", str(ctx.exception))

    def test_03_unmapped_region_id_fails(self):
        # Place undeclared region ID 99 at pixel (0, 0)
        mask_img = Image.open(self.mask_path)
        mask_bytes = bytearray(mask_img.tobytes())
        mask_bytes[0] = 99
        Image.frombytes("L", mask_img.size, bytes(mask_bytes)).save(self.mask_path)

        manifest = MaskAssetManifest.from_dict(self.manifest_dict, self.test_dir)
        with self.assertRaises(MaskValidationError) as ctx:
            validate_mask_asset(manifest)
        self.assertIn("Undeclared region ID 99", str(ctx.exception))

    def test_04_mask_on_transparent_alpha_fails(self):
        # Place active region ID on bottom half where base alpha == 0
        mask_img = Image.open(self.mask_path)
        mask_bytes = bytearray(mask_img.tobytes())
        offset = 20 * self.w + 5
        mask_bytes[offset] = 1 # Active wall region on transparent pixel
        Image.frombytes("L", mask_img.size, bytes(mask_bytes)).save(self.mask_path)

        manifest = MaskAssetManifest.from_dict(self.manifest_dict, self.test_dir)
        with self.assertRaises(MaskValidationError) as ctx:
            validate_mask_asset(manifest)
        self.assertIn("transparent base alpha", str(ctx.exception))

    def test_05_alpha_preservation_byte_identical(self):
        out_dir = os.path.join(self.test_dir, "out")
        generated_pngs, _ = process_mask_manifest(self.manifest_path, out_dir)

        base_bytes = Image.open(self.base_path).tobytes()
        out_bytes = Image.open(generated_pngs[0]).tobytes()

        base_alphas = [base_bytes[i*4 + 3] for i in range(self.w * self.h)]
        out_alphas = [out_bytes[i*4 + 3] for i in range(self.w * self.h)]

        self.assertEqual(out_alphas, base_alphas, "Output alpha is not byte-identical to base alpha")

    def test_06_unmasked_pixels_byte_identical(self):
        out_dir = os.path.join(self.test_dir, "out")
        generated_pngs, _ = process_mask_manifest(self.manifest_path, out_dir)

        base_bytes = Image.open(self.base_path).tobytes()
        out_bytes = Image.open(generated_pngs[0]).tobytes()
        mask_bytes = Image.open(self.mask_path).tobytes()

        for i in range(self.w * self.h):
            offset = i * 4
            region_id = mask_bytes[i]

            if region_id == 0:
                self.assertEqual(out_bytes[offset], base_bytes[offset])
                self.assertEqual(out_bytes[offset + 1], base_bytes[offset + 1])
                self.assertEqual(out_bytes[offset + 2], base_bytes[offset + 2])
                self.assertEqual(out_bytes[offset + 3], base_bytes[offset + 3])

    def test_07_deterministic_sha256(self):
        out_dir1 = os.path.join(self.test_dir, "out1")
        out_dir2 = os.path.join(self.test_dir, "out2")

        pngs1, _ = process_mask_manifest(self.manifest_path, out_dir1)
        pngs2, _ = process_mask_manifest(self.manifest_path, out_dir2)

        hash1 = compute_file_sha256(pngs1[0])
        hash2 = compute_file_sha256(pngs2[0])

        self.assertEqual(hash1, hash2, "SHA-256 hashes differ across executions for identical inputs")

    def test_08_texture_mode_and_sidecar(self):
        out_dir = os.path.join(self.test_dir, "out_tex")
        pngs, sidecars = process_mask_manifest(self.manifest_path, out_dir)
        self.assertEqual(len(pngs), 2)
        self.assertEqual(len(sidecars), 2)

        # Check sidecar content for variant 2 (texture mode)
        with open(sidecars[1], "r", encoding="utf-8") as f:
            sc_data = json.load(f)

        self.assertEqual(sc_data["variantId"], "texture_test")
        self.assertIn("material_sha256", sc_data)
        self.assertEqual(sc_data["material_sha256"], compute_file_sha256(self.material_path))


if __name__ == "__main__":
    unittest.main()
