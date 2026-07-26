#!/usr/bin/env python3
import sys
import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description="Ant Compliance Test Suite Orchestrator")
    parser.add_argument("--tier", choices=["1", "2", "3", "all"], default="1", help="Select tier to execute (default: 1)")
    parser.add_argument("--smoke", action="store_true", default=True, help="Run pulled official online smoke test subset (default: True)")
    parser.add_argument("--all", action="store_true", help="Run full local test suite instead of smoke subset")
    parser.add_argument("-f", "--filter", type=str, help="Filter test name by substring")
    parser.add_argument("-m", "--module", type=str, help="Filter Node module by name (Tier 2)")
    args = parser.parse_args()

    mode_flag = "--all" if args.all else "--smoke"
    extra_flags = []
    if args.filter:
        extra_flags.extend(["--filter", args.filter])
    if args.module:
        extra_flags.extend(["--module", args.module])

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

    sys.exit(overall_exit_code)

if __name__ == "__main__":
    main()
