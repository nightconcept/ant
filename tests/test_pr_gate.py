#!/usr/bin/env python3
import os
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".github" / "agents" / "check_pr_gate.js"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-ci.yml"
BUILD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-platform.yml"
MAIN_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "main-ci.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


BASE_ENV = {
    "EVENT_NAME": "pull_request",
    "WORKFLOW_CHANGED": "false",
    "BUILD_CHANGED": "false",
    "RUNTIME_CHANGED": "false",
    "CLASSIFY_RESULT": "success",
    "REPO_RESULT": "success",
    "WORKFLOW_RESULT": "skipped",
    "BUILD_RESULT": "skipped",
    "WINTERTC_RESULT": "skipped",
    "REGRESSION_RESULT": "skipped",
    "TEST262_RESULT": "skipped",
}


class PullRequestGateTests(unittest.TestCase):
    def run_gate(self, **overrides):
        env = os.environ.copy()
        env.update(BASE_ENV)
        env.update({key: str(value).lower() for key, value in overrides.items()})
        return subprocess.run(
            ["node", str(SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_docs_only_gate_accepts_optional_skips(self):
        self.assertEqual(self.run_gate().returncode, 0)

    def test_runtime_gate_requires_build_wintertc_regression_and_test262(self):
        result = self.run_gate(
            BUILD_CHANGED=True,
            RUNTIME_CHANGED=True,
            BUILD_RESULT="success",
            WINTERTC_RESULT="success",
            REGRESSION_RESULT="success",
            TEST262_RESULT="success",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_gate_rejects_skipped_test262(self):
        result = self.run_gate(
            BUILD_CHANGED=True,
            RUNTIME_CHANGED=True,
            BUILD_RESULT="success",
            WINTERTC_RESULT="success",
            REGRESSION_RESULT="success",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test262", result.stderr)

    def test_build_gate_rejects_skipped_wintertc(self):
        result = self.run_gate(
            BUILD_CHANGED=True,
            BUILD_RESULT="success",
            REGRESSION_RESULT="success",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wintertc", result.stderr)

    def test_workflow_gate_rejects_failed_lint(self):
        result = self.run_gate(WORKFLOW_CHANGED=True, WORKFLOW_RESULT="failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("workflow-lint", result.stderr)

    def test_merge_group_always_requires_test262(self):
        result = self.run_gate(EVENT_NAME="merge_group")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test262", result.stderr)

    def test_aggregate_job_checks_out_its_gate_script(self):
        aggregate_job = WORKFLOW.read_text().split("\n  pr-gate:\n", 1)[1]
        checkout = aggregate_job.index("uses: actions/checkout@")
        execute = aggregate_job.index("run: node .github/agents/check_pr_gate.js")
        self.assertLess(checkout, execute)

    def test_wintertc_uses_exact_set_gate_not_platform_raw_exit(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("suite: wintertc", workflow)
        self.assertNotIn(
            "scripts/run_compliance.py --suite wintertc",
            BUILD_WORKFLOW.read_text(),
        )

    def test_main_and_release_gate_wintertc(self):
        self.assertIn("suite: wintertc", MAIN_WORKFLOW.read_text())
        release = RELEASE_WORKFLOW.read_text()
        self.assertIn("suite: wintertc", release)
        self.assertIn("compliance-wintertc", release)


if __name__ == "__main__":
    unittest.main()
