#!/usr/bin/env python3
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from .compliance_common import (
        REPO_ROOT,
        SummaryTracker,
        WPTManifestError,
        WPT_TMP_PREFIX,
        discover_wpt_tests,
        ensure_wpt_repo,
        find_ant_binary,
        make_log_path,
        run_js_test,
        run_wpt_test,
    )
except ImportError:
    from compliance_common import (
        REPO_ROOT,
        SummaryTracker,
        WPTManifestError,
        WPT_TMP_PREFIX,
        discover_wpt_tests,
        ensure_wpt_repo,
        find_ant_binary,
        make_log_path,
        run_js_test,
        run_wpt_test,
    )


MANIFEST_PATH = REPO_ROOT / "tests" / "wintertc" / "wpt-manifest.json"
API_SURFACE_PATH = REPO_ROOT / "tests" / "wintertc" / "api-surface.js"


def sweep_stale_wpt_files(wpt_dir: Path) -> int:
    removed = 0
    for path in wpt_dir.glob(f"**/{WPT_TMP_PREFIX}*"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def run_one(ant_bin: Path, wpt_dir: Path, item, sequence: int):
    name = f"WPT: {item.path.relative_to(wpt_dir).as_posix()}"
    try:
        passed, duration_ms, output = run_wpt_test(
            ant_bin, wpt_dir, item.path, sequence
        )
    except (OSError, WPTManifestError) as exc:
        passed, duration_ms, output = False, 0.0, f"WPT harness error: {exc}"
    return name, item.category, passed, duration_ms, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WinterTC compliance tests")
    parser.add_argument("--all", action="store_true", help="Run the full suite (default)")
    parser.add_argument("-f", "--filter", help="Filter tests by path substring")
    parser.add_argument("--limit", type=int, help="Limit the selected WPT tests")
    parser.add_argument("--list", action="store_true", help="List selected tests without running Ant")
    parser.add_argument("--log", action="store_true", help="Log all test output")
    parser.add_argument("--log-fail", action="store_true", help="Log failing output only")
    args = parser.parse_args()

    try:
        wpt_dir = ensure_wpt_repo()
        selected = discover_wpt_tests(wpt_dir, MANIFEST_PATH)
    except (OSError, RuntimeError, WPTManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    filter_value = args.filter.lower() if args.filter else None
    if filter_value:
        selected = [
            item for item in selected
            if filter_value in item.path.relative_to(wpt_dir).as_posix().lower()
        ]
    if args.limit is not None:
        if args.limit < 1:
            print("error: --limit must be positive", file=sys.stderr)
            return 1
        selected = selected[:args.limit]
    include_surface = not filter_value or filter_value in "api-surface"
    if not selected and not include_surface:
        print("error: filter selected no WinterTC tests", file=sys.stderr)
        return 1

    if args.list:
        if include_surface:
            print("WinterTC: API surface")
        for item in selected:
            print(f"WPT: {item.path.relative_to(wpt_dir).as_posix()}")
        return 0

    ant_bin = find_ant_binary()
    log_path = make_log_path("wintertc") if args.log or args.log_fail else None
    tracker = SummaryTracker(
        "wintertc",
        "WinterTC",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
        filter=args.filter,
    )

    if include_surface:
        passed, duration_ms, output = run_js_test(ant_bin, API_SURFACE_PATH)
        tracker.add(
            "WinterTC: API surface",
            passed,
            duration_ms,
            category="WinterTC: API surface",
            details=output if not passed else "",
        )

    sweep_stale_wpt_files(wpt_dir)
    workers = min(os.cpu_count() or 8, 16)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_one, ant_bin, wpt_dir, item, sequence)
                for sequence, item in enumerate(selected)
            ]
            for future in as_completed(futures):
                name, category, passed, duration_ms, output = future.result()
                tracker.add(
                    name,
                    passed,
                    duration_ms,
                    category=f"WinterTC: {category}",
                    details=output if not passed else "",
                )
    finally:
        sweep_stale_wpt_files(wpt_dir)
    return tracker.print_summary()


if __name__ == "__main__":
    sys.exit(main())
