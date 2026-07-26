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
    REPO_ROOT
)

def main():
    parser = argparse.ArgumentParser(description="Run Tier 1 Compliance Tests (WinterTC / Edge Baseline & Core JS)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset")
    parser.add_argument("--all", action="store_true", help="Run all local Tier 1 spec tests")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
    args = parser.parse_args()

    ant_bin = find_ant_binary()
    tracker = SummaryTracker("Tier 1 - WinterTC / Edge Baseline & Core JS")

    if args.smoke or not args.all:
        print("Fetching and running Tier 1 pulled official online tests (Test262 / WPT)...")
        specs = PULLED_SMOKE_TESTS["tier1"]
        if args.filter:
            specs = [s for s in specs if args.filter.lower() in s["name"].lower()]

        for spec in specs:
            test_path = fetch_pulled_test(spec)
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(spec["name"], passed, duration_ms, details=output if not passed else "")

    else:
        print("Running local Tier 1 spec files in examples/spec/...")
        spec_dir = REPO_ROOT / "examples" / "spec"
        spec_files = sorted([f for f in spec_dir.glob("*.js") if f.name != "run.js"])

        if args.filter:
            spec_files = [f for f in spec_files if args.filter.lower() in f.name.lower()]

        for test_path in spec_files:
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(test_path.name, passed, duration_ms, details=output if not passed else "")

    return tracker.print_summary()

if __name__ == "__main__":
    sys.exit(main())
