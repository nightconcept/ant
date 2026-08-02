#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_compliance_regression import discover_regression_tests

from compliance_common import MultiRuntimeTracker, make_log_path, run_js_test


def run_regression(
    runtimes: list[dict],
    smoke: bool = False,
    filter_term: str | None = None,
    log_all: bool = False,
    log_fail: bool = False,
) -> dict:
    del smoke
    selected = discover_regression_tests(REPO_ROOT)
    if filter_term:
        selected = [item for item in selected if filter_term.lower() in item.name.lower()]
    log_path = make_log_path("regression") if log_all or log_fail else None
    tracker = MultiRuntimeTracker(
        "Ant Regression", runtimes, log_path=log_path, log_fail_only=log_fail and not log_all
    )
    for item in selected:
        results = {}
        for runtime in runtimes:
            passed, duration_ms, output = run_js_test(runtime, item.path)
            results[runtime["id"]] = {
                "passed": passed,
                "duration_ms": duration_ms,
                "details": output if not passed else "",
            }
        tracker.add_test(item.name, results)
    return tracker.print_suite_summary()
