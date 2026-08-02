#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compliance_common import (
    WPT_TMP_PREFIX,
    discover_wpt_tests,
    ensure_wpt_repo,
    execute_prepared_wpt,
)
from scripts.run_compliance_wintertc import (
    API_SURFACE_PATH,
    MANIFEST_PATH,
    sweep_stale_wpt_files,
)

from compliance_common import MultiRuntimeTracker, make_log_path, run_js_test


def run_wintertc(
    runtimes: list[dict],
    filter_term: str | None = None,
    log_all: bool = False,
    log_fail: bool = False,
) -> dict:
    wpt_dir = ensure_wpt_repo()
    selected = discover_wpt_tests(wpt_dir, MANIFEST_PATH)
    if filter_term:
        needle = filter_term.lower()
        selected = [
            item for item in selected
            if needle in item.path.relative_to(wpt_dir).as_posix().lower()
        ]
    log_path = make_log_path("wintertc") if log_all or log_fail else None
    tracker = MultiRuntimeTracker(
        "WinterTC", runtimes, log_path=log_path, log_fail_only=log_fail and not log_all
    )

    if not filter_term or filter_term.lower() in "api-surface":
        results = {}
        for runtime in runtimes:
            passed, duration_ms, output = run_js_test(runtime, API_SURFACE_PATH)
            results[runtime["id"]] = {
                "passed": passed,
                "duration_ms": duration_ms,
                "details": output if not passed else "",
            }
        tracker.add_test("WinterTC: API surface", results)

    sweep_stale_wpt_files(wpt_dir)
    try:
        for sequence, item in enumerate(selected):
            name = f"WPT: {item.path.relative_to(wpt_dir).as_posix()}"
            results = {}
            for runtime_index, runtime in enumerate(runtimes):
                scratch = item.path.parent / (
                    f"{WPT_TMP_PREFIX}{sequence}_{runtime_index}_{item.path.name}"
                )
                passed, duration_ms, output = execute_prepared_wpt(
                    wpt_dir,
                    item.path,
                    scratch,
                    lambda path, runtime=runtime: run_js_test(runtime, path),
                )
                results[runtime["id"]] = {
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "details": output if not passed else "",
                }
            tracker.add_test(name, results)
    finally:
        sweep_stale_wpt_files(wpt_dir)
    return tracker.print_suite_summary()
