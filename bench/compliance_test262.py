#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compliance_common import ensure_test262_repo, prepare_test262_code
from scripts.run_compliance_test262 import (
    TMP_PREFIX,
    discover_test262_tests,
    sweep_stale_tmp,
)

from compliance_common import MultiRuntimeTracker, make_log_path, run_js_test


def run_test262(
    runtimes: list[dict],
    smoke: bool = False,
    filter_term: str | None = None,
    limit: int | None = None,
    log_all: bool = False,
    log_fail: bool = False,
) -> dict:
    del smoke
    test262_dir = ensure_test262_repo()
    selected = discover_test262_tests(test262_dir, filter_term, limit)
    log_path = make_log_path("test262") if log_all or log_fail else None
    tracker = MultiRuntimeTracker(
        "Test262", runtimes, log_path=log_path, log_fail_only=log_fail and not log_all
    )
    sweep_stale_tmp(test262_dir)
    try:
        for sequence, source in enumerate(selected):
            relative = source.relative_to(test262_dir / "test").as_posix()
            code, frontmatter = prepare_test262_code(source, test262_dir)
            results = {}
            for runtime_index, runtime in enumerate(runtimes):
                scratch = source.parent / (
                    f"{TMP_PREFIX}{sequence}_{runtime_index}_{source.name}"
                )
                try:
                    scratch.write_text(code, encoding="utf-8")
                    process_passed, duration_ms, output = run_js_test(
                        runtime, scratch, timeout_sec=5.0
                    )
                finally:
                    try:
                        scratch.unlink()
                    except OSError:
                        pass
                passed = (
                    not process_passed
                    if frontmatter.get("negative") is not None
                    else process_passed
                )
                results[runtime["id"]] = {
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "details": output if not passed else "",
                }
            tracker.add_test(f"Test262: {relative}", results)
    finally:
        sweep_stale_tmp(test262_dir)
    return tracker.print_suite_summary()
