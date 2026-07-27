#!/usr/bin/env python3
from __future__ import annotations
import sys
import argparse
from pathlib import Path
from compliance_common import (
    load_runtimes,
    run_js_test,
    MultiRuntimeTracker,
    fetch_pulled_test,
    PULLED_SMOKE_TESTS,
    make_log_path,
    REPO_ROOT
)

TIER2_SPEC_FILES = [
    "base64.js", "blob.js", "buffer.js", "child_process.js", "console.js",
    "crypto.js", "diagnostics_channel.js", "events.js", "eventsource.js", "fetch.js",
    "formdata.js", "fs.js", "fs_async.js", "headers.js", "localstorage.js",
    "navigator.js", "os.js", "path.js", "performance.js", "process.js",
    "readline.js", "request.js", "response.js", "sessionstorage.js", "shell.js",
    "streams-compression.js", "streams-encoding.js", "streams-pipe.js", "streams-queuing.js",
    "streams-readable.js", "streams-transform.js", "textcodec.js", "timers.js",
    "tty.js", "url.js", "v8.js", "websocket.js", "zlib.js"
]

def run_tier2(runtimes: list[dict], smoke: bool = False, filter_term: str | None = None, log_all: bool = False, log_fail: bool = False) -> dict:
    log_path = make_log_path("tier2") if (log_all or log_fail) else None

    tracker = MultiRuntimeTracker(
        "Tier 2 - Node.js Compatibility Suite",
        runtimes=runtimes,
        log_path=log_path,
        log_fail_only=log_fail and not log_all,
    )

    if smoke:
        print("\n=== Executing Tier 2 Smoke Tests (Node.js Compatibility Suite) ===")
        specs = PULLED_SMOKE_TESTS["tier2"]
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
        print("\n=== Executing Tier 2 Full Suite (Node.js Compatibility Suite) ===")
        spec_dir = REPO_ROOT / "examples" / "spec"
        test_files = sorted([spec_dir / name for name in TIER2_SPEC_FILES if (spec_dir / name).exists()])
        if filter_term:
            test_files = [f for f in test_files if filter_term.lower() in f.name.lower()]

        for test_path in test_files:
            results_by_runtime = {}
            for r in runtimes:
                passed, duration_ms, output = run_js_test(r, test_path)
                results_by_runtime[r["id"]] = {
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "details": output if not passed else ""
                }
            tracker.add_test(test_path.name, results_by_runtime)

    return tracker.print_tier_summary()

def main():
    parser = argparse.ArgumentParser(description="Run Tier 2 Compliance Tests (Node.js Compatibility Suite)")
    parser.add_argument("--smoke", action="store_true", help="Run pulled official online smoke test subset")
    parser.add_argument("--all", action="store_true", default=True, help="Run all local Node module tests (default)")
    parser.add_argument("-f", "--filter", type=str, help="Filter tests by substring")
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
    run_tier2(runtimes, smoke=smoke, filter_term=args.filter, log_all=args.log, log_fail=args.log_fail)

if __name__ == "__main__":
    main()
