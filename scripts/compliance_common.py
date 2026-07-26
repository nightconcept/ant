#!/usr/bin/env python3
import sys
import os
import time
import urllib.request
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPS_DIR = REPO_ROOT / ".deps" / "compliance"

# ANSI Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Official Upstream Online Smoke Test Manifests
PULLED_SMOKE_TESTS = {
    "tier1": [
        {
            "name": "Test262: Array.prototype.map (15.4.4.19-1-1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Array/prototype/map/15.4.4.19-1-1.js",
            "filename": "t262_array_map_1.js",
            "type": "test262"
        },
        {
            "name": "Test262: Array.prototype.indexOf (15.4.4.14-1-1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Array/prototype/indexOf/15.4.4.14-1-1.js",
            "filename": "t262_array_indexof.js",
            "type": "test262"
        },
        {
            "name": "Test262: Math.abs (S15.8.2.1_A1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Math/abs/S15.8.2.1_A1.js",
            "filename": "t262_math_abs.js",
            "type": "test262"
        },
        {
            "name": "Test262: Object.create (15.2.3.5-1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Object/create/15.2.3.5-1.js",
            "filename": "t262_object_create.js",
            "type": "test262"
        },
        {
            "name": "Test262: Reflect.has (return-boolean)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Reflect/has/return-boolean.js",
            "filename": "t262_reflect_has.js",
            "type": "test262"
        }
    ],
    "tier2": [
        {
            "name": "Node.js: events.once (test-events-once.js)",
            "url": "https://raw.githubusercontent.com/nodejs/node/main/test/parallel/test-events-once.js",
            "filename": "node_events_once.cjs",
            "type": "node"
        },
        {
            "name": "Node.js: buffer inheritance (test-buffer-inheritance.js)",
            "url": "https://raw.githubusercontent.com/nodejs/node/main/test/parallel/test-buffer-inheritance.js",
            "filename": "node_buffer_inheritance.cjs",
            "type": "node"
        },
        {
            "name": "Node.js: buffer iterator (test-buffer-iterator.js)",
            "url": "https://raw.githubusercontent.com/nodejs/node/main/test/parallel/test-buffer-iterator.js",
            "filename": "node_buffer_iterator.cjs",
            "type": "node"
        },
        {
            "name": "Node.js: stream readable event (test-stream-readable-event.js)",
            "url": "https://raw.githubusercontent.com/nodejs/node/main/test/parallel/test-stream-readable-event.js",
            "filename": "node_stream_readable_event.cjs",
            "type": "node"
        },
        {
            "name": "Node.js: process.uptime (test-process-uptime.js)",
            "url": "https://raw.githubusercontent.com/nodejs/node/main/test/parallel/test-process-uptime.js",
            "filename": "node_process_uptime.cjs",
            "type": "node"
        }
    ],
    "tier3": [
        {
            "name": "Test262: Promise.resolve (S25.4.4.5_A1.1_T1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Promise/resolve/S25.4.4.5_A1.1_T1.js",
            "filename": "t262_promise_resolve.js",
            "type": "test262"
        },
        {
            "name": "Test262: Promise.all (S25.4.4.1_A1.1_T1)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Promise/all/S25.4.4.1_A1.1_T1.js",
            "filename": "t262_promise_all.js",
            "type": "test262"
        },
        {
            "name": "Test262: Array.prototype.map (15.4.4.19-1-10)",
            "url": "https://raw.githubusercontent.com/tc39/test262/main/test/built-ins/Array/prototype/map/15.4.4.19-1-10.js",
            "filename": "t262_array_map_10.js",
            "type": "test262"
        }
    ]
}

def find_ant_binary() -> Path:
    local_ant = REPO_ROOT / "build" / "ant"
    if local_ant.exists() and os.access(local_ant, os.X_OK):
        return local_ant
    
    import shutil
    sys_ant = shutil.which("ant")
    if sys_ant:
        return Path(sys_ant)
        
    raise RuntimeError(
        f"Ant binary not found at {local_ant}. Please run 'just build' or 'meson compile -C build' first."
    )

def ensure_test262_harness() -> tuple[Path, Path]:
    harness_dir = DEPS_DIR / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    
    assert_js = harness_dir / "assert.js"
    sta_js = harness_dir / "sta.js"
    
    headers = {"User-Agent": "ant-compliance-runner"}
    
    if not assert_js.exists():
        url = "https://raw.githubusercontent.com/tc39/test262/main/harness/assert.js"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(assert_js, "wb") as f:
            f.write(resp.read())

    if not sta_js.exists():
        url = "https://raw.githubusercontent.com/tc39/test262/main/harness/sta.js"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(sta_js, "wb") as f:
            f.write(resp.read())
            
    return assert_js, sta_js

def fetch_pulled_test(spec: dict) -> Path:
    pulled_dir = DEPS_DIR / "pulled"
    pulled_dir.mkdir(parents=True, exist_ok=True)
    
    target_path = pulled_dir / spec["filename"]
    
    if not target_path.exists():
        headers = {"User-Agent": "ant-compliance-runner"}
        req = urllib.request.Request(spec["url"], headers=headers)
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            
        if spec["type"] == "test262":
            assert_js, sta_js = ensure_test262_harness()
            harness_code = assert_js.read_text() + "\n" + sta_js.read_text() + "\n"
            content = harness_code + content
        elif spec["type"] == "node":
            content = content.replace(
                "require('../common')",
                "(function(){ return { mustCall: (f) => f || (() => {}), mustNotCall: () => {} }; })()"
            )
            
        target_path.write_text(content)
        
    return target_path

def run_js_test(ant_bin: Path, test_path: Path, timeout_sec: float = 15.0) -> tuple[bool, float, str]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(ant_bin), str(test_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            cwd=REPO_ROOT
        )
        duration_ms = (time.perf_counter() - start) * 1000.0
        output = proc.stdout + proc.stderr
        passed = (proc.returncode == 0)
        return passed, duration_ms, output
    except subprocess.TimeoutExpired:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return False, duration_ms, f"TIMEOUT after {timeout_sec}s"
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return False, duration_ms, str(e)

class SummaryTracker:
    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.results = []

    def add(self, name: str, passed: bool, duration_ms: float, category: str = "General", details: str = ""):
        self.results.append({
            "name": name,
            "passed": passed,
            "duration_ms": duration_ms,
            "category": category,
            "details": details
        })
        status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{status_str}] {name} ({duration_ms:.1f}ms)")
        if not passed and details:
            for line in details.strip().split("\n")[:5]:
                print(f"        {YELLOW}| {line}{RESET}")

    def print_summary(self):
        total = len(self.results)
        if total == 0:
            print(f"\n{BOLD}No tests executed for {self.suite_name}{RESET}")
            return 0

        passed_cnt = sum(1 for r in self.results if r["passed"])
        failed_cnt = total - passed_cnt
        pass_pct = (passed_cnt / total) * 100.0

        print("\n" + "=" * 60)
        print(f"{BOLD}Summary: {self.suite_name}{RESET}")
        print("=" * 60)
        print(f"Total Tests : {total}")
        print(f"Passed      : {GREEN}{passed_cnt}{RESET}")
        print(f"Failed      : {RED}{failed_cnt}{RESET}")
        print(f"Pass Rate   : {BOLD}{pass_pct:.1f}%{RESET}")
        print("=" * 60 + "\n")
        return 0 if failed_cnt == 0 else 1
