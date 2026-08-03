#!/usr/bin/env python3
import sys
import os
import re
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPS_DIR = REPO_ROOT / ".deps" / "compliance"
LOGS_DIR = DEPS_DIR / "logs"
VERSIONS_FILE = REPO_ROOT / ".github" / "versions.json"

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


def git_revision() -> dict:
    """Describe the tree the suite is being run against.

    Compliance percentages are only comparable between runs at the same
    revision, and a log that does not say which commit produced it will be
    misread later (a fix landed after the run looks like a live failure). So
    every log records the commit, whether the tree was dirty, and the branch.
    """
    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
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

def revision_tag(rev: dict) -> str:
    """Short `<short-sha>` / `<short-sha>-dirty` tag used in log filenames."""
    return f"{rev['short']}-dirty" if rev["dirty"] else rev["short"]

# Mirrors `category_of()` in `.claude/skills/compliance-failures/parse_failures.py`.
# Kept as a separate copy on purpose: that script parses historical log text and
# must keep working standalone against old logs, while this one buckets live
# results as they are recorded. If the naming convention for test names changes,
# update both.
def category_of(name: str) -> str:
    """Coarse bucket for grouping, e.g. Test262: built-ins/Temporal."""
    m = re.match(r"Test262:\s*([^/]+/[^/]+)", name)
    if m:
        return f"Test262: {m.group(1)}"
    m = re.match(r"(Test262):\s*([^/]+)", name)
    if m:
        return f"Test262: {m.group(2)}"
    return name

def find_ant_binary() -> Path:
    local_ant = REPO_ROOT / "build" / "ant"
    if local_ant.exists() and os.access(local_ant, os.X_OK):
        expected = git_revision()["short"]
        try:
            result = subprocess.run(
                [str(local_ant), "--version-raw"],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Could not verify {local_ant}: {exc}") from exc
        version = result.stdout.strip()
        if result.returncode != 0 or expected == "unknown" or not re.search(
            rf"(?:^|\.){re.escape(expected)}(?:\.|$)", version
        ):
            raise RuntimeError(
                f"{local_ant} reports version {version or '(none)'}, but HEAD is {expected}. "
                "Reconfigure and rebuild before running compliance."
            )
        return local_ant
    
    import shutil
    sys_ant = shutil.which("ant")
    if sys_ant:
        return Path(sys_ant)
        
    raise RuntimeError(
        f"Ant binary not found at {local_ant}. Please run 'just build' or 'meson compile -C build' first."
    )

def pinned_test262_revision() -> str:
    revision = json.loads(VERSIONS_FILE.read_text())["dependencies"]["test262"]
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise RuntimeError(".github/versions.json must pin Test262 to a full commit SHA")
    return revision.lower()


def checkout_test262_revision(test262_dir: Path, revision: str) -> None:
    current = subprocess.run(
        ["git", "-C", str(test262_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()
    if current == revision:
        return

    print(f"{CYAN}Checking out pinned Test262 revision {revision[:12]}...{RESET}")
    subprocess.run(
        ["git", "-C", str(test262_dir), "fetch", "--depth", "1", "origin", revision],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(test262_dir), "checkout", "--detach", revision],
        check=True,
    )


def ensure_test262_repo() -> Path:
    """Ensure Test262 suite repository is checked out locally.

    Note: the checkout ships a `package.json`, which makes ant run the tests
    (which are executed in place, see run_compliance_test262) in CommonJS scope
    rather than as Scripts. Removing it fixes a handful of `noStrict` tests that
    assert `this === global`, but costs ~60 dynamic-import tests, so it is left
    alone. Fixing both needs an engine-side way to force Script semantics.
    """
    revision = pinned_test262_revision()
    root_t262 = REPO_ROOT / "test262"
    if (root_t262 / "test").exists():
        checkout_test262_revision(root_t262, revision)
        return root_t262

    deps_t262 = DEPS_DIR / "test262"
    if (deps_t262 / "test").exists():
        checkout_test262_revision(deps_t262, revision)
        return deps_t262

    print(f"{CYAN}Cloning pinned tc39/test262 repository into {deps_t262}...{RESET}")
    deps_t262.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/tc39/test262.git", str(deps_t262)],
        check=True
    )
    subprocess.run(
        ["git", "-C", str(deps_t262), "fetch", "--depth", "1", "origin", revision],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(deps_t262), "checkout", "--detach", revision],
        check=True,
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
    """Return a revision-tagged, timestamped log path under .deps/compliance/logs/.

    The commit is in the filename as well as the header so that agents can pick
    the right log (and spot a stale one) without opening a 20MB file.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = label.lower().replace(" ", "_").replace("/", "_")
    return LOGS_DIR / f"{safe}_{ts}_{revision_tag(git_revision())}.log"

class SummaryTracker:
    def __init__(self, suite_id: str, suite_name: str, log_path: Path | None = None, log_fail_only: bool = False, filter: str | None = None):
        if not suite_id or not re.fullmatch(r"[a-z0-9-]+", suite_id):
            raise ValueError(f"invalid suite_id: {suite_id!r}")
        self.suite_id = suite_id
        self.suite_name = suite_name
        self.results = []
        self.log_path = log_path
        self.log_fail_only = log_fail_only
        self.filter = filter
        self._log_file = None
        self.revision = git_revision()
        self.started = datetime.now(timezone.utc).isoformat()

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self.log_path, "w", encoding="utf-8")
            self._log_file.write(f"=== {suite_name} ===\n")
            self._log_file.write(f"Started  : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self._log_file.write(f"Commit   : {self.revision['commit']}\n")
            self._log_file.write(f"Branch   : {self.revision['branch']}\n")
            self._log_file.write(f"Tree     : {'dirty' if self.revision['dirty'] else 'clean'}\n")
            if self.revision["subject"]:
                self._log_file.write(f"Subject  : {self.revision['subject']}\n")
            self._log_file.write("\n")

        if self.revision["dirty"]:
            print(
                f"  {YELLOW}Warning: working tree is dirty; results are not reproducible "
                f"from commit {self.revision['short']} alone.{RESET}"
            )

    def _write_log(self, text: str):
        if self._log_file:
            self._log_file.write(strip_ansi(text) + "\n")
            self._log_file.flush()

    def add(self, name: str, passed: bool, duration_ms: float, category: str | None = None, details: str = ""):
        if category is None:
            category = category_of(name)
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

    def _build_manifest(self) -> dict:
        """Build the machine-readable per-run manifest (see docs/repo/compliance.md).

        This is the cheap, structured counterpart to the multi-MB `.log` file:
        agents should read this first and only drill into the log for the
        specific failing test output they need.
        """
        total = len(self.results)
        passed_cnt = sum(1 for r in self.results if r["passed"])
        failed_cnt = total - passed_cnt
        pass_rate = round((passed_cnt / total) * 100.0, 1) if total else 0.0

        categories: dict[str, dict] = {}
        for r in self.results:
            cat = categories.setdefault(r["category"], {
                "total": 0, "passed": 0, "failed": 0, "failing": [],
            })
            cat["total"] += 1
            if r["passed"]:
                cat["passed"] += 1
            else:
                cat["failed"] += 1
                cat["failing"].append(r["name"])
        for cat in categories.values():
            cat["failing"].sort()

        return {
            "schema_version": 2,
            "suite_id": self.suite_id,
            "suite": self.suite_name,
            "started": self.started,
            "finished": datetime.now(timezone.utc).isoformat(),
            "revision": self.revision,
            "filter": self.filter,
            "totals": {
                "total": total,
                "passed": passed_cnt,
                "failed": failed_cnt,
                "pass_rate": pass_rate,
            },
            "categories": categories,
        }

    def _write_manifest(self):
        """Write the JSON manifest next to the log file (same stem, .json suffix).

        Also refreshes a stable `<suite>-latest.json` symlink pointing at it, so
        callers (justfile recipes, CI, the compliance-failures skill) can find
        the manifest a run just produced without globbing the timestamped
        filenames and sorting by mtime.
        """
        if not self.log_path:
            return
        manifest_path = self.log_path.with_suffix(".json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(self._build_manifest(), f, indent=2)
                f.write("\n")
            print(f"  {CYAN}Manifest: {manifest_path}{RESET}")
        except Exception as e:
            print(f"  {YELLOW}Warning: failed to write manifest {manifest_path}: {e}{RESET}")
            return

        latest_path = LOGS_DIR / f"{self.suite_id}-latest.json"
        try:
            if latest_path.exists() or latest_path.is_symlink():
                latest_path.unlink()
            latest_path.symlink_to(manifest_path.name)
            print(f"  {CYAN}Latest  : {latest_path}{RESET}")
        except Exception as e:
            print(f"  {YELLOW}Warning: failed to update {latest_path}: {e}{RESET}")

    def print_summary(self) -> int:
        total = len(self.results)
        if total == 0:
            print(f"\n{BOLD}No tests executed for {self.suite_name}{RESET}")
            if self._log_file:
                self._write_log("No tests executed.")
                self._close_log(0)
                self._write_manifest()
            return 0

        passed_cnt = sum(1 for r in self.results if r["passed"])
        failed_cnt = total - passed_cnt
        pass_pct = (passed_cnt / total) * 100.0

        rev_label = revision_tag(self.revision)

        summary_lines = [
            "",
            "=" * 60,
            f"Summary: {self.suite_name}",
            "=" * 60,
            f"Commit      : {self.revision['commit']}"
            + (" (dirty)" if self.revision["dirty"] else ""),
            f"Branch      : {self.revision['branch']}",
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
        print(f"Commit      : {CYAN}{rev_label}{RESET} ({self.revision['branch']})")
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
            self._write_manifest()

        gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if gh_summary:
            try:
                with open(gh_summary, "a", encoding="utf-8") as f:
                    f.write(f"### Compliance Summary: {self.suite_name}\n\n")
                    f.write(f"Commit `{rev_label}` on `{self.revision['branch']}`\n\n")
                    f.write(f"| Total Tests | Passed | Failed | Pass Rate |\n")
                    f.write(f"| ----------- | ------ | ------ | --------- |\n")
                    f.write(f"| {total} | {passed_cnt} | {failed_cnt} | **{pass_pct:.1f}%** |\n\n")
            except Exception:
                pass

        return 0 if failed_cnt == 0 else 1

    def _close_log(self, exit_code: int):
        if self._log_file:
            self._write_log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')} (exit {exit_code})")
            self._log_file.close()
            self._log_file = None
            mode = "fail-only" if self.log_fail_only else "full"
            print(f"  {CYAN}Log ({mode}): {self.log_path}{RESET}")
