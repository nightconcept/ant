#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".github" / "agents" / "classify_changes.js"


class ClassifyChangesTests(unittest.TestCase):
    def classify(self, *files):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("\n".join(files))
            handle.write("\n")
            path = Path(handle.name)
        try:
            result = subprocess.run(
                ["node", str(SCRIPT), "--files-from", str(path), "--json"],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_docs_only_uses_repository_checks_only(self):
        result = self.classify("docs/repo/testing.md", "README.md")
        self.assertTrue(result["docs_only"])
        self.assertFalse(result["build_changed"])
        self.assertFalse(result["runtime_changed"])

    def test_runtime_module_requires_build_compliance_and_performance_evidence(self):
        result = self.classify("src/modules/iterator.c")
        self.assertFalse(result["docs_only"])
        self.assertTrue(result["build_changed"])
        self.assertTrue(result["runtime_changed"])
        self.assertTrue(result["performance_sensitive"])

    def test_workflow_change_is_not_docs_only(self):
        result = self.classify(".github/workflows/pr-ci.yml")
        self.assertTrue(result["workflow_changed"])
        self.assertTrue(result["build_changed"])
        self.assertFalse(result["runtime_changed"])

    def test_unknown_file_falls_back_to_full_gate(self):
        result = self.classify("new-unclassified-input.xyz")
        self.assertFalse(result["docs_only"])
        self.assertTrue(result["build_changed"])
        self.assertTrue(result["runtime_changed"])
        self.assertTrue(result["performance_sensitive"])


if __name__ == "__main__":
    unittest.main()
