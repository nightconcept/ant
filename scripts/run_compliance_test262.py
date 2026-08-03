#!/usr/bin/env python3
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from .compliance_common import (
        SummaryTracker,
        ensure_test262_repo,
        find_ant_binary,
        make_log_path,
        prepare_test262_code,
        run_js_test,
    )
except ImportError:
    from compliance_common import (
        SummaryTracker,
        ensure_test262_repo,
        find_ant_binary,
        make_log_path,
        prepare_test262_code,
        run_js_test,
    )


TMP_PREFIX = "ant_t262_tmp_"


def discover_test262_tests(
    test262_dir: Path,
    filter_value: str | None = None,
    limit: int | None = None,
) -> list[Path]:
    test_root = test262_dir / "test"
    selected = sorted(
        path
        for path in test_root.glob("**/*.js")
        if "FIXTURE" not in path.name and not path.name.startswith(TMP_PREFIX)
    )
    if filter_value:
        needle = filter_value.lower()
        selected = [
            path
            for path in selected
            if needle in path.relative_to(test_root).as_posix().lower()
        ]
    if limit is not None:
        selected = selected[:limit]
    return selected


def sweep_stale_tmp(test262_dir: Path) -> int:
    removed = 0
    for stale in (test262_dir / "test").glob(f"**/{TMP_PREFIX}*"):
        try:
            stale.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def run_one(ant_bin: Path, test262_dir: Path, test_file: Path, sequence: int):
    scratch = test_file.parent / f"{TMP_PREFIX}{sequence}_{test_file.name}"
    try:
        code, frontmatter = prepare_test262_code(test_file, test262_dir)
        scratch.write_text(code, encoding="utf-8")
        process_passed, duration_ms, output = run_js_test(
            ant_bin, scratch, timeout_sec=5.0
        )
    finally:
        try:
            scratch.unlink()
        except OSError:
            pass
    passed = not process_passed if frontmatter.get("negative") is not None else process_passed
    relative = test_file.relative_to(test262_dir / "test").as_posix()
    return f"Test262: {relative}", passed, duration_ms, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the pinned Test262 suite")
    parser.add_argument("--all", action="store_true", help="Run the full suite (default)")
    parser.add_argument("-f", "--filter", help="Filter Test262 paths by substring")
    parser.add_argument("--limit", type=int, help="Limit the selected Test262 tests")
    parser.add_argument("--log", action="store_true", help="Log all test output")
    parser.add_argument("--log-fail", action="store_true", help="Log failing output only")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        print("error: --limit must be positive", file=sys.stderr)
        return 1

    ant_bin = find_ant_binary()
    test262_dir = ensure_test262_repo()
    selected = discover_test262_tests(test262_dir, args.filter, args.limit)
    if not selected:
        print("error: filter selected no Test262 tests", file=sys.stderr)
        return 1

    log_path = make_log_path("test262") if args.log or args.log_fail else None
    tracker = SummaryTracker(
        "test262",
        "Test262",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
        filter=args.filter,
    )
    sweep_stale_tmp(test262_dir)
    workers = min(os.cpu_count() or 8, 16)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_one, ant_bin, test262_dir, path, sequence)
                for sequence, path in enumerate(selected)
            ]
            for future in as_completed(futures):
                name, passed, duration_ms, output = future.result()
                tracker.add(
                    name,
                    passed,
                    duration_ms,
                    details=output if not passed else "",
                )
    finally:
        sweep_stale_tmp(test262_dir)
    return tracker.print_summary()


if __name__ == "__main__":
    sys.exit(main())
