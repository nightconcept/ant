#!/usr/bin/env python3
from __future__ import annotations
import sys
import os
import argparse
from pathlib import Path
from compliance_common import (
    load_runtimes,
    run_js_test,
    MultiRuntimeTracker,
    fetch_pulled_test,
    PULLED_SMOKE_TESTS,
    make_log_path,
    ensure_test262_repo,
    prepare_test262_code,
    DEPS_DIR,
    REPO_ROOT
)

TIER3_SPEC_FILES = [
    "observable.js",
    "explicit_resource_management.js",
    "finalizationregistry.js",
    "lmdb.js",
    "tla.js",
    "worker_threads.js",
]

def run_tier3(runtimes: list[dict], smoke: bool = False, filter_term: str | None = None, limit: int | None = None, log_all: bool = False, log_fail: bool = False) -> dict:
    log_path = make_log_path("tier3") if (log_all or log_fail) else None

    tracker = MultiRuntimeTracker(
        "Tier 3 - Full Conformance (Test262 / WPT / Frameworks)",
        runtimes=runtimes,
        log_path=log_path,
        log_fail_only=log_fail and not log_all,
    )

    if smoke:
        print("\n=== Executing Tier 3 Smoke Tests (Test262 / WPT Baseline) ===")
        specs = PULLED_SMOKE_TESTS["tier3"]
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
        print("\n=== Executing Tier 3 Full Suite (Test262 / WPT / Advanced Frameworks) ===")
        spec_dir = REPO_ROOT / "examples" / "spec"
        spec_files = sorted([spec_dir / name for name in TIER3_SPEC_FILES if (spec_dir / name).exists()])

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

        # Execute Test262 repository suite
        t262_repo = ensure_test262_repo()
        t262_test_root = t262_repo / "test"
        if t262_test_root.exists():
            test262_dir = t262_test_root.parent
            all_t262 = sorted([
                f for f in t262_test_root.glob("**/*.js")
                if not f.name.endswith("_FIXTURE.js") and "FIXTURE" not in f.name
            ])

            if filter_term:
                filter_lower = filter_term.lower()
                all_t262 = [f for f in all_t262 if filter_lower in str(f.relative_to(t262_test_root)).lower()]

            if limit:
                all_t262 = all_t262[:limit]

            if all_t262:
                print(f"Executing {len(all_t262)} Test262 tests across runtimes...")

                def run_single_t262(item):
                    idx, t_file = item
                    code, fm = prepare_test262_code(t_file, test262_dir)
                    tmp_file = DEPS_DIR / f"tmp_t262_{idx}_{os.getpid()}.js"
                    tmp_file.write_text(code, encoding="utf-8")

                    rel_path = t_file.relative_to(t262_test_root)
                    test_name = f"Test262: {rel_path}"
                    neg = fm.get("negative")

                    results_by_runtime = {}
                    for r in runtimes:
                        passed, duration_ms, output = run_js_test(r, tmp_file, timeout_sec=5.0)
                        actual_passed = (not passed) if neg is not None else passed
                        results_by_runtime[r["id"]] = {
                            "passed": actual_passed,
                            "duration_ms": duration_ms,
                            "details": output if not actual_passed else ""
                        }
                    try:
                        tmp_file.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return test_name, results_by_runtime

                print_output = (len(all_t262) <= 50)
                from concurrent.futures import ThreadPoolExecutor
                max_workers = min(32, (os.cpu_count() or 4) * 4)

                completed = 0
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    for test_name, results in executor.map(run_single_t262, enumerate(all_t262)):
                        completed += 1
                        tracker.add_test(test_name, results, print_output=print_output)
                        if not print_output and (completed % 100 == 0 or completed == len(all_t262)):
                            print(f"\r  ⏳ Test262 progress: [{completed}/{len(all_t262)}] tests completed...", end="", flush=True)
                if not print_output:
                    print()

    return tracker.print_tier_summary()

def main():
    parser = argparse.ArgumentParser(description="Run Tier 3 Compliance Tests (Full Conformance: Test262 / WPT / Frameworks)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset")
    parser.add_argument("--all", action="store_true", default=True, help="Run full local Tier 3 spec tests (default)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
    parser.add_argument("--limit", type=int, help="Limit number of Test262 tests")
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
    run_tier3(runtimes, smoke=smoke, filter_term=args.filter, limit=args.limit, log_all=args.log, log_fail=args.log_fail)

if __name__ == "__main__":
    main()
