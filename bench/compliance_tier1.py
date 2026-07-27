#!/usr/bin/env python3
from __future__ import annotations
import sys
import argparse
from pathlib import Path
from compliance_common import (
    load_runtimes,
    run_js_test,
    MultiRuntimeTracker,
    fetch_pulled_test,
    PULLED_SMOKE_TESTS,
    make_log_path,
    REPO_ROOT
)

TIER1_SPEC_FILES = [
    "ant.js", "arrays.js", "arrow.js", "async.js", "async_iterators.js", "async_loops.js",
    "atomics.js", "bigint.js", "class_computed_key.js", "classes.js", "completion.js", "dataview.js",
    "date.js", "delete.js", "destructuring.js", "devirtualization.js", "escapes.js",
    "exceptions.js", "forin.js", "functions.js", "generators.js", "getters.js",
    "globalthis.js", "iterators.js", "json.js", "loops.js", "map.js",
    "match.js", "math.js", "modules.js", "numbers.js", "objects.js", "operators.js",
    "optional_chaining.js", "private_classes.js", "promise.js", "proxy.js", "reflect.js",
    "regexp.js", "set.js", "spread.js", "strings.js", "switch.js",
    "symbols.js", "tco.js", "tco_brackets.js", "tco_shift.js", "throw_expressions.js",
    "typeof.js", "uri.js", "weakmap.js", "weakref.js", "weakset.js"
]

def run_tier1(runtimes: list[dict], smoke: bool = False, filter_term: str | None = None, log_all: bool = False, log_fail: bool = False) -> dict:
    log_path = make_log_path("tier1") if (log_all or log_fail) else None

    tracker = MultiRuntimeTracker(
        "Tier 1 - WinterTC / Edge Baseline & Core JS",
        runtimes=runtimes,
        log_path=log_path,
        log_fail_only=log_fail and not log_all,
    )

    if smoke:
        print("\n=== Executing Tier 1 Smoke Tests (WinterTC / Edge Baseline) ===")
        specs = PULLED_SMOKE_TESTS["tier1"]
        if filter_term:
            specs = [s for s in specs if filter_term.lower() in s["name"].lower()]

        for spec in specs:
            test_path = fetch_pulled_test(spec)
            results_by_runtime = {}
            for r in runtimes:
                passed, duration_ms, output = run_js_test(r, test_path)
                results_by_runtime[r["id"]] = {
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "details": output if not passed else ""
                }
            tracker.add_test(spec["name"], results_by_runtime)

    else:
        print("\n=== Executing Tier 1 Full Suite (WinterTC / Edge Baseline & Core JS) ===")
        spec_dir = REPO_ROOT / "examples" / "spec"
        spec_files = sorted([spec_dir / f for f in TIER1_SPEC_FILES if (spec_dir / f).exists()])
        if filter_term:
            spec_files = [f for f in spec_files if filter_term.lower() in f.name.lower()]

        for test_path in spec_files:
            results_by_runtime = {}
            for r in runtimes:
                passed, duration_ms, output = run_js_test(r, test_path)
                results_by_runtime[r["id"]] = {
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "details": output if not passed else ""
                }
            tracker.add_test(test_path.name, results_by_runtime)

    return tracker.print_tier_summary()

def main():
    parser = argparse.ArgumentParser(description="Run Tier 1 Compliance Tests (WinterTC / Edge Baseline & Core JS)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset")
    parser.add_argument("--all", action="store_true", default=True, help="Run full local Tier 1 spec tests (default)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
    parser.add_argument("--runtimes", type=str, help="Comma-separated runtime IDs to execute")
    parser.add_argument("--log", action="store_true", help="Write test output to log file")
    parser.add_argument("--log-fail", action="store_true", help="Write failing test output to log file")
    args = parser.parse_args()

    filter_ids = args.runtimes.split(",") if args.runtimes else None
    runtimes = load_runtimes(filter_ids=filter_ids)
    if not runtimes:
        print("No valid runtimes available.")
        sys.exit(1)

    smoke = args.smoke
    run_tier1(runtimes, smoke=smoke, filter_term=args.filter, log_all=args.log, log_fail=args.log_fail)

if __name__ == "__main__":
    main()
