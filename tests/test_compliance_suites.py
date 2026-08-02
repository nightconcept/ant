#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import compliance_common
from scripts import run_compliance_regression
from scripts import run_compliance_test262


class NamedManifestTests(unittest.TestCase):
    def test_summary_tracker_writes_named_schema_two_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log_path = root / "wintertc_run.log"
            revision = {
                "commit": "a" * 40,
                "short": "aaaaaaaa",
                "dirty": False,
                "branch": "main",
                "subject": "synthetic",
            }
            with (
                mock.patch.object(compliance_common, "LOGS_DIR", root),
                mock.patch.object(compliance_common, "git_revision", return_value=revision),
            ):
                tracker = compliance_common.SummaryTracker(
                    "wintertc", "WinterTC", log_path=log_path
                )
                tracker.add("WPT: url/example.any.js", True, 1.0)
                self.assertEqual(tracker.print_summary(), 0)

            manifest = json.loads(log_path.with_suffix(".json").read_text())
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["suite_id"], "wintertc")
            self.assertEqual(manifest["suite"], "WinterTC")
            self.assertNotIn("tier", manifest)
            self.assertEqual(
                (root / "wintertc-latest.json").resolve(),
                log_path.with_suffix(".json"),
            )

    def test_orchestrator_exposes_named_suites_only(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_compliance.py", "--help"],
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--suite", result.stdout)
        self.assertIn("wintertc", result.stdout)
        self.assertIn("regression", result.stdout)
        self.assertIn("test262", result.stdout)
        self.assertNotIn("--" + "tier", result.stdout)

    def test_failure_parser_exposes_named_suites_only(self):
        result = subprocess.run(
            [
                sys.executable,
                ".agents/skills/compliance-failures/parse_failures.py",
                "--help",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--suite", result.stdout)
        self.assertNotIn("--" + "tier", result.stdout)

    def test_multi_runtime_orchestrator_loads_named_suites(self):
        result = subprocess.run(
            [sys.executable, "bench/compliance.py", "--help"],
            cwd=Path(__file__).resolve().parent.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--suite", result.stdout)
        self.assertIn("wintertc", result.stdout)
        self.assertNotIn("--smoke", result.stdout)

    def test_regression_baseline_recipe_requires_a_passing_run(self):
        justfile = (Path(__file__).resolve().parent.parent / "justfile").read_text()
        recipe = justfile.split("compliance-update-regression:", 1)[1].split(
            "compliance-update-test262:", 1
        )[0]
        self.assertNotIn("|| true", recipe)
        self.assertNotIn("--allow-failures", recipe)


class RegressionDiscoveryTests(unittest.TestCase):
    def test_discovers_both_internal_test_roots_with_stable_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tests").mkdir()
            (root / "examples/spec").mkdir(parents=True)
            for relative in [
                "tests/test_alpha.cjs",
                "tests/test_beta.mjs",
                "tests/helper.js",
                "examples/spec/arrays.js",
                "examples/spec/run.js",
                "examples/spec/helpers.js",
                "examples/spec/import_abs_target.js",
            ]:
                (root / relative).write_text("// fixture\n")

            discovered = run_compliance_regression.discover_regression_tests(root)
            self.assertEqual(
                [(item.name, item.category) for item in discovered],
                [
                    ("examples/spec/arrays.js", "Ant Regression: spec"),
                    ("tests/test_alpha.cjs", "Ant Regression: tests"),
                    ("tests/test_beta.mjs", "Ant Regression: tests"),
                ],
            )


class Test262DiscoveryTests(unittest.TestCase):
    def test_discovers_only_test262_sources_and_excludes_fixtures(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "test/built-ins/Array").mkdir(parents=True)
            for name in ["a.js", "b_FIXTURE.js", "ant_t262_tmp_1_old.js"]:
                (root / "test/built-ins/Array" / name).write_text("// fixture\n")
            selected = run_compliance_test262.discover_test262_tests(root)
            self.assertEqual(
                [path.relative_to(root / "test").as_posix() for path in selected],
                ["built-ins/Array/a.js"],
            )

    def test_test262_filter_and_limit_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "test/language").mkdir(parents=True)
            for name in ["b.js", "a.js", "c.js"]:
                (root / "test/language" / name).write_text("// fixture\n")
            selected = run_compliance_test262.discover_test262_tests(
                root, filter_value="language", limit=2
            )
            self.assertEqual([path.name for path in selected], ["a.js", "b.js"])


if __name__ == "__main__":
    unittest.main()
