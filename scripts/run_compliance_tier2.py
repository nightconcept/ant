#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from compliance_common import (
    find_ant_binary,
    run_js_test,
    SummaryTracker,
    fetch_pulled_test,
    PULLED_SMOKE_TESTS,
    make_log_path,
    REPO_ROOT
)

def main():
    parser = argparse.ArgumentParser(description="Run Tier 2 Compliance Tests (Node.js Compatibility Suite)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official Node.js online smoke test subset only")
    parser.add_argument("--all", action="store_true", help="Run all local Node module tests in tests/ (default behavior)")
    parser.add_argument("-m", "--module", type=str, help="Filter tests by module name (e.g. events, buffer, fs)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
    parser.add_argument("--log", action="store_true", help="Write all test output to a timestamped log file")
    parser.add_argument("--log-fail", action="store_true", help="Write only failing test output to a timestamped log file")
    args = parser.parse_args()

    ant_bin = find_ant_binary()

    filter_term = args.module or args.filter

    log_path = None
    if args.log or args.log_fail:
        log_path = make_log_path("tier2")

    tracker = SummaryTracker(
        "Tier 2 - Node.js Compatibility Suite",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
        filter=filter_term,
    )

    if args.smoke:
        print("Fetching and running Tier 2 pulled official Node.js tests (nodejs/node)...")
        specs = PULLED_SMOKE_TESTS["tier2"]
        if filter_term:
            specs = [s for s in specs if filter_term.lower() in s["name"].lower()]

        for spec in specs:
            test_path = fetch_pulled_test(spec)
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(spec["name"], passed, duration_ms, details=output if not passed else "")

    else:
        print("Running local Node module tests in tests/...")
        test_dir = REPO_ROOT / "tests"
        test_files = sorted(
            [f for f in test_dir.iterdir() if f.is_file() and f.name.startswith("test_") and f.suffix in (".cjs", ".js", ".mjs")]
        )

        if filter_term:
            test_files = [f for f in test_files if filter_term.lower() in f.name.lower()]

        for test_path in test_files:
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(test_path.name, passed, duration_ms, details=output if not passed else "")

    return tracker.print_summary()

if __name__ == "__main__":
    sys.exit(main())
