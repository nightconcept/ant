#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from compliance_common import (
    find_ant_binary,
    run_js_test,
    SummaryTracker,
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
    "atomics.js",
    "explicit_resource_management.js",
]

def run_single_t262(ant_bin: Path, test262_dir: Path, test_file: Path, worker_id: int):
    tmp_file = DEPS_DIR / f"tmp_t262_w{worker_id}.js"
    code, fm = prepare_test262_code(test_file, test262_dir)
    tmp_file.write_text(code, encoding="utf-8")
    
    passed, duration_ms, output = run_js_test(ant_bin, tmp_file, timeout_sec=5.0)
    
    neg = fm.get("negative")
    rel_path = test_file.relative_to(test262_dir / "test")
    test_name = f"Test262: {rel_path}"
    
    if neg is not None:
        actual_passed = not passed
    else:
        actual_passed = passed
        
    return test_name, actual_passed, duration_ms, output

def main():
    parser = argparse.ArgumentParser(description="Run Tier 3 Compliance Tests (Full Conformance: Test262 / WPT / Frameworks)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset only")
    parser.add_argument("--all", action="store_true", help="Run full local Tier 3 spec tests and complete Test262 (default behavior)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring (e.g., 'Array/prototype/map', 'built-ins', 'language')")
    parser.add_argument("--limit", type=int, help="Limit number of Test262 tests to execute")
    parser.add_argument("--log", action="store_true", help="Write all test output to a timestamped log file")
    parser.add_argument("--log-fail", action="store_true", help="Write only failing test output to a timestamped log file")
    args = parser.parse_args()

    ant_bin = find_ant_binary()

    log_path = None
    if args.log or args.log_fail:
        log_path = make_log_path("tier3")

    tracker = SummaryTracker(
        "Tier 3 - Full Conformance (Test262 / WPT / Frameworks)",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
    )

    if args.smoke:
        print("Fetching and running Tier 3 pulled official online tests (Test262)...")
        specs = PULLED_SMOKE_TESTS["tier3"]
        if args.filter:
            specs = [s for s in specs if args.filter.lower() in s["name"].lower()]

        for spec in specs:
            test_path = fetch_pulled_test(spec)
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(spec["name"], passed, duration_ms, details=output if not passed else "")

    else:
        print("Running local Tier 3 advanced spec files in examples/spec/...")
        spec_dir = REPO_ROOT / "examples" / "spec"
        spec_files = sorted([spec_dir / name for name in TIER3_SPEC_FILES if (spec_dir / name).exists()])

        if args.filter:
            spec_files = [f for f in spec_files if args.filter.lower() in f.name.lower()]

        for test_path in spec_files:
            passed, duration_ms, output = run_js_test(ant_bin, test_path)
            tracker.add(test_path.name, passed, duration_ms, details=output if not passed else "")

        # Run real Test262 test suite
        print("Ensuring Test262 test suite repository...")
        test262_dir = ensure_test262_repo()
        t262_test_root = test262_dir / "test"

        if t262_test_root.exists():
            print(f"Discovering Test262 tests in {t262_test_root}...")
            all_t262 = sorted([
                f for f in t262_test_root.glob("**/*.js")
                if not f.name.endswith("_FIXTURE.js") and "FIXTURE" not in f.name
            ])

            if args.filter:
                filter_lower = args.filter.lower()
                all_t262 = [f for f in all_t262 if filter_lower in str(f.relative_to(t262_test_root)).lower()]

            if args.limit:
                all_t262 = all_t262[:args.limit]

            print(f"Executing full set of {len(all_t262)} Test262 tests...")
            workers = min(os.cpu_count() or 8, 16)
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = []
                for idx, t_file in enumerate(all_t262):
                    worker_id = idx % workers
                    futures.append(executor.submit(run_single_t262, ant_bin, test262_dir, t_file, worker_id))

                for future in as_completed(futures):
                    name, passed, duration_ms, output = future.result()
                    tracker.add(name, passed, duration_ms, details=output if not passed else "")

    return tracker.print_summary()

if __name__ == "__main__":
    sys.exit(main())
