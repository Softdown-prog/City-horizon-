"""Output-path guards for the Map Forge worker and CLI (no native core required)."""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

try:  # The guards run before native use; stub the compiled core only when it is unavailable.
    import city_horizon_native  # noqa: F401
except ImportError:
    sys.modules["city_horizon_native"] = mock.MagicMock()

from tools.map_forge import cli, scenario_worker  # noqa: E402


class WorkerGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.scenarios = self.root / "assets" / "scenarios"
        self.scenarios.mkdir(parents=True)
        self.source = self.scenarios / "initial_city.json"
        self.source.write_text("{}", encoding="utf-8")

    def test_source_is_never_overwritten_even_with_overwrite(self):
        with self.assertRaisesRegex(ValueError, "source scenario"):
            scenario_worker.run_worker(self.root, self.source, "beach_water_v2",
                                       "initial_city.json", overwrite=True)
        self.assertEqual(self.source.read_text(encoding="utf-8"), "{}")

    def test_existing_scenario_requires_overwrite(self):
        (self.scenarios / "other.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            scenario_worker.run_worker(self.root, self.source, "beach_water_v2", "other.json")

    def test_main_reports_refusal_as_json(self):
        argv = ["worker", "--asset-root", str(self.root), "--recipe", "beach_water_v2",
                "--scenario-id", "initial_city.json", "--overwrite"]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as raised:
                scenario_worker.main()
        self.assertEqual(raised.exception.code, 1)
        report = json.loads(out.getvalue())
        self.assertFalse(report["success"])
        self.assertEqual(report["error"]["type"], "ValueError")


class CliGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source.json"
        self.source.write_text("{}", encoding="utf-8")

    def run_generate(self, output, **extra):
        args = argparse.Namespace(action="generate-coastal-district", output=str(output), **extra)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.run_cli(args, str(self.root), str(self.source))
        return json.loads(out.getvalue())

    def test_output_equal_to_source_is_rejected(self):
        result = self.run_generate(self.source, overwrite=True)
        self.assertFalse(result["success"])
        self.assertIn("source scenario", result["error"])
        self.assertEqual(self.source.read_text(encoding="utf-8"), "{}")

    def test_existing_output_requires_overwrite(self):
        existing = self.root / "existing.json"
        existing.write_text("keep", encoding="utf-8")
        result = self.run_generate(existing)
        self.assertFalse(result["success"])
        self.assertIn("--overwrite", result["error"])
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
