#!/usr/bin/env python3
from __future__ import annotations
import sys
import os
import re
import time
import json
import shutil
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent
DEPS_DIR = REPO_ROOT / ".deps" / "compliance"
LOGS_DIR = DEPS_DIR / "logs"
BIN_DIR = REPO_ROOT / "bin"
VERSIONS_PATH = REPO_ROOT / "versions.json"

# ANSI Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

def pad_cell(text: str, width: int, align="left") -> str:
    visible_len = len(strip_ansi(text))
    padding = max(0, width - visible_len)
    if align == "right":
        return " " * padding + text
    elif align == "center":
        left = padding // 2
        right = padding - left
        return " " * left + text + " " * right
    return text + " " * padding

def git_revision() -> dict:
    repo_base = REPO_ROOT.parent if REPO_ROOT.name == "bench" else REPO_ROOT
    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=repo_base,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
            )
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            return ""

    commit = _git("rev-parse", "HEAD")
    if not commit:
        return {"commit": "unknown", "short": "unknown", "dirty": False, "branch": "unknown", "subject": ""}

    return {
        "commit": commit,
        "short": commit[:8],
        "dirty": bool(_git("status", "--porcelain")),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        "subject": _git("log", "-1", "--format=%s"),
    }

# Default Runtimes Specification
DEFAULT_RUNTIMES = [
    {
        "id": "ant",
        "name": "ant",
        "binary_path": "bin/ant",
        "args": [],
        "color": GREEN
    },
    {
        "id": "tjs",
        "name": "txiki.js",
        "binary_path": "bin/tjs",
        "args": ["run"],
        "color": YELLOW
    },
    {
        "id": "node",
        "name": "Node.js",
        "binary_path": "node",
        "args": [],
        "color": BLUE
    },
    {
        "id": "deno",
        "name": "Deno",
        "binary_path": "bin/deno",
        "args": ["run", "-A"],
        "color": MAGENTA
    },
    {
        "id": "bun",
        "name": "Bun",
        "binary_path": "bin/bun",
        "args": ["run"],
        "color": CYAN
    }
]

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

def resolve_binary_path(path_str: str, r_id: str | None = None) -> Path | None:
    """Resolve binary path relative to REPO_ROOT, system PATH, or mise."""
    if r_id == "ant" or path_str == "bin/ant" or "build/ant" in path_str:
        build_bin = REPO_ROOT.parent / "build" / "ant"
        if build_bin.exists() and build_bin.is_file() and build_bin.stat().st_size > 0:
            target = BIN_DIR / "ant"
            try:
                BIN_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(build_bin, target)
                target.chmod(target.stat().st_mode | 0o755)
            except Exception:
                pass
            return target
        target = BIN_DIR / "ant"
        if target.exists() and target.is_file() and target.stat().st_size > 0:
            target.chmod(target.stat().st_mode | 0o755)
            return target

    p = Path(path_str)
    if p.is_absolute():
        if p.exists() and p.is_file():
            return p
    else:
        rel_p = REPO_ROOT / p
        if rel_p.exists() and rel_p.is_file():
            return rel_p

        bin_p = BIN_DIR / p.name
        if bin_p.exists() and bin_p.is_file():
            return bin_p

    which_path = shutil.which(path_str)
    if which_path:
        return Path(which_path)

    base_name = p.name
    which_base = shutil.which(base_name)
    if which_base:
        return Path(which_base)

    if r_id:
        which_id = shutil.which(r_id)
        if which_id:
            return Path(which_id)

    if shutil.which("mise"):
        for candidate in [path_str, base_name, r_id]:
            if not candidate:
                continue
            try:
                res = subprocess.run(["mise", "which", candidate], capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    mp = Path(res.stdout.strip())
                    if mp.exists():
                        return mp
            except Exception:
                pass

    return None

def load_runtimes(filter_ids: list[str] | None = None, extra_runtimes: list[dict] | None = None) -> list[dict]:
    """Load and resolve runtimes from versions.json, defaults, and custom additions."""
    runtimes_map = {}

    # Load defaults
    for r in DEFAULT_RUNTIMES:
        runtimes_map[r["id"]] = dict(r)

    # Merge versions.json if present
    if VERSIONS_PATH.exists():
        try:
            with open(VERSIONS_PATH, "r") as f:
                vdata = json.load(f)
                vruntimes = vdata.get("runtimes", {})
                for r_id, r_info in vruntimes.items():
                    if r_id not in runtimes_map:
                        runtimes_map[r_id] = {
                            "id": r_id,
                            "name": r_info.get("name", r_id),
                            "binary_path": r_info.get("binary_path", r_id),
                            "args": r_info.get("args", []),
                            "color": CYAN
                        }
                    else:
                        if "binary_path" in r_info:
                            runtimes_map[r_id]["binary_path"] = r_info["binary_path"]
                        if "args" in r_info:
                            runtimes_map[r_id]["args"] = r_info["args"]
                        if "name" in r_info:
                            runtimes_map[r_id]["name"] = r_info["name"]
        except Exception as e:
            print(f"{YELLOW}Warning: Could not parse versions.json: {e}{RESET}")

    # Add extra runtime specs passed dynamically
    if extra_runtimes:
        for ex in extra_runtimes:
            runtimes_map[ex["id"]] = ex

    resolved_runtimes = []
    for r_id, r_spec in runtimes_map.items():
        if filter_ids and r_id not in filter_ids:
            continue
        
        resolved = resolve_binary_path(r_spec["binary_path"], r_id=r_id)
        if resolved:
            r_copy = dict(r_spec)
            r_copy["resolved_path"] = resolved
            resolved_runtimes.append(r_copy)
        else:
            if filter_ids and r_id in filter_ids:
                print(f"{YELLOW}Warning: Binary for runtime '{r_id}' ({r_spec['binary_path']}) not found. Skipping.{RESET}")

    return resolved_runtimes

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
    
    parts = []
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
            
    parts.append("if (typeof $DONE === 'undefined') { globalThis.$DONE = function(err) { if (err) throw err; }; }")
    
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

def run_js_test(runtime: dict, test_path: Path, timeout_sec: float = 15.0) -> tuple[bool, float, str]:
    bin_path = runtime["resolved_path"]
    args = runtime.get("args", [])
    cmd = [str(bin_path)] + args + [str(test_path)]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
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

class MultiRuntimeTracker:
    def __init__(self, tier_name: str, runtimes: list[dict], log_path: Path | None = None, log_fail_only: bool = False):
        self.tier_name = tier_name
        self.runtimes = runtimes
        self.log_path = log_path
        self.log_fail_only = log_fail_only
        self.test_records = []  # [{ "name": ..., "results": { r_id: { passed, duration_ms, details } } }]
        self._log_file = None

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self.log_path, "w", encoding="utf-8")
            self._log_file.write(f"=== {tier_name} ===\n")
            self._log_file.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def _write_log(self, text: str):
        if self._log_file:
            self._log_file.write(strip_ansi(text) + "\n")
            self._log_file.flush()

    def add_test(self, test_name: str, results_by_runtime: dict, print_output: bool = True):
        """
        results_by_runtime: { r_id: { "passed": bool, "duration_ms": float, "details": str } }
        """
        self.test_records.append({
            "name": test_name,
            "results": results_by_runtime
        })

        if print_output:
            print(f"\n  {BOLD}Test:{RESET} {CYAN}{test_name}{RESET}")
            for r in self.runtimes:
                r_id = r["id"]
                res = results_by_runtime.get(r_id, {})
                passed = res.get("passed", False)
                duration_ms = res.get("duration_ms", 0.0)
                details = res.get("details", "")

                status_str = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"

                r_color = r.get("color", "")
                r_name_padded = pad_cell(f"{r_color}{r['name']}{RESET}", 14)
                print(f"    [{status_str}] {r_name_padded} ({duration_ms:.1f}ms)")

                if not passed and details:
                    first_line = details.strip().split("\n")[0] if details else ""
                    if first_line:
                        print(f"          {YELLOW}└─ {first_line[:80]}{RESET}")

        if self._log_file:
            for r in self.runtimes:
                res = results_by_runtime.get(r["id"], {})
                passed = res.get("passed", False)
                duration_ms = res.get("duration_ms", 0.0)
                details = res.get("details", "")
                should_log = (not self.log_fail_only) or (not passed)
                if should_log:
                    status_plain = "PASS" if passed else "FAIL"
                    self._write_log(f"[{status_plain}] {r['name']} - {test_name} ({duration_ms:.1f}ms)")
                    if details:
                        self._write_log("--- output ---")
                        self._write_log(details.rstrip())
                        self._write_log("-" * 14)

    def print_tier_summary(self, width: int = 90) -> dict:
        """
        Print tier summary box and return runtime stats dict:
        { r_id: { "total": int, "passed": int, "failed": int, "pass_pct": float } }
        """
        stats = {}
        for r in self.runtimes:
            r_id = r["id"]
            total = len(self.test_records)
            passed_cnt = sum(1 for tr in self.test_records if tr["results"].get(r_id, {}).get("passed", False))
            failed_cnt = total - passed_cnt
            pass_pct = (passed_cnt / total * 100.0) if total > 0 else 0.0
            stats[r_id] = {
                "total": total,
                "passed": passed_cnt,
                "failed": failed_cnt,
                "pass_pct": pass_pct
            }

        lines = [
            f"{BOLD}{MAGENTA}Summary: {self.tier_name}{RESET}",
            "─" * (width - 6),
            f"{BOLD}{pad_cell('Runtime', 16)} {pad_cell('Total', 10, 'right')} {pad_cell('Passed', 10, 'right')} {pad_cell('Failed', 10, 'right')} {pad_cell('Pass Rate', 14, 'right')}{RESET}",
            "─" * (width - 6),
        ]

        for r in self.runtimes:
            r_id = r["id"]
            st = stats[r_id]
            r_colored = f"{r.get('color', '')}{pad_cell(r['name'], 16)}{RESET}"
            pct_colored = f"{GREEN}{st['pass_pct']:.1f}%{RESET}" if st['pass_pct'] == 100.0 else f"{YELLOW}{st['pass_pct']:.1f}%{RESET}" if st['pass_pct'] >= 50.0 else f"{RED}{st['pass_pct']:.1f}%{RESET}"
            lines.append(
                f"{r_colored} {pad_cell(str(st['total']), 10, 'right')} {pad_cell(str(st['passed']), 10, 'right')} {pad_cell(str(st['failed']), 10, 'right')} {pad_cell(pct_colored, 14, 'right')}"
            )

        lines.append("─" * (width - 6))

        box = []
        box.append("\n┌" + "─" * (width - 2) + "┐")
        for l in lines:
            box.append("│  " + pad_cell(l, width - 6) + "  │")
        box.append("└" + "─" * (width - 2) + "┘\n")
        print("\n".join(box))

        if self._log_file:
            self._write_log(f"Summary for {self.tier_name}:")
            for r in self.runtimes:
                st = stats[r["id"]]
                self._write_log(f"  {r['name']}: {st['passed']}/{st['total']} ({st['pass_pct']:.1f}%)")
            self._close_log()

        return stats

    def _close_log(self):
        if self._log_file:
            self._write_log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            self._log_file.close()
            self._log_file = None
            mode = "fail-only" if self.log_fail_only else "full"
            print(f"  {CYAN}Log ({mode}): {self.log_path}{RESET}")
