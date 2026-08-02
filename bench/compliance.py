#!/usr/bin/env python3
from __future__ import annotations
import sys
import argparse
from pathlib import Path
from compliance_common import (
    load_runtimes,
    pad_cell,
    strip_ansi,
    BOLD,
    CYAN,
    GREEN,
    YELLOW,
    RED,
    MAGENTA,
    DIM,
    RESET,
    REPO_ROOT
)
from compliance_wintertc import run_wintertc
from compliance_regression import run_regression
from compliance_test262 import run_test262

def parse_add_runtime_arg(arg_str: str) -> dict:
    """Parse '--add-runtime id:name:binary_path[:args]' argument."""
    parts = arg_str.split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid --add-runtime format '{arg_str}'. Expected 'id:name:binary_path[:arg1,arg2]'")
    r_id = parts[0].strip()
    name = parts[1].strip()
    binary_path = parts[2].strip()
    args = parts[3].split(",") if len(parts) > 3 and parts[3].strip() else []
    return {
        "id": r_id,
        "name": name,
        "binary_path": binary_path,
        "args": args,
        "color": CYAN
    }

def draw_compliance_header_box(runtimes: list[dict], mode_name: str, width: int = 90) -> str:
    r_names = ", ".join(f"{r.get('color','')}{r['name']}{RESET}" for r in runtimes)
    lines = [
        f"{BOLD}{MAGENTA}JS/TS RUNTIME COMPLIANCE BENCHMARK SUITE{RESET}",
        f"{DIM}Target Runtimes: {r_names}{RESET}",
        f"{DIM}Execution Mode: {mode_name}{RESET}",
        f"{DIM}Suites: WinterTC, Ant Regression, Test262{RESET}"
    ]
    box = []
    box.append("╔" + "═" * (width - 2) + "╗")
    for l in lines:
        box.append("║  " + pad_cell(l, width - 6, "center") + "  ║")
    box.append("╚" + "═" * (width - 2) + "╝")
    return "\n".join(box)

def draw_overall_matrix(runtimes: list[dict], suite_results: dict, width: int = 96) -> str:
    """
    Transposed matrix: runtimes as rows and suites as columns.
    """
    lines = [
        f"{BOLD}{MAGENTA}OVERALL COMPLIANCE SCORE MATRIX{RESET}",
        "─" * (width - 6),
    ]

    suite_keys = list(suite_results.keys())

    header_cols = [pad_cell("Runtime", 16)]
    for tk in suite_keys:
        short_name = tk.split(" ")[0] + " " + tk.split(" ")[1] if " " in tk else tk
        header_cols.append(pad_cell(short_name, 16, "right"))
    header_cols.append(pad_cell("Overall Score", 18, "right"))

    lines.append(f"{BOLD}{' '.join(header_cols)}{RESET}")
    lines.append("─" * (width - 6))

    for r in runtimes:
        r_id = r["id"]
        r_color = r.get("color", "")
        row = [pad_cell(f"{r_color}{r['name']}{RESET}", 16)]

        tot_passed = 0
        tot_total = 0

        for tk in suite_keys:
            st = suite_results[tk].get(r_id, {"total": 0, "passed": 0, "pass_pct": 0.0})
            tot_passed += st["passed"]
            tot_total += st["total"]
            score_str = f"{st['passed']}/{st['total']} ({st['pass_pct']:.0f}%)"
            row.append(pad_cell(score_str, 16, "right"))

        overall_pct = (tot_passed / tot_total * 100.0) if tot_total > 0 else 0.0
        pct_color = GREEN if overall_pct == 100.0 else YELLOW if overall_pct >= 50.0 else RED
        overall_str = f"{tot_passed}/{tot_total} ({pct_color}{overall_pct:.1f}%{RESET})"
        row.append(pad_cell(overall_str, 18, "right"))

        lines.append(" ".join(row))

    lines.append("─" * (width - 6))

    tot_ant_p, tot_ant_t = 0, 0
    tot_tjs_p, tot_tjs_t = 0, 0

    for tk in suite_keys:
        st_ant = suite_results[tk].get("ant", {"total": 0, "passed": 0})
        st_tjs = suite_results[tk].get("tjs", {"total": 0, "passed": 0})
        tot_ant_p += st_ant.get("passed", 0)
        tot_ant_t += st_ant.get("total", 0)
        tot_tjs_p += st_tjs.get("passed", 0)
        tot_tjs_t += st_tjs.get("total", 0)

    pct_ant = (tot_ant_p / tot_ant_t * 100.0) if tot_ant_t > 0 else 0.0
    pct_tjs = (tot_tjs_p / tot_tjs_t * 100.0) if tot_tjs_t > 0 else 0.0

    if tot_ant_t > 0 and tot_tjs_t > 0:
        h2h_comp = f"{BOLD}Head-to-Head Compliance (ant vs txiki.js):{RESET} {GREEN}ant{RESET}: {tot_ant_p}/{tot_ant_t} ({pct_ant:.1f}%) | {YELLOW}txiki.js{RESET}: {tot_tjs_p}/{tot_tjs_t} ({pct_tjs:.1f}%)"
        lines.append(pad_cell(h2h_comp, width - 6, "center"))

    box = []
    box.append("\n╔" + "═" * (width - 2) + "╗")
    for l in lines:
        box.append("║  " + pad_cell(l, width - 6) + "  ║")
    box.append("╚" + "═" * (width - 2) + "╝\n")
    return "\n".join(box)

def save_compliance_json_and_baseline(runtimes: list[dict], suite_results: dict, update_baseline: bool = False) -> tuple[Path, Path | None]:
    import json
    import time
    from datetime import datetime, timezone
    from compliance_common import git_revision

    logs_dir = REPO_ROOT.parent / ".deps" / "compliance" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    manifest_path = logs_dir / f"compliance_{ts}.json"
    latest_path = logs_dir / "compliance-latest.json"

    rev = git_revision()

    manifest_data = {
        "schema_version": 1,
        "type": "multi_runtime_compliance",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "revision": rev,
        "runtimes": [r["id"] for r in runtimes],
        "suite_results": suite_results
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")

    try:
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        latest_path.symlink_to(manifest_path.name)
    except Exception:
        pass

    baseline_written = None
    if update_baseline:
        # Deliberately NOT docs/repo/compliance-baseline.json - that file is the
        # ant-only CI regression gate (scripts/compliance_baseline.py, keyed by
        # suite ID) and has an incompatible schema from this multi-runtime
        # manifest (keyed by suite label). Keep this snapshot separate so running
        # --update-baseline can't corrupt the CI gate's baseline.
        baseline_path = REPO_ROOT.parent / "docs" / "repo" / "compliance-runtimes-baseline.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
            f.write("\n")
        baseline_written = baseline_path

    return manifest_path, baseline_written

def main():
    parser = argparse.ArgumentParser(description="Multi-Runtime Compliance Benchmark Orchestrator")
    parser.add_argument("--suite", choices=["wintertc", "regression", "test262", "all"], default="all", help="Select suite to execute (default: all)")
    parser.add_argument("--smoke", action="store_true", help="Run official online smoke test subset")
    parser.add_argument("--all", action="store_true", help="Run full local test suite (default)")
    parser.add_argument("-f", "--filter", type=str, help="Filter test name by substring")
    parser.add_argument("--runtimes", type=str, help="Comma-separated runtime IDs to run (e.g. 'ant,tjs,node,deno,bun')")
    parser.add_argument("--add-runtime", type=str, action="append", help="Add custom runtime formatted as 'id:name:binary_path[:arg1,arg2]' (e.g. 'ant-fork:Ant Fork:../ant/build/ant')")
    parser.add_argument("--limit", type=int, help="Limit the selected Test262 tests")
    parser.add_argument("--log", action="store_true", help="Write all test output to log files")
    parser.add_argument("--log-fail", action="store_true", help="Write failing test output to log files")
    parser.add_argument("--allow-failures", action="store_true", help="Exit with 0 even if some tests fail")
    parser.add_argument("--update-baseline", action="store_true", help="Update checked-in compliance baseline file with run manifest")
    args = parser.parse_args()

    smoke_mode = args.smoke and not args.all

    extra_runtimes = []
    if args.add_runtime:
        for ex_arg in args.add_runtime:
            try:
                extra_runtimes.append(parse_add_runtime_arg(ex_arg))
            except Exception as e:
                print(f"{RED}Error parsing --add-runtime: {e}{RESET}")
                sys.exit(1)

    filter_ids = args.runtimes.split(",") if args.runtimes else None
    runtimes = load_runtimes(filter_ids=filter_ids, extra_runtimes=extra_runtimes)

    if not runtimes:
        print(f"{RED}Error: No valid runtimes resolved.{RESET}")
        sys.exit(1)

    mode_str = "Smoke Test" if smoke_mode else "Full Suite"
    print(draw_compliance_header_box(runtimes, mode_str))

    suite_results = {}
    overall_exit_code = 0

    if args.suite in ("wintertc", "all"):
        stats = run_wintertc(runtimes, smoke=smoke_mode, filter_term=args.filter, log_all=args.log, log_fail=args.log_fail)
        suite_results["WinterTC"] = stats
        if any(st["failed"] > 0 for st in stats.values()):
            overall_exit_code = 1

    if args.suite in ("regression", "all"):
        stats = run_regression(runtimes, smoke=smoke_mode, filter_term=args.filter, log_all=args.log, log_fail=args.log_fail)
        suite_results["Ant Regression"] = stats
        if any(st["failed"] > 0 for st in stats.values()):
            overall_exit_code = 1

    if args.suite in ("test262", "all"):
        stats = run_test262(runtimes, smoke=smoke_mode, filter_term=args.filter, limit=args.limit, log_all=args.log, log_fail=args.log_fail)
        suite_results["Test262"] = stats
        if any(st["failed"] > 0 for st in stats.values()):
            overall_exit_code = 1

    if len(suite_results) > 1:
        print(draw_overall_matrix(runtimes, suite_results))

    manifest_path, baseline_path = save_compliance_json_and_baseline(runtimes, suite_results, update_baseline=args.update_baseline)
    print(f"  {CYAN}Compliance Manifest JSON : {manifest_path}{RESET}")
    if baseline_path:
        print(f"  {GREEN}Compliance Baseline Updated: {baseline_path}{RESET}")

    if args.allow_failures:
        sys.exit(0)
    else:
        sys.exit(overall_exit_code)

if __name__ == "__main__":
    main()
