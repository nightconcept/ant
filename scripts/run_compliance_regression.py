#!/usr/bin/env python3
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .compliance_common import (
        REPO_ROOT,
        SummaryTracker,
        find_ant_binary,
        make_log_path,
        run_js_test,
    )
except ImportError:
    from compliance_common import (
        REPO_ROOT,
        SummaryTracker,
        find_ant_binary,
        make_log_path,
        run_js_test,
    )


SPEC_EXCLUSIONS = {"run.js", "helpers.js", "import_abs_target.js"}


@dataclass(frozen=True)
class RegressionTest:
    path: Path
    name: str
    category: str


def discover_regression_tests(repo_root: Path = REPO_ROOT) -> list[RegressionTest]:
    tests = []
    spec_dir = repo_root / "examples" / "spec"
    for path in spec_dir.glob("*.js"):
        if path.name not in SPEC_EXCLUSIONS:
            tests.append(
                RegressionTest(
                    path=path,
                    name=path.relative_to(repo_root).as_posix(),
                    category="Ant Regression: spec",
                )
            )
    test_dir = repo_root / "tests"
    for path in test_dir.glob("test_*"):
        if path.is_file() and path.suffix in {".cjs", ".js", ".mjs"}:
            tests.append(
                RegressionTest(
                    path=path,
                    name=path.relative_to(repo_root).as_posix(),
                    category="Ant Regression: tests",
                )
            )
    return sorted(tests, key=lambda item: item.name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ant Regression tests")
    parser.add_argument("--all", action="store_true", help="Run the full suite (default)")
    parser.add_argument("-f", "--filter", help="Filter test names by substring")
    parser.add_argument("-m", "--module", help="Alias for --filter")
    parser.add_argument("--log", action="store_true", help="Log all test output")
    parser.add_argument("--log-fail", action="store_true", help="Log failing output only")
    args = parser.parse_args()

    filter_value = args.module or args.filter
    selected = discover_regression_tests()
    if filter_value:
        selected = [item for item in selected if filter_value.lower() in item.name.lower()]
    if not selected:
        print("error: filter selected no Ant Regression tests", file=sys.stderr)
        return 1

    ant_bin = find_ant_binary()
    log_path = make_log_path("regression") if args.log or args.log_fail else None
    tracker = SummaryTracker(
        "regression",
        "Ant Regression",
        log_path=log_path,
        log_fail_only=args.log_fail and not args.log,
        filter=filter_value,
    )
    for item in selected:
        passed, duration_ms, output = run_js_test(ant_bin, item.path)
        tracker.add(
            item.name,
            passed,
            duration_ms,
            category=item.category,
            details=output if not passed else "",
        )
    return tracker.print_summary()


if __name__ == "__main__":
    sys.exit(main())
