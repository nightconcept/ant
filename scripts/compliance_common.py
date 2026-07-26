#!/usr/bin/env python3
import sys
import os
import re
import time
import urllib.request
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPS_DIR = REPO_ROOT / ".deps" / "compliance"
LOGS_DIR = DEPS_DIR / "logs"

# ANSI Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

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

# Test262 host-provided `$262` object. Test262 assumes the host injects this
# global (see test262/INTERPRETING.md); ant, as a runtime, does not ship it, so
# hundreds of tests fail with `ReferenceError: '$262' is not defined`. We provide
# a best-effort shim built from primitives ant actually exposes:
#   - global            -> globalThis
#   - evalScript(src)   -> indirect eval (runs as global-scope Script)
#   - detachArrayBuffer -> ArrayBuffer.prototype.transfer() (detaches the buffer)
#   - gc()              -> globalThis.gc() if present, else a safe no-op
# Capabilities ant lacks (agent/createRealm/IsHTMLDDA/AbstractModuleSource) are
# intentionally omitted: those tests still fail, but with an accurate error about
# the missing feature rather than a spurious `$262` ReferenceError.
T262_HOST_262_SHIM = (
    "if (typeof $262 === 'undefined') {"
    " Object.defineProperty(globalThis, '$262', {"
    " writable: true, enumerable: false, configurable: true, value: {"
    " global: globalThis,"
    " evalScript: function(src) { return (0, eval)(src); },"
    " gc: function() { if (typeof globalThis.gc === 'function') return globalThis.gc(); },"
    " detachArrayBuffer: function(buffer) {"
    " if (buffer && typeof buffer.transfer === 'function') { buffer.transfer(); }"
    " return null; }"
    " } });"
    " }"
)


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

def ensure_test262_repo() -> Path:
    """Ensure Test262 suite repository is checked out locally."""
    root_t262 = REPO_ROOT / "test262"
    if (root_t262 / "test").exists():
        return root_t262
    
    deps_t262 = DEPS_DIR / "test262"
    if (deps_t262 / "test").exists():
        return deps_t262

    print(f"{CYAN}Cloning tc39/test262 repository into {deps_t262}...{RESET}")
    deps_t262.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/tc39/test262.git", str(deps_t262)],
        check=True
    )
    return deps_t262

def parse_test262_frontmatter(content: str) -> dict:
    frontmatter = {"includes": [], "flags": [], "negative": None}
    match = re.search(r"/\*---(.*?)---\*/", content, re.DOTALL)
    if match:
        block = match.group(1)
        
        inc_match = re.search(r"includes:\s*\[(.*?)\]", block)
        if inc_match:
            frontmatter["includes"] = [x.strip() for x in inc_match.group(1).split(",") if x.strip()]
        else:
            inc_list = re.findall(r"includes:.*?\n((?:\s*-\s*.*?\n)+)", block)
            if inc_list:
                frontmatter["includes"] = [x.strip().lstrip("- ").strip() for x in inc_list[0].splitlines()]

        flags_match = re.search(r"flags:\s*\[(.*?)\]", block)
        if flags_match:
            frontmatter["flags"] = [x.strip() for x in flags_match.group(1).split(",") if x.strip()]

        if "negative:" in block:
            neg_type_match = re.search(r"type:\s*(\w+)", block)
            neg_phase_match = re.search(r"phase:\s*(\w+)", block)
            frontmatter["negative"] = {
                "type": neg_type_match.group(1) if neg_type_match else None,
                "phase": neg_phase_match.group(1) if neg_phase_match else None
            }
    return frontmatter

def prepare_test262_code(test_file: Path, test262_dir: Path) -> tuple[str, dict]:
    harness_dir = test262_dir / "harness"
    content = test_file.read_text(encoding="utf-8", errors="replace")
    fm = parse_test262_frontmatter(content)
    
    # Host-provided globals must exist before any harness code runs: some includes
    # (e.g. atomicsHelper.js) touch `$262` at load time, so the shims go first.
    parts = [
        "if (typeof $DONE === 'undefined') { globalThis.$DONE = function(err) { if (err) throw err; }; }",
        T262_HOST_262_SHIM,
    ]
    assert_js = harness_dir / "assert.js"
    sta_js = harness_dir / "sta.js"
    if assert_js.exists():
        parts.append(assert_js.read_text(encoding="utf-8", errors="replace"))
    if sta_js.exists():
        parts.append(sta_js.read_text(encoding="utf-8", errors="replace"))

    for inc in fm.get("includes", []):
        inc_path = harness_dir / inc
        if inc_path.exists():
            parts.append(inc_path.read_text(encoding="utf-8", errors="replace"))
    
    flags = fm.get("flags", [])
    if "onlyStrict" in flags:
        parts.append('"use strict";')
        
    parts.append(content)
    return "\n".join(parts), fm

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

def make_log_path(label: str) -> Path:
    """Return a timestamped log path under .deps/compliance/logs/."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = label.lower().replace(" ", "_").replace("/", "_")
    return LOGS_DIR / f"{safe}_{ts}.log"

class SummaryTracker:
    def __init__(self, suite_name: str, log_path: Path | None = None, log_fail_only: bool = False):
        self.suite_name = suite_name
        self.results = []
        self.log_path = log_path
        self.log_fail_only = log_fail_only
        self._log_file = None

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self.log_path, "w", encoding="utf-8")
            self._log_file.write(f"=== {suite_name} ===\n")
            self._log_file.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def _write_log(self, text: str):
        if self._log_file:
            self._log_file.write(strip_ansi(text) + "\n")
            self._log_file.flush()

    def add(self, name: str, passed: bool, duration_ms: float, category: str = "General", details: str = ""):
        self.results.append({
            "name": name,
            "passed": passed,
            "duration_ms": duration_ms,
            "category": category,
            "details": details
        })
        status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        status_plain = "PASS" if passed else "FAIL"
        print(f"  [{status_str}] {name} ({duration_ms:.1f}ms)")
        if not passed and details:
            for line in details.strip().split("\n")[:5]:
                print(f"        {YELLOW}| {line}{RESET}")

        # Write to log
        if self._log_file:
            should_log = (not self.log_fail_only) or (not passed)
            if should_log:
                self._write_log(f"[{status_plain}] {name} ({duration_ms:.1f}ms)")
                if details:
                    self._write_log("--- output ---")
                    self._write_log(details.rstrip())
                    self._write_log("-" * 14)
                self._write_log("")

    def add_raw_log(self, header: str, content: str):
        """Write a block of raw output to the log (used for full-suite subprocess output)."""
        if self._log_file:
            self._write_log(f"--- {header} ---")
            self._write_log(strip_ansi(content).rstrip())
            self._write_log("-" * (len(header) + 8))
            self._write_log("")

    def print_summary(self) -> int:
        total = len(self.results)
        if total == 0:
            print(f"\n{BOLD}No tests executed for {self.suite_name}{RESET}")
            if self._log_file:
                self._write_log("No tests executed.")
                self._close_log(0)
            return 0

        passed_cnt = sum(1 for r in self.results if r["passed"])
        failed_cnt = total - passed_cnt
        pass_pct = (passed_cnt / total) * 100.0

        summary_lines = [
            "",
            "=" * 60,
            f"Summary: {self.suite_name}",
            "=" * 60,
            f"Total Tests : {total}",
            f"Passed      : {passed_cnt}",
            f"Failed      : {failed_cnt}",
            f"Pass Rate   : {pass_pct:.1f}%",
            "=" * 60,
            "",
        ]

        print("\n" + "=" * 60)
        print(f"{BOLD}Summary: {self.suite_name}{RESET}")
        print("=" * 60)
        print(f"Total Tests : {total}")
        print(f"Passed      : {GREEN}{passed_cnt}{RESET}")
        print(f"Failed      : {RED}{failed_cnt}{RESET}")
        print(f"Pass Rate   : {BOLD}{pass_pct:.1f}%{RESET}")
        print("=" * 60 + "\n")

        if self._log_file:
            for line in summary_lines:
                self._write_log(line)
            exit_code = 0 if failed_cnt == 0 else 1
            self._close_log(exit_code)

        return 0 if failed_cnt == 0 else 1

    def _close_log(self, exit_code: int):
        if self._log_file:
            self._write_log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')} (exit {exit_code})")
            self._log_file.close()
            self._log_file = None
            mode = "fail-only" if self.log_fail_only else "full"
            print(f"  {CYAN}Log ({mode}): {self.log_path}{RESET}")
