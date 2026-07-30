#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "compliance_baseline.py"
COMMIT = "a" * 40


def manifest(*, failing=(), filter_value=None, commit=COMMIT, branch="dev", dirty=False):
    failing = list(failing)
    total = 2
    return {
        "schema_version": 1,
        "suite": "Synthetic",
        "tier": 2,
        "filter": filter_value,
        "revision": {
            "commit": commit,
            "short": commit[:8],
            "dirty": dirty,
            "branch": branch,
            "subject": "synthetic",
        },
        "totals": {
            "total": total,
            "passed": total - len(failing),
            "failed": len(failing),
            "pass_rate": 100.0 * (total - len(failing)) / total,
        },
        "categories": {
            "synthetic": {
                "total": total,
                "passed": total - len(failing),
                "failed": len(failing),
                "failing": failing,
            }
        },
    }


class ComplianceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.baseline_path = self.root / "baseline.json"
        self.manifest_path = self.root / "manifest.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def run_diff(self, current, *args):
        self.write_json(self.manifest_path, current)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "diff",
                str(self.manifest_path),
                "--baseline",
                str(self.baseline_path),
                *args,
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def seed(self, baseline_manifest):
        self.write_json(
            self.baseline_path,
            {"schema_version": 1, "tiers": {"2": baseline_manifest}},
        )

    def test_equal_total_pass_fail_swap_is_a_regression(self):
        self.seed(manifest(failing=["old-failure"]))
        result = self.run_diff(manifest(failing=["new-failure"]), "--require-baseline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("new-failure", result.stdout)
        self.assertIn("old-failure", result.stdout)

    def test_required_baseline_must_exist(self):
        result = self.run_diff(manifest(), "--require-baseline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no baseline recorded", result.stderr)

    def test_required_baseline_must_be_full_and_clean(self):
        self.seed(manifest(filter_value="slice", dirty=True))
        result = self.run_diff(manifest(), "--require-baseline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial", result.stderr)
        self.assertIn("dirty", result.stderr)

    def test_required_full_manifest_rejects_filter(self):
        self.seed(manifest())
        result = self.run_diff(
            manifest(filter_value="slice"),
            "--require-baseline",
            "--require-full",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("partial", result.stderr)

    def test_expected_revision_and_branch_are_exact(self):
        self.seed(manifest())
        result = self.run_diff(
            manifest(commit="b" * 40, branch="main"),
            "--require-baseline",
            "--require-full",
            "--expect-commit",
            COMMIT,
            "--expect-branch",
            "dev",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match expected", result.stderr)

    def test_expected_revision_rejects_dirty_manifest(self):
        self.seed(manifest())
        result = self.run_diff(
            manifest(dirty=True),
            "--require-baseline",
            "--expect-commit",
            COMMIT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty working tree", result.stderr)

    def test_missing_manifest_fails_closed(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "diff",
                str(self.root / "missing.json"),
                "--baseline",
                str(self.baseline_path),
                "--require-baseline",
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
