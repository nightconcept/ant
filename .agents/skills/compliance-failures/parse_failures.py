#!/usr/bin/env python3
"""Parse Ant named compliance-suite logs into structured failure data.

Logs live in .deps/compliance/logs/<suite>_<timestamp>.log and share one
block format:

    [FAIL] <test name> (<time>ms)
    --- output ---
    <captured stdout/stderr, ends with the error>
    --------------

Only failures are emitted to the log (passes are counted in the summary only).
This script locates the latest log per suite, extracts every [FAIL] block, pulls
the primary error type + message, and prints either a human summary or JSON.

Usage:
    parse_failures.py                       # summary of all suites
    parse_failures.py --suite test262       # only Test262
    parse_failures.py --suite regression --list
    parse_failures.py --suite test262 --group category
    parse_failures.py --suite test262 --group message
    parse_failures.py --suite test262 --filter Temporal
    parse_failures.py --json          # machine-readable, for follow-up tooling
    parse_failures.py --log <path>    # parse a specific log file
    parse_failures.py --require-current  # exit non-zero if the log is stale

Prefer the JSON manifest (`<log>.json`, next to the log) for a first pass -
it is a few KB and already carries per-category totals and failing-test
names; this script's grouping/message analysis is for drilling into the
`.log` file the manifest points at. See docs/repo/compliance.md.

Staleness: every log records the commit and tree state it was produced at
(`Commit:` / `Branch:` / `Tree:` in the header, and `<sha>[-dirty]` in the
filename). Test262 runs take long enough that a log routinely outlives the
code it describes. This script checks whether the log's commit is still an
ancestor of HEAD and warns loudly (see `staleness_of`) if not, if the tree
was dirty, or if no commit can be determined at all (old logs).
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

LOG_DIR = os.path.join(".deps", "compliance", "logs")

FAIL_RE = re.compile(r"^\[FAIL\]\s+(.*?)\s+\(([\d.]+m?s)\)\s*$")
# Lines like "TypeError: ...", "Error: ...", "Test262Error: ...", plus bare TIMEOUT.
# The optional prefix lets the bare word "Error" match as well as "ReferenceError".
ERR_RE = re.compile(r"^((?:[A-Z][A-Za-z0-9]*)?Error)\s*:\s*(.*)$")
DASHES_RE = re.compile(r"^-{6,}\s*$")

HEADER_COMMIT_RE = re.compile(r"^Commit\s*:\s*([0-9a-fA-F]+)", re.MULTILINE)
HEADER_BRANCH_RE = re.compile(r"^Branch\s*:\s*(.+)$", re.MULTILINE)
HEADER_TREE_RE = re.compile(r"^Tree\s*:\s*(\w+)", re.MULTILINE)
FILENAME_SHA_RE = re.compile(
    r"^(?:regression|test262|tier\d+)_\d{8}_\d{6}_"
    r"([0-9a-fA-F]{6,40})(-dirty)?\.log$"
)


def revision_of(path, text):
    """Extract {commit, short, dirty, branch} from a log's header, falling
    back to the filename. Fields are None/False when undeterminable (logs
    that predate this tracking carry neither)."""
    commit = None
    dirty = False
    branch = None

    m = HEADER_COMMIT_RE.search(text)
    if m:
        commit = m.group(1)
        tm = HEADER_TREE_RE.search(text)
        if tm:
            dirty = tm.group(1).strip().lower() == "dirty"
        bm = HEADER_BRANCH_RE.search(text)
        if bm:
            branch = bm.group(1).strip()
    else:
        fm = FILENAME_SHA_RE.match(os.path.basename(path))
        if fm:
            commit = fm.group(1)
            dirty = bool(fm.group(2))

    return {
        "commit": commit,
        "short": commit[:8] if commit else None,
        "dirty": dirty,
        "branch": branch,
    }


def is_ancestor_of_head(commit):
    """True/False if determinable, None if git can't tell (unknown object, no repo, etc)."""
    if not commit:
        return None
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return r.returncode == 0
    except Exception:
        return None


def staleness_of(rev):
    """Return (stale: bool, reasons: [str]) describing why a log might not
    reflect the current binary."""
    if not rev["commit"]:
        return True, ["no commit recorded in this log (predates staleness tracking)"]

    reasons = []
    if rev["dirty"]:
        reasons.append("produced from a dirty working tree (not reproducible from the commit alone)")

    ancestor = is_ancestor_of_head(rev["commit"])
    if ancestor is False:
        reasons.append(f"commit {rev['short']} is not an ancestor of HEAD - it may already be fixed")
    elif ancestor is None:
        reasons.append(f"commit {rev['short']} is unknown to this repo - cannot verify ancestry")

    return bool(reasons), reasons


def latest_log(suite):
    pattern = os.path.join(LOG_DIR, f"{suite}_*.log")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def parse_summary(text):
    """Extract the trailing Summary block counts."""
    out = {}
    for key, field in (
        ("Total Tests", "total"),
        ("Passed", "passed"),
        ("Failed", "failed"),
        ("Pass Rate", "pass_rate"),
    ):
        m = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE)
        if m:
            out[field] = m.group(1).strip()
    return out


def extract_error(body_lines):
    """Return (error_type, message) from a failure body."""
    joined = body_lines
    # TIMEOUT is emitted as a bare line.
    for line in joined:
        if line.strip() == "TIMEOUT" or line.strip().startswith("TIMEOUT after"):
            return "TIMEOUT", line.strip()
    # Prefer the LAST matching *Error line (the thrown error, past assert frames).
    err_type, err_msg = None, ""
    for line in joined:
        m = ERR_RE.match(line.strip())
        if m:
            err_type, err_msg = m.group(1), m.group(2).strip()
    if err_type:
        return err_type, err_msg
    # Fallback: first non-empty content line.
    for line in joined:
        if line.strip():
            return "Unknown", line.strip()[:200]
    return "Unknown", ""


def normalize_message(msg):
    """Collapse variable bits so similar failures group together."""
    m = re.sub(r"'[^']*'", "'X'", msg)
    m = re.sub(r'"[^"]*"', '"X"', m)
    m = re.sub(r"\b\d+\b", "N", m)
    m = re.sub(r"tmp_t262_w\d+", "tmp_t262", m)
    return m.strip()[:160]


def category_of(name):
    """Coarse bucket for grouping, e.g. Test262: built-ins/Temporal."""
    m = re.match(r"Test262:\s*([^/]+/[^/]+)", name)
    if m:
        return f"Test262: {m.group(1)}"
    m = re.match(r"(Test262):\s*([^/]+)", name)
    if m:
        return f"Test262: {m.group(2)}"
    return name


def parse_log(path):
    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()

    failures = []
    i = 0
    n = len(lines)
    while i < n:
        m = FAIL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name, timing = m.group(1), m.group(2)
        i += 1
        # Skip the "--- output ---" marker if present.
        if i < n and lines[i].strip().startswith("--- output"):
            i += 1
        body = []
        while i < n and not DASHES_RE.match(lines[i]) and not FAIL_RE.match(lines[i]):
            body.append(lines[i])
            i += 1
        err_type, err_msg = extract_error(body)
        failures.append(
            {
                "test": name,
                "time": timing,
                "error_type": err_type,
                "message": err_msg,
                "category": category_of(name),
            }
        )
    return failures


def _staleness_entry(path, text):
    rev = revision_of(path, text)
    stale, reasons = staleness_of(rev)
    return {"revision": rev, "stale": stale, "reasons": reasons}


def load(suite=None, log=None):
    """Return {suite_id: (path, summary_dict, [failures], staleness_dict)}."""
    results = {}
    if log:
        text = open(log, errors="replace").read()
        results[os.path.basename(log)] = (log, parse_summary(text), parse_log(log), _staleness_entry(log, text))
        return results
    suites = [suite] if suite else ["regression", "test262"]
    for suite_id in suites:
        path = latest_log(suite_id)
        if not path:
            continue
        text = open(path, errors="replace").read()
        results[suite_id] = (path, parse_summary(text), parse_log(path), _staleness_entry(path, text))
    return results


def print_staleness_warnings(results):
    """Print a prominent warning at the top of the report for any stale log."""
    stale_entries = [(label, path, st) for label, (path, summ, fails, st) in results.items() if st["stale"]]
    if not stale_entries:
        return
    print("!" * 72)
    print("! STALENESS WARNING")
    print("! One or more logs may not reflect the current binary. Failures below")
    print("! could already be fixed - re-verify against HEAD before acting on them.")
    print("!" * 72)
    for label, path, st in stale_entries:
        rev = st["revision"]
        sha = rev["short"] or "unknown"
        print(f"  [{label}] {os.path.basename(path)}")
        print(f"      commit: {sha}" + (f" (branch {rev['branch']})" if rev.get("branch") else ""))
        for reason in st["reasons"]:
            print(f"      - {reason}")
    print("!" * 72)
    print()


def cmd_summary(results):
    for label, (path, summ, fails, staleness) in results.items():
        print(f"=== {label} ({os.path.basename(path)}) ===")
        if summ:
            print(
                f"  Total {summ.get('total','?')}  "
                f"Passed {summ.get('passed','?')}  "
                f"Failed {summ.get('failed','?')}  "
                f"Rate {summ.get('pass_rate','?')}"
            )
        by_type = Counter(f["error_type"] for f in fails)
        if by_type:
            print("  Failures by error type:")
            for et, c in by_type.most_common():
                print(f"    {c:6d}  {et}")
        print()


def cmd_group(results, key):
    for label, (path, summ, fails, staleness) in results.items():
        print(f"=== {label}: grouped by {key} ===")
        buckets = Counter()
        for f in fails:
            if key == "category":
                buckets[f["category"]] += 1
            elif key == "message":
                buckets[f"{f['error_type']}: {normalize_message(f['message'])}"] += 1
            elif key == "type":
                buckets[f["error_type"]] += 1
        for k, c in buckets.most_common(40):
            print(f"  {c:6d}  {k}")
        print()


def cmd_list(results, filt):
    for label, (path, summ, fails, staleness) in results.items():
        shown = [f for f in fails if not filt or filt.lower() in f["test"].lower()]
        print(f"=== {label}: {len(shown)} failing tests"
              + (f" matching '{filt}'" if filt else "") + " ===")
        for f in shown:
            msg = f["message"][:100]
            print(f"  {f['test']}\n      [{f['error_type']}] {msg}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", choices=["regression", "test262"])
    ap.add_argument("--log", help="parse a specific log file")
    ap.add_argument("--list", action="store_true", help="list every failing test")
    ap.add_argument("--group", choices=["category", "message", "type"])
    ap.add_argument("--filter", dest="filt", help="substring filter on test name")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--require-current",
        action="store_true",
        help="exit non-zero if any selected log is stale (dirty, superseded, or has no known commit)",
    )
    args = ap.parse_args()

    results = load(suite=args.suite, log=args.log)
    if not results:
        print("No compliance logs found in " + LOG_DIR, file=sys.stderr)
        return 1

    any_stale = any(st["stale"] for _, (_, _, _, st) in results.items())

    if args.json:
        out = {
            label: {"log": path, "summary": summ, "failures": fails, "staleness": st}
            for label, (path, summ, fails, st) in results.items()
        }
        print(json.dumps(out, indent=2))
        if args.require_current and any_stale:
            return 1
        return 0

    print_staleness_warnings(results)

    if args.group:
        cmd_group(results, args.group)
    elif args.list or args.filt:
        cmd_list(results, args.filt)
    else:
        cmd_summary(results)

    if args.require_current and any_stale:
        print("error: --require-current: one or more logs are stale (see warning above)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
