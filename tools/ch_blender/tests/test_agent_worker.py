"""Fast CH Blender agent-contract checks; Blender is deliberately unnecessary."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/ch_blender"))
from agent_worker import WorkerError, validate_job  # noqa: E402


class JobValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.job_path = Path(self.tmp.name) / "example.job.json"
        self.job = {
            "contract": "CH_BLENDER_AGENT_JOB_V1",
            "jobId": "example.proxy.001",
            "operation": "guarded_blender_script",
            "script": "tools/tycoon_photo_studio/build_small_commercial_guarded.py",
            "qualityStage": "proxy",
            "outputDir": "out/ch_blender_agent/example",
            "args": ["--output", "out/ch_blender_agent/example"],
        }

    def check(self):
        self.job_path.write_text(json.dumps(self.job), encoding="utf-8")
        return validate_job(self.job_path)

    def test_existing_repository_jobs(self):
        paths = list((ROOT / "tools/ch_blender/jobs").glob("*.job.json"))
        paths += list((ROOT / "tools/ch_blender/jobs_ground").glob("*.ground.job.json"))
        self.assertGreater(len(paths), 50)
        for path in paths:
            with self.subTest(job=path.name):
                validate_job(path)

    def test_valid_guarded_job_does_not_render_or_create_output(self):
        self.assertEqual(self.check()["jobId"], "example.proxy.001")
        self.assertFalse((ROOT / "out/ch_blender_agent/example").exists())

    def test_output_mismatch_rejected_before_blender(self):
        self.job["args"][-1] = "out/ch_blender_agent/other"
        with self.assertRaisesRegex(WorkerError, "must match"):
            self.check()

    def test_reserved_quality_flag_rejected_in_equals_form(self):
        self.job["args"].append("--stage=final")
        with self.assertRaisesRegex(WorkerError, "owned by"):
            self.check()

    def test_unsafe_job_id_and_output_path_rejected(self):
        self.job["jobId"] = "../escape"
        with self.assertRaises(WorkerError) as error:
            self.check()
        self.assertEqual(error.exception.code, "JOB_INVALID")
        self.job["jobId"] = "example.proxy.001"
        self.job["outputDir"] = "../outside"
        with self.assertRaises(WorkerError) as error:
            self.check()
        self.assertEqual(error.exception.code, "JOB_INVALID")

    def test_cli_reports_job_error_even_without_blender(self):
        self.job["args"][-1] = "out/ch_blender_agent/other"
        self.job_path.write_text(json.dumps(self.job), encoding="utf-8")
        cli = ROOT / "tools/ch_blender/ch_blender_cli.py"
        command = [sys.executable, str(cli), "run-job", "--job", str(self.job_path),
                   "--blender", "/definitely/missing/blender"]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 10)
        self.assertEqual(json.loads(completed.stdout)["error"]["code"], "JOB_INVALID")


if __name__ == "__main__":
    unittest.main()
