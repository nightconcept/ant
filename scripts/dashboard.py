#!/usr/bin/env python3
"""Print a one-shot snapshot of the checked-in compliance and bench baselines.

Reads the same files the CI regression gates diff against:

  * docs/repo/compliance-baseline.json          - ant tier 1/2/3 pass rates (CI gate)
  * docs/repo/compliance-runtimes-baseline.json - ant vs. other runtimes compliance
  * docs/repo/bench-baseline.json                - ant vs. other runtimes timing/size

All are checked-in snapshots, not live measurements - see the commit/branch
printed with each section before treating a number as current. Run
`just compliance-diff-t<N>`, `just compliance-runtimes-update`, or
`just bench-fast-diff` for a fresh run.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPLIANCE_BASELINE = REPO_ROOT / "docs" / "repo" / "compliance-baseline.json"
COMPLIANCE_RUNTIMES_BASELINE = REPO_ROOT / "docs" / "repo" / "compliance-runtimes-baseline.json"
BENCH_BASELINE = REPO_ROOT / "docs" / "repo" / "bench-baseline.json"

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

TIER_NAMES = {
    "1": "WinterTC / edge baseline",
    "2": "Node.js compatibility",
    "3": "Test262 / WPT / frameworks",
}


def load(path):
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def format_local(iso_str):
    """Parse an ISO timestamp (aware or naive-UTC) and render it in local time."""
    if not iso_str:
        return f"{DIM}unknown time{RESET}"
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def pass_rate_color(rate):
    if rate >= 99.0:
        return GREEN
    if rate >= 90.0:
        return YELLOW
    return RED


def print_header(title):
    print(f"\n{BOLD}{CYAN}{title}{RESET}")
    print(f"{DIM}{'-' * len(title)}{RESET}")


def print_compliance(data):
    print_header("Compliance")
    if data is None:
        print(f"  {DIM}no baseline at {COMPLIANCE_BASELINE.relative_to(REPO_ROOT)}{RESET}")
        return

    tiers = data.get("tiers", {})
    for tier in sorted(tiers, key=lambda t: int(t)):
        entry = tiers[tier]
        totals = entry["totals"]
        rev = entry["revision"]
        rate = totals["pass_rate"]
        color = pass_rate_color(rate)
        name = TIER_NAMES.get(tier, f"tier {tier}")
        when = format_local(entry.get("finished"))
        print(
            f"  Tier {tier} {DIM}({name}){RESET}: "
            f"{color}{rate:5.1f}%{RESET} "
            f"({totals['passed']}/{totals['total']} passed, {totals['failed']} failed) "
            f"{DIM}@ {rev['short']} [{rev['branch']}] recorded {when}{RESET}"
        )


def print_compliance_runtimes(data):
    print_header("Compliance vs other runtimes")
    if data is None:
        print(f"  {DIM}no baseline at {COMPLIANCE_RUNTIMES_BASELINE.relative_to(REPO_ROOT)}{RESET}")
        print(f"  {DIM}run `just compliance-runtimes-update` to record one{RESET}")
        return

    rev = data["revision"]
    print(f"  {DIM}@ {rev['short']} [{rev['branch']}] recorded {format_local(data['timestamp'])}{RESET}")

    runtime_ids = list(data.get("runtimes", []))
    if "ant" in runtime_ids:
        runtime_ids.remove("ant")
        runtime_ids = ["ant"] + runtime_ids

    for tier_label, runtime_stats in data.get("tier_results", {}).items():
        print()
        print(f"  {BOLD}{tier_label}{RESET}")
        header = "    " + f"{'runtime':<12}" + f"{'pass rate':>12}" + f"{'passed/total':>16}"
        print(header)
        for rt in runtime_ids:
            stats = runtime_stats.get(rt)
            if stats is None:
                continue
            rate = stats.get("pass_pct", 0.0)
            color = GREEN if rt == "ant" else pass_rate_color(rate)
            rate_cell = f"{rate:5.1f}%"
            ratio_cell = f"{stats.get('passed', 0)}/{stats.get('total', 0)}"
            row = (
                f"    {rt:<12}"
                f"{color}{rate_cell:>12}{RESET}"
                f"{ratio_cell:>16}"
            )
            print(row)


def format_ms(value):
    if value is None:
        return f"{DIM}-{RESET}"
    return f"{value:8.2f}ms"


def print_metric_table(title, benchmarks, names, runtimes, metric, unit, fmt="{:.1f}"):
    print()
    print(f"  {BOLD}{title}{RESET}")
    header = "    " + f"{'benchmark':<28}" + "".join(f"{runtimes[rt]['name']:>12}" for rt in names)
    print(header)

    for b in benchmarks:
        values = b.get(metric, {})
        row = f"    {b['name']:<28}"
        for rt in names:
            v = values.get(rt)
            plain = f"{fmt.format(v)}{unit}" if v is not None else "-"
            cell = f"{plain:>12}"
            if rt == "ant" and v is not None:
                cell = f"{GREEN}{cell}{RESET}"
            row += cell
        print(row)


def print_bench(data, top_n):
    print_header("Benchmarks")
    if data is None:
        print(f"  {DIM}no baseline at {BENCH_BASELINE.relative_to(REPO_ROOT)}{RESET}")
        return

    rev = data["revision"]
    print(f"  {DIM}@ {rev['short']} [{rev['branch']}] recorded {format_local(data['timestamp'])}{RESET}")

    runtimes = data["runtimes"]
    names = list(runtimes.keys())
    if "ant" in names:
        names.remove("ant")
        names = ["ant"] + names

    print()
    print(f"  {BOLD}Startup floor{RESET}")
    floor = data.get("startup_floor_ms", {})
    for rt in names:
        if rt in floor:
            label = runtimes[rt]["name"]
            print(f"    {label:<12} {format_ms(floor[rt])}")

    all_benchmarks = data.get("benchmarks", [])
    benchmarks = all_benchmarks[:top_n] if top_n else all_benchmarks

    print_metric_table(
        "Benchmark means (lower is better, ant column highlighted)",
        benchmarks, names, runtimes, "means", "ms",
    )
    print_metric_table(
        "Peak RSS (lower is better, ant column highlighted)",
        benchmarks, names, runtimes, "rss", "MB",
    )

    if top_n and len(all_benchmarks) > top_n:
        remaining = len(all_benchmarks) - top_n
        print(f"\n  {DIM}... {remaining} more, drop --bench-top to see everything{RESET}")

    print()
    print(f"  {BOLD}Average peak RSS across all benchmarks{RESET}")
    for rt in names:
        vals = [b["rss"][rt] for b in all_benchmarks if b.get("rss", {}).get(rt, 0) > 0]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        label = runtimes[rt]["name"]
        color = GREEN if rt == "ant" else ""
        reset = RESET if rt == "ant" else ""
        print(f"    {label:<12} {color}{avg:8.1f} MB{reset}")

    binary_sizes = {rt: runtimes[rt].get("binary_size") for rt in names if runtimes[rt].get("binary_size")}
    if binary_sizes:
        print()
        print(f"  {BOLD}Binary size{RESET}")
        for rt in names:
            size = binary_sizes.get(rt)
            if size is None:
                continue
            label = runtimes[rt]["name"]
            color = GREEN if rt == "ant" else ""
            reset = RESET if rt == "ant" else ""
            print(f"    {label:<12} {color}{size / (1024 * 1024):8.2f} MB{reset}")


def main(argv):
    top_n = None
    if "--bench-top" in argv:
        idx = argv.index("--bench-top")
        top_n = int(argv[idx + 1])

    compliance = load(COMPLIANCE_BASELINE)
    compliance_runtimes = load(COMPLIANCE_RUNTIMES_BASELINE)
    bench = load(BENCH_BASELINE)

    print(f"{BOLD}Ant dashboard{RESET} {DIM}(checked-in baselines, not a live run){RESET}")
    print_compliance(compliance)
    print_compliance_runtimes(compliance_runtimes)
    print_bench(bench, top_n)
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
