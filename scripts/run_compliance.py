#!/usr/bin/env python3
import sys
import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Ant Compliance Test Suite Orchestrator")
    parser.add_argument("--tier", choices=["1", "2", "3", "all"], default="1", help="Select tier to execute (default: 1)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset instead of the full local suite")
    parser.add_argument("--all", action="store_true", help="Run full local test suite (default behavior)")
    parser.add_argument("-f", "--filter", type=str, help="Filter test name by substring")
    parser.add_argument("-m", "--module", type=str, help="Filter Node module by name (Tier 2)")
    parser.add_argument("--limit", type=int, help="Limit number of Test262 tests to execute (Tier 3)")
    parser.add_argument("--all-test262", action="store_true", help="Run complete Test262 suite in Tier 3 without limit")
    parser.add_argument("--log", action="store_true", help="Write all test output to a timestamped log file")
    parser.add_argument("--log-fail", action="store_true", help="Write only failing test output to a timestamped log file")
    parser.add_argument("--allow-failures", action="store_true", help="Exit with 0 even if some tests fail")
    args = parser.parse_args()

    mode_flag = "--smoke" if args.smoke else "--all"
    extra_flags = []
    if args.filter:
        extra_flags.extend(["--filter", args.filter])
    if args.module:
        extra_flags.extend(["--module", args.module])
    if args.limit:
        extra_flags.extend(["--limit", str(args.limit)])
    if args.all_test262:
        extra_flags.append("--all-test262")
    if args.log:
        extra_flags.append("--log")
    if args.log_fail:
        extra_flags.append("--log-fail")

    tiers_to_run = []
    if args.tier in ("1", "all"):
        tiers_to_run.append(("Tier 1", REPO_ROOT / "run_compliance_tier1.py"))
    if args.tier in ("2", "all"):
        tiers_to_run.append(("Tier 2", REPO_ROOT / "run_compliance_tier2.py"))
    if args.tier in ("3", "all"):
        tiers_to_run.append(("Tier 3", REPO_ROOT / "run_compliance_tier3.py"))

    overall_exit_code = 0
    for name, script_path in tiers_to_run:
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
