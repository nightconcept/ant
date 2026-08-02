#!/usr/bin/env python3
import sys
import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Ant Compliance Test Suite Orchestrator")
    parser.add_argument(
        "--suite",
        choices=["regression", "test262", "all"],
        default="regression",
        help="Select suite to execute (default: regression)",
    )
    parser.add_argument("--all", action="store_true", help="Run full local test suite (default behavior)")
    parser.add_argument("-f", "--filter", type=str, help="Filter test name by substring")
    parser.add_argument("-m", "--module", type=str, help="Filter Ant Regression tests by module name")
    parser.add_argument("--limit", type=int, help="Limit tests in suites that support it")
    parser.add_argument("--log", action="store_true", help="Write all test output to a timestamped log file")
    parser.add_argument("--log-fail", action="store_true", help="Write only failing test output to a timestamped log file")
    parser.add_argument("--allow-failures", action="store_true", help="Exit with 0 even if some tests fail")
    args = parser.parse_args()

    mode_flag = "--all"
    extra_flags = []
    if args.filter:
        extra_flags.extend(["--filter", args.filter])
    if args.module:
        extra_flags.extend(["--module", args.module])
    if args.limit:
        extra_flags.extend(["--limit", str(args.limit)])
    if args.log:
        extra_flags.append("--log")
    if args.log_fail:
        extra_flags.append("--log-fail")

    suites_to_run = []
    if args.suite in ("regression", "all"):
        suites_to_run.append(("Ant Regression", REPO_ROOT / "run_compliance_regression.py"))
    if args.suite in ("test262", "all"):
        suites_to_run.append(("Test262", REPO_ROOT / "run_compliance_test262.py"))

    overall_exit_code = 0
    for name, script_path in suites_to_run:
        print(f"\n=== Executing {name} ({script_path.name}) ===")
        cmd = [sys.executable, str(script_path), mode_flag] + extra_flags
        res = subprocess.run(cmd)
        if res.returncode != 0:
            overall_exit_code = res.returncode

    if args.allow_failures:
        sys.exit(0)
    else:
        sys.exit(overall_exit_code)

if __name__ == "__main__":
    main()
