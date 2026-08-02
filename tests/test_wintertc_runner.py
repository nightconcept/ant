#!/usr/bin/env python3
import json
import stat
import tempfile
import unittest
from pathlib import Path

from scripts import compliance_common


class WinterTCRunnerTests(unittest.TestCase):
    def test_wpt_revision_is_a_full_pinned_commit(self):
        self.assertRegex(compliance_common.pinned_wpt_revision(), r"^[0-9a-f]{40}$")

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "resources").mkdir()
        (self.root / "resources" / "testharness.js").write_text("// harness\n")
        (self.root / "common").mkdir()
        (self.root / "common" / "helper.js").write_text("const helperLoaded = true;\n")
        (self.root / "url").mkdir()
        (self.root / "streams").mkdir()
        (self.root / "url" / "basic.any.js").write_text(
            "// META: script=/common/helper.js\n"
            "test(() => assert_true(helperLoaded), 'helper');\n"
        )
        (self.root / "url" / "server.any.js").write_text("test(() => {}, 'server');\n")
        (self.root / "url" / "window.any.js").write_text(
            "// META: global=window\ntest(() => {}, 'window');\n"
        )
        (self.root / "url" / "support.js").write_text("throw new Error('not a test');\n")
        (self.root / "streams" / "basic.any.js").write_text("test(() => {}, 'stream');\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def write_manifest(self, value):
        path = self.root / "wintertc.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def manifest(self):
        return {
            "schema_version": 1,
            "includes": [
                {"pattern": "url/**/*.any.js", "category": "url"},
                {"pattern": "streams/**/*.any.js", "category": "streams"},
            ],
            "excludes": [
                {"pattern": "url/server.any.js", "reason": "server-required"},
                {"pattern": "url/window.any.js", "reason": "window-only"},
            ],
        }

    def test_manifest_selects_any_tests_and_applies_explained_exclusions(self):
        selected = compliance_common.discover_wpt_tests(
            self.root, self.write_manifest(self.manifest())
        )
        self.assertEqual(
            [(item.path.relative_to(self.root).as_posix(), item.category) for item in selected],
            [("streams/basic.any.js", "streams"), ("url/basic.any.js", "url")],
        )

    def test_manifest_rejects_an_unexplained_exclusion(self):
        value = self.manifest()
        value["excludes"][0].pop("reason")
        with self.assertRaisesRegex(compliance_common.WPTManifestError, "reason"):
            compliance_common.discover_wpt_tests(self.root, self.write_manifest(value))

    def test_manifest_rejects_selected_window_only_test(self):
        value = self.manifest()
        value["excludes"] = [value["excludes"][0]]
        with self.assertRaisesRegex(compliance_common.WPTManifestError, "global=window"):
            compliance_common.discover_wpt_tests(self.root, self.write_manifest(value))

    def test_manifest_fails_when_an_include_matches_nothing(self):
        value = self.manifest()
        value["includes"].append({"pattern": "missing/**/*.any.js", "category": "missing"})
        with self.assertRaisesRegex(compliance_common.WPTManifestError, "matched no files"):
            compliance_common.discover_wpt_tests(self.root, self.write_manifest(value))

    def test_prepare_wpt_code_resolves_meta_scripts_and_requires_completion(self):
        code = compliance_common.prepare_wpt_code(self.root / "url/basic.any.js", self.root)
        self.assertLess(code.index("globalThis.GLOBAL"), code.index("// harness"))
        self.assertLess(code.index("// harness"), code.index("const helperLoaded"))
        self.assertLess(code.index("const helperLoaded"), code.index("helperLoaded), 'helper'"))
        self.assertIn("globalThis.GLOBAL", code)
        self.assertIn("isWindow", code)
        self.assertIn("globalThis.location", code)
        self.assertIn(compliance_common.WPT_COMPLETION_MARKER, code)
        self.assertIn("add_completion_callback", code)

    def test_checked_in_manifest_classifies_server_backed_sources(self):
        manifest = json.loads(
            (compliance_common.REPO_ROOT / "tests/wintertc/wpt-manifest.json").read_text()
        )
        exclusions = {
            item["pattern"]: item["reason"] for item in manifest["excludes"]
        }
        for path in (
            "url/url-constructor.any.js",
            "url/url-setters.any.js",
            "fetch/api/request/request-bad-port.any.js",
            "fetch/api/response/response-blob-realm.any.js",
            "fetch/api/response/response-clone.any.js",
        ):
            self.assertIn(exclusions.get(path), {"server-required", "window-only"})

    def test_api_surface_checks_all_tc55_global_properties(self):
        contract = (
            compliance_common.REPO_ROOT / "tests/wintertc/api-surface.js"
        ).read_text()
        for name in (
            "onerror",
            "onunhandledrejection",
            "onrejectionhandled",
            "JSTag",
        ):
            self.assertIn(name, contract)

    def test_prepare_wpt_code_rejects_missing_meta_script(self):
        test = self.root / "url/missing.any.js"
        test.write_text("// META: script=/common/missing.js\ntest(() => {}, 'x');\n")
        with self.assertRaisesRegex(compliance_common.WPTManifestError, "META script"):
            compliance_common.prepare_wpt_code(test, self.root)

    def fake_engine(self, name, body):
        path = self.root / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_run_wpt_test_requires_completion_marker_and_cleans_scratch(self):
        engine = self.fake_engine("engine", "exit 0\n")
        passed, _, output = compliance_common.run_wpt_test(
            engine, self.root, self.root / "url/basic.any.js", 7
        )
        self.assertFalse(passed)
        self.assertIn("did not report completion", output)
        self.assertEqual(list((self.root / "url").glob("ant_wpt_tmp_*")), [])

    def test_run_wpt_test_accepts_successful_harness_completion(self):
        engine = self.fake_engine(
            "engine", f"echo {compliance_common.WPT_COMPLETION_MARKER}\nexit 0\n"
        )
        passed, _, _ = compliance_common.run_wpt_test(
            engine, self.root, self.root / "streams/basic.any.js", 8
        )
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()
