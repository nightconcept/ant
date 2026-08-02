import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compliance_common.py"
SPEC = importlib.util.spec_from_file_location("compliance_common_under_test", MODULE_PATH)
compliance_common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compliance_common)


class Test262PinTests(unittest.TestCase):
    def test_pin_requires_full_commit_sha(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            versions = Path(temp_dir) / "versions.json"
            versions.write_text(json.dumps({"dependencies": {"test262": "main"}}))
            with mock.patch.object(compliance_common, "VERSIONS_FILE", versions):
                with self.assertRaisesRegex(RuntimeError, "full commit SHA"):
                    compliance_common.pinned_test262_revision()

    def test_matching_checkout_does_not_fetch(self):
        revision = "a" * 40
        completed = mock.Mock(stdout=f"{revision}\n")
        with mock.patch.object(compliance_common.subprocess, "run", return_value=completed) as run:
            compliance_common.checkout_test262_revision(Path("/tmp/test262"), revision)
        run.assert_called_once()

    def test_mismatched_checkout_fetches_and_detaches_pin(self):
        revision = "b" * 40
        completed = mock.Mock(stdout=f"{'a' * 40}\n")
        with mock.patch.object(compliance_common.subprocess, "run", return_value=completed) as run:
            compliance_common.checkout_test262_revision(Path("/tmp/test262"), revision)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[1].args[0][-2:], ["origin", revision])
        self.assertEqual(run.call_args_list[2].args[0][-2:], ["--detach", revision])


if __name__ == "__main__":
    unittest.main()
