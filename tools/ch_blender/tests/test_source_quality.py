"""Source-file and animation package regressions; no Blender process is needed."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools/tycoon_photo_studio'), str(ROOT / 'tools/ch_blender')]
from source_validation import validate_sources
import postprocess
import postprocess_character
from agent_worker import validate_job, WorkerError, _canonical_bake
from validate_character import validate_png


class SourceQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.preset = json.loads((ROOT / 'tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json').read_text())
        self.metadata = {'contract': 'TYCOON_ASSET_BAKE_V1', 'studioPreset': self.preset['id'],
                         'renderResolution': [64, 32], 'finalResolution': [32, 16],
                         'directionOrder': ['south', 'east', 'west', 'north'], 'directions': []}
        for direction in self.metadata['directionOrder']:
            record = {'id': direction, 'groundOriginSourcePx': {'x': 32, 'y': 24},
                      'colorSource': direction + '_color.png', 'shadowSource': direction + '_shadow.png'}
            Image.new('RGBA', (64, 32), (90, 100, 110, 255)).save(self.directory / record['colorSource'])
            Image.new('RGBA', (64, 32)).save(self.directory / record['shadowSource'])
            self.metadata['directions'].append(record)

    def check(self):
        return validate_sources(self.directory, self.metadata, self.preset)

    def test_empty_shadows_allowed_but_empty_asset_rejected(self):
        self.assertEqual(self.check(), (32, 16))
        Image.new('RGBA', (64, 32)).save(self.directory / 'south_color.png')
        with self.assertRaisesRegex(ValueError, 'no visible asset'):
            self.check()

    def test_wrong_actual_size_and_missing_alpha_rejected(self):
        for mode, size in [('RGBA', (32, 32)), ('RGB', (64, 32))]:
            Image.new(mode, size).save(self.directory / 'south_shadow.png')
            with self.assertRaisesRegex(ValueError, 'RGBA PNG of declared size'):
                self.check()

    def test_character_frame_validator_rejects_rgb_and_wrong_size(self):
        path = self.directory / 'south_color.png'
        validate_png(path, (64, 32))
        with self.assertRaisesRegex(RuntimeError, 'size differs'):
            validate_png(path, (64, 64))
        Image.new('RGB', (64, 32)).save(path)
        with self.assertRaisesRegex(RuntimeError, 'RGBA'):
            validate_png(path, (64, 32))

    def test_duplicate_direction_and_reused_pass_rejected(self):
        self.metadata['directions'][1]['id'] = 'south'
        with self.assertRaisesRegex(ValueError, 'order exactly'):
            self.check()
        self.metadata['directions'][1]['id'] = 'east'
        self.metadata['directions'][1]['colorSource'] = 'south_color.png'
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.check()

    def test_nonfinite_pivot_and_source_outside_directory_rejected(self):
        self.metadata['directions'][0]['groundOriginSourcePx']['x'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.check()
        self.metadata['directions'][0]['groundOriginSourcePx']['x'] = 32
        self.metadata['directions'][0]['colorSource'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, 'inside'):
            self.check()

    def test_fixed_sheet_uses_actual_large_rectangular_frames(self):
        image = Image.new('RGBA', (768, 384), (0, 0, 0, 0))
        image.putpixel((767, 383), (255, 0, 255, 255))
        candidates = {d: image for d in self.metadata['directionOrder']}
        with patch.object(postprocess, 'FINAL_SIZE', (256, 256)):
            sheet = postprocess.make_fixed_sheet(candidates)
        self.assertEqual(sheet.size, (3072, 384))
        self.assertEqual(sheet.getpixel((3071, 383)), (255, 0, 255, 255))

    def test_sequence_review_preserves_rectangular_aspect(self):
        image = Image.new('RGBA', (200, 100), (255, 0, 255, 255))
        board = postprocess_character.make_sequence_review({'n': [image]}, ['n'], 1)
        colors = board.getcolors(board.width * board.height)
        self.assertEqual(dict((color, count) for count, color in colors).get((255, 0, 255, 255)), 128 * 64)

    def test_character_roundtrip_keeps_dynamic_size_and_truthful_color_metadata(self):
        metadata = copy.deepcopy(self.metadata)
        metadata.update(contract='TYCOON_CHARACTER_BAKE_V1', sourceObject='test_character', footprint={'widthTiles': 1, 'depthTiles': 1},
                        animation={'id': 'walk', 'frameCount': 2}, directionOrder=['n', 's'], directions=[])
        for direction in ('n', 's'):
            frames = []
            for frame in range(2):
                record = {'frame': frame, 'phase': frame / 2, 'groundOriginSourcePx': {'x': 32, 'y': 24},
                          'colorSource': f'{direction}_{frame}_color.png', 'shadowSource': f'{direction}_{frame}_shadow.png'}
                Image.new('RGBA', (64, 32), (90 + frame, 110, 120, 255)).save(self.directory / record['colorSource'])
                Image.new('RGBA', (64, 32)).save(self.directory / record['shadowSource'])
                frames.append(record)
            metadata['directions'].append({'id': direction, 'rotationDegrees': 0, 'frames': frames})
        wrong = copy.deepcopy(metadata)
        wrong['directions'][0]['frames'][1]['frame'] = 0
        with self.assertRaisesRegex(ValueError, 'duplicated or reordered'):
            validate_sources(self.directory, wrong, self.preset, character=True)
        (self.directory / 'character_studio_metadata.json').write_text(json.dumps(metadata))
        preset_path = self.directory / 'preset.json'
        preset_path.write_text(json.dumps(self.preset))
        out = self.directory / 'final'
        command = [sys.executable, str(ROOT / 'tools/tycoon_photo_studio/postprocess_character.py'),
                   '--input', str(self.directory), '--output', str(out), '--studio-preset', str(preset_path)]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        manifest = json.loads((out / 'test_character_manifest.json').read_text())
        self.assertEqual(manifest['finalFrameResolution'], [32, 16])
        self.assertEqual(manifest['candidatePostProcess']['mode'], 'full_rgba')
        self.assertEqual(manifest['candidatePostProcess']['dither'], 'none')
        with Image.open(out / manifest['files']['spriteSheet']) as image:
            self.assertEqual(image.size, (64, 32))

    def test_canonical_job_rejects_bad_input_before_blender_and_missing_output_after(self):
        asset = self.directory / 'asset.json'
        asset.write_text(json.dumps({'contract': 'TYCOON_ASSET_SOURCE_V1', 'assetId': ''}))
        job = {'contract': 'CH_BLENDER_AGENT_JOB_V1', 'jobId': 'test.canonical', 'operation': 'canonical_bake',
               'assetConfig': str(asset), 'outputDir': str(self.directory / 'output'), 'postprocess': False}
        path = self.directory / 'job.json'
        path.write_text(json.dumps(job))
        with self.assertRaisesRegex(WorkerError, 'assetId'):
            validate_job(path)
        asset.write_text(json.dumps({'contract': 'TYCOON_ASSET_SOURCE_V1', 'assetId': 'valid'}))
        with patch('agent_worker._run'):
            with self.assertRaisesRegex(WorkerError, 'not produced'):
                _canonical_bake(job, Path('/not-used/blender'), 0)


if __name__ == '__main__':
    unittest.main()
