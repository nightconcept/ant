#!/usr/bin/env python3
import sys
import time
import subprocess
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
    parser = argparse.ArgumentParser(description="Run Tier 1 Compliance Tests (WinterTC / Edge Baseline & Core JS)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset only")
    parser.add_argument("--all", action="store_true", help="Run full local Tier 1 spec tests (default behavior)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
    parser.add_argument("--log", action="store_true", help="Write all test output to a timestamped log file")
    parser.add_argument("--log-fail", action="store_true", help="Write only failing test output to a timestamped log file")
    args = parser.parse_args()

    ant_bin = find_ant_binary()

    log_path = None
    if args.log or args.log_fail:
        log_path = make_log_path("tier1")

    tracker = SummaryTracker(
        "Tier 1 - WinterTC / Edge Baseline & Core JS",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
    )

    if args.smoke:
        print("Fetching and running Tier 1 pulled official online tests (Test262 / WPT)...")
        specs = PULLED_SMOKE_TESTS["tier1"]
        if args.filter:
            specs = [s for s in specs if args.filter.lower() in s["name"].lower()]

        for spec in specs:
            test_path = fetch_pulled_test(spec)
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(spec["name"], passed, duration_ms, details=output if not passed else "")

    else:
        spec_dir = REPO_ROOT / "examples" / "spec"
        run_js = spec_dir / "run.js"

        if args.filter:
            # Filter mode: run individual matching spec files directly
            print(f"Running filtered local Tier 1 spec files (filter='{args.filter}')...")
            spec_files = sorted([
                f for f in spec_dir.glob("*.js")
                if f.name not in ("run.js", "helpers.js", "import_abs_target.js")
            ])
            spec_files = [f for f in spec_files if args.filter.lower() in f.name.lower()]
            for test_path in spec_files:
                passed, duration_ms, output = run_js_test(ant_bin, test_path)
                tracker.add(test_path.name, passed, duration_ms, details=output if not passed else "")
        else:
            # Full mode: delegate to run.js --all for proper harness output
            print("Running full local Tier 1 spec suite via examples/spec/run.js --all...")
            start = time.perf_counter()
            proc = subprocess.run(
                [str(ant_bin), str(run_js), "--all"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=REPO_ROOT
            )
            duration_ms = (time.perf_counter() - start) * 1000.0
            passed = proc.returncode == 0
            output = proc.stdout or ""
            # Stream the captured output so the user sees it live in the summary
            print(output, end="")
            if log_path:
                should_log = (not args.log_fail) or (not passed)
                if should_log:
                    tracker.add_raw_log("examples/spec/run.js --all", output)
            tracker.add("examples/spec (full suite)", passed, duration_ms)

    return tracker.print_summary()

if __name__ == "__main__":
    sys.exit(main())
