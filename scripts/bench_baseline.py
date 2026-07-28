#!/usr/bin/env python3
"""Track Ant's benchmark results over time, the way compliance tracks pass rates.

`bench/bench.py` measures one commit against the other runtimes and writes a
manifest to `.deps/compliance/logs/bench_<timestamp>.json`. That answers "how
fast is Ant today" but not "did this change cost us anything", which is the
question a merge or an optimisation actually needs.

This script adds the missing half:

  * a checked-in baseline (`docs/repo/bench-baseline.json`) - the last run we
    consider good, so any later run can be diffed against it;
  * an append-only history (`docs/repo/bench-history.jsonl`) - one line per
    recorded run, so a slow drift across many small changes is visible even
    when no single change tripped a threshold.

Subcommands
-----------
update <manifest.json>
    Promote a manifest to the baseline, and record it in the history. Refuses
    dirty or commit-less manifests, like the compliance baseline does.

record <manifest.json>
    Append to the history without moving the baseline. This is what you want
    after an ordinary change: it keeps the series dense while the baseline
    stays put at the last known-good point.

diff <manifest.json>
    Compare a manifest against the baseline and report per-benchmark deltas.
    Exits non-zero if any benchmark regressed past the threshold, unless
    --allow-regressions is passed.

history
    Print the recorded series per benchmark.

On noise
--------
Wall-clock benchmarks are noisy, and a threshold on absolute milliseconds will
either cry wolf or miss real losses depending on the machine. Two mitigations:

  * when a manifest carries per-runtime `stddev`, a delta must exceed both the
    relative threshold *and* the combined standard deviation to be called a
    regression;
  * every report also shows the ratio against a reference runtime (node by
    default). Machine-wide noise - a busy CPU, a different laptop - moves Ant
    and node together and barely moves the ratio, so a delta that shows up in
    absolute time but not in the ratio is usually the machine, not the code.

See docs/repo/benchmarking.md for the workflow.
"""
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "docs" / "repo" / "bench-baseline.json"
HISTORY_PATH = REPO_ROOT / "docs" / "repo" / "bench-history.jsonl"

# Ant is the runtime under test; the rest are reference points that also move
# on their own release schedule, so only Ant is gated.
SUBJECT = "ant"
REFERENCE = "node"

DEFAULT_TIME_THRESHOLD = 5.0
DEFAULT_RSS_THRESHOLD = 10.0
DEFAULT_SIZE_THRESHOLD = 25.0

# The fast tier runs 6 iterations instead of 10, so its means are noisier.
# Measured on two back-to-back fast runs of identical code: median drift 2.4%,
# p90 6.1%, worst 11.7% (gc_pressure - collection timing is inherently spiky).
# At 5% that check would flag two or three benchmarks every single run and stop
# meaning anything, so the fast tier gets a threshold matched to its own
# precision. It catches breakage while iterating; the 5% gate lives on the full
# run, which is what actually guards a merge.
FAST_TIME_THRESHOLD = 12.0

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def benchmarks_by_name(manifest: dict) -> dict:
    """Manifests key benchmarks by display name, so that is the join key."""
    out = {}
    for b in manifest.get("benchmarks", []):
        name = b.get("name")
        if name:
            out[name] = b
    return out


def metric(entry: dict, field: str, runtime: str):
    value = (entry.get(field) or {}).get(runtime)
    if value is None or value == 0:
        return None
    return value


def pct(new: float, old: float) -> float:
    if not old:
        return 0.0
    return (new - old) / old * 100.0


def ratio_to_reference(entry: dict, reference: str):
    """Ant's time as a multiple of the reference runtime's.

    Prefers `work` - the mean with that runtime's process startup subtracted -
    because the runtimes' startup floors differ by 5x (Ant ~3.5ms, node ~18ms).
    On a short benchmark the raw means make that gap look like a compute result.
    Manifests written before `work` existed fall back to `means`.
    """
    subject = metric(entry, "work", SUBJECT) or metric(entry, "means", SUBJECT)
    ref = metric(entry, "work", reference) or metric(entry, "means", reference)
    if subject is None or ref is None:
        return None
    return subject / ref


def significant(new_entry: dict, old_entry: dict, runtime: str, delta_pct: float,
                threshold: float) -> bool:
    """A delta counts only if it clears the threshold and the run-to-run spread.

    `stddev` is absent from manifests written before it was recorded; those fall
    back to the threshold alone.
    """
    if abs(delta_pct) < threshold:
        return False
    new_sd = metric(new_entry, "stddev", runtime)
    old_sd = metric(old_entry, "stddev", runtime)
    if new_sd is None or old_sd is None:
        return True
    new_mean = metric(new_entry, "means", runtime)
    old_mean = metric(old_entry, "means", runtime)
    if new_mean is None or old_mean is None:
        return True
    # Combined spread of the two means, in the same units as the difference.
    return abs(new_mean - old_mean) > (new_sd + old_sd)


def revision_of(manifest: dict) -> dict:
    return manifest.get("revision", {}) or {}


def check_reproducible(manifest: dict, allow_dirty: bool) -> str | None:
    rev = revision_of(manifest)
    if not rev.get("commit") or rev.get("commit") == "unknown":
        return "manifest has no known commit"
    if rev.get("dirty") and not allow_dirty:
        return (
            "manifest was produced from a dirty working tree, so the numbers are "
            "not reproducible from a commit alone (pass --allow-dirty to override)"
        )
    return None


def history_row(manifest: dict, reference: str) -> dict:
    rev = revision_of(manifest)
    entries = {}
    for name, b in benchmarks_by_name(manifest).items():
        row = {}
        ms = metric(b, "means", SUBJECT)
        rss = metric(b, "rss", SUBJECT)
        ratio = ratio_to_reference(b, reference)
        if ms is not None:
            row["ms"] = round(ms, 4)
        if rss is not None:
            row["rss"] = round(rss, 3)
        if ratio is not None:
            row["ratio"] = round(ratio, 4)
        if row:
            entries[name] = row
    return {
        "timestamp": manifest.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "commit": rev.get("commit", "unknown"),
        "short": rev.get("short", "unknown"),
        "branch": rev.get("branch", "unknown"),
        "dirty": bool(rev.get("dirty")),
        "subject_version": (manifest.get("runtimes", {}).get(SUBJECT, {}) or {}).get("version"),
        "reference": reference,
        "reference_version": (manifest.get("runtimes", {}).get(reference, {}) or {}).get("version"),
        "benchmarks": entries,
    }


def append_history(row: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def read_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    rows = []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cmd_record(args) -> int:
    manifest = load_json(Path(args.manifest))
    row = history_row(manifest, args.reference)
    append_history(row)
    print(
        f"Recorded {len(row['benchmarks'])} benchmarks at "
        f"{row['short']}{' (dirty)' if row['dirty'] else ''} -> {HISTORY_PATH}"
    )
    return 0


def cmd_update(args) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_json(manifest_path)

    problem = check_reproducible(manifest, args.allow_dirty)
    if problem:
        print(f"error: refusing to baseline - {problem}.", file=sys.stderr)
        return 1

    # A fast manifest holds a subset of the benchmarks and runtimes. Promoting
    # it would shrink the baseline to that subset, and every benchmark it does
    # not cover would then read as "new" on the next full run.
    if manifest.get("tier", "full") != "full":
        print(
            f"error: refusing to baseline - this is a "
            f"'{manifest.get('tier')}' tier run, which covers only part of the "
            f"suite. Seed the baseline from a full run.",
            file=sys.stderr,
        )
        return 1

    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    append_history(history_row(manifest, args.reference))

    rev = revision_of(manifest)
    count = len(manifest.get("benchmarks", []))
    print(f"Updated benchmark baseline: {count} benchmarks at commit {rev.get('short', '?')}.")
    print(f"Baseline written to {BASELINE_PATH}")
    print(f"Recorded in {HISTORY_PATH}")
    return 0


def cmd_diff(args) -> int:
    manifest = load_json(Path(args.manifest))
    if not BASELINE_PATH.exists():
        print(
            f"error: no baseline at {BASELINE_PATH}. Promote a run first:\n"
            f"  python3 scripts/bench_baseline.py update <manifest.json>",
            file=sys.stderr,
        )
        return 1
    baseline = load_json(BASELINE_PATH)

    new = benchmarks_by_name(manifest)
    old = benchmarks_by_name(baseline)

    new_rev = revision_of(manifest)
    old_rev = revision_of(baseline)
    print(f"{BOLD}Benchmark diff{RESET}")
    print(f"  baseline : {old_rev.get('short', '?')}"
          f"{' (dirty)' if old_rev.get('dirty') else ''}"
          f"  {DIM}{baseline.get('timestamp', '')}{RESET}")
    print(f"  current  : {new_rev.get('short', '?')}"
          f"{' (dirty)' if new_rev.get('dirty') else ''}"
          f"  {DIM}{manifest.get('timestamp', '')}{RESET}")

    ref_old = (baseline.get("runtimes", {}).get(args.reference, {}) or {}).get("version")
    ref_new = (manifest.get("runtimes", {}).get(args.reference, {}) or {}).get("version")
    if ref_old and ref_new and ref_old != ref_new:
        print(f"  {YELLOW}note:{RESET} {args.reference} changed {ref_old} -> {ref_new}, "
              f"so the ratio column moved for reasons unrelated to Ant.")

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    shared = [n for n in new if n in old]

    tier = manifest.get("tier", "full")
    if args.threshold is None:
        args.threshold = FAST_TIME_THRESHOLD if tier == "fast" else DEFAULT_TIME_THRESHOLD
    if tier == "fast":
        print(f"  {YELLOW}tier{RESET}     : fast - a subset of the suite at "
              f"{args.threshold:.0f}% (its own noise floor). "
              f"Gate on a full run before merging.")

    if added:
        print(f"\n{CYAN}new benchmarks{RESET} (no baseline yet): {', '.join(added)}")
    if removed:
        # A fast run legitimately skips most of the suite; calling that
        # "missing" would read as something having gone wrong.
        label = "not run in the fast tier" if tier == "fast" else "missing from this run"
        print(f"{CYAN}{label}{RESET}: {', '.join(removed)}")

    if not shared:
        print(f"\n{YELLOW}Nothing comparable between the two runs.{RESET}")
        return 0

    header = f"  {'benchmark':<32} {'time':>18}  {'rss':>16}  {'vs ' + args.reference:>16}"
    print(f"\n{BOLD}{header}{RESET}")

    regressions = []
    improvements = []
    for name in shared:
        n, o = new[name], old[name]
        n_ms, o_ms = metric(n, "means", SUBJECT), metric(o, "means", SUBJECT)
        n_rss, o_rss = metric(n, "rss", SUBJECT), metric(o, "rss", SUBJECT)

        if n_ms is None or o_ms is None:
            print(f"  {name:<32} {DIM}no data{RESET}")
            continue

        d_ms = pct(n_ms, o_ms)
        ms_regressed = d_ms > 0 and significant(n, o, SUBJECT, d_ms, args.threshold)
        ms_improved = d_ms < 0 and significant(n, o, SUBJECT, d_ms, args.threshold)

        d_rss = pct(n_rss, o_rss) if (n_rss is not None and o_rss is not None) else None
        rss_regressed = d_rss is not None and d_rss > args.rss_threshold

        n_ratio, o_ratio = ratio_to_reference(n, args.reference), ratio_to_reference(o, args.reference)
        d_ratio = pct(n_ratio, o_ratio) if (n_ratio and o_ratio) else None

        colour = RED if ms_regressed else (GREEN if ms_improved else RESET)
        time_cell = f"{o_ms:.1f}->{n_ms:.1f}ms {d_ms:+.1f}%"
        rss_cell = f"{d_rss:+.1f}%" if d_rss is not None else "-"
        ratio_cell = f"{n_ratio:.2f}x {d_ratio:+.1f}%" if d_ratio is not None else "-"

        flag = ""
        if ms_regressed:
            flag = " REGRESSED"
        elif rss_regressed:
            flag = " RSS"
        print(f"  {name:<32} {colour}{time_cell:>18}{RESET}  "
              f"{(RED if rss_regressed else RESET)}{rss_cell:>16}{RESET}  {ratio_cell:>16}{flag}")

        if ms_regressed or rss_regressed:
            regressions.append((name, d_ms, d_rss, d_ratio, ms_regressed))
        elif ms_improved:
            improvements.append((name, d_ms))

    # Binary growth is gated alongside speed: a runtime that gets faster by
    # getting much larger is still a regression for an embeddable engine.
    old_size = (baseline.get("runtimes", {}).get(SUBJECT, {}) or {}).get("binary_size") or 0
    new_size = (manifest.get("runtimes", {}).get(SUBJECT, {}) or {}).get("binary_size") or 0
    size_regressed = False
    if old_size and new_size:
        d_size = pct(new_size, old_size)
        size_regressed = d_size > args.size_threshold
        colour = RED if size_regressed else RESET
        print(f"\n  {'binary size':<32} {colour}"
              f"{old_size / 1048576:.2f}->{new_size / 1048576:.2f}MB {d_size:+.1f}%{RESET}"
              f"{' GREW' if size_regressed else ''}")
    elif not new_size:
        print(f"\n  {DIM}binary size not recorded in this run{RESET}")

    if improvements:
        print(f"\n{GREEN}Improved{RESET} ({len(improvements)})")
        for name, d in sorted(improvements, key=lambda x: x[1]):
            print(f"  {name}: {d:+.1f}%")

    if not regressions and not size_regressed:
        print(f"\n{GREEN}No regressions past {args.threshold:.0f}% time / "
              f"{args.rss_threshold:.0f}% RSS / {args.size_threshold:.0f}% size.{RESET}")
        return 0

    if size_regressed and not regressions:
        print(f"\n{RED}Binary grew past {args.size_threshold:.0f}%.{RESET}")
        return 0 if args.allow_regressions else 1

    print(f"\n{RED}Regressions{RESET} ({len(regressions)})")
    for name, d_ms, d_rss, d_ratio, was_time in regressions:
        detail = f"time {d_ms:+.1f}%"
        if d_rss is not None:
            detail += f", rss {d_rss:+.1f}%"
        if d_ratio is not None:
            detail += f", vs {args.reference} {d_ratio:+.1f}%"
            # Only meaningful for a time regression: RSS has no ratio column.
            if was_time and abs(d_ratio) < args.threshold:
                detail += f" {DIM}(ratio held - suspect machine noise){RESET}"
        print(f"  {name}: {detail}")

    if args.allow_regressions:
        print(f"\n{YELLOW}--allow-regressions set; not failing.{RESET}")
        return 0
    return 1


def cmd_history(args) -> int:
    rows = read_history()
    if not rows:
        print(f"No history yet at {HISTORY_PATH}.")
        print("Record a run with: python3 scripts/bench_baseline.py record <manifest.json>")
        return 0

    names = sorted({n for r in rows for n in r.get("benchmarks", {})})
    if args.benchmark:
        wanted = args.benchmark.lower()
        names = [n for n in names if wanted in n.lower()]
        if not names:
            print(f"No benchmark matching {args.benchmark!r}.", file=sys.stderr)
            return 1

    # Insertion order is not chronological once runs come from several machines
    # or get recorded out of order, and a series only reads correctly in time
    # order.
    rows.sort(key=lambda r: r.get("timestamp") or "")
    rows = rows[-args.limit:] if args.limit else rows
    for name in names:
        print(f"\n{BOLD}{name}{RESET}")
        print(f"  {'commit':<10} {'when':<18} {'ms':>10} {'delta':>9} {'ratio':>8}")
        previous = None
        for r in rows:
            entry = r.get("benchmarks", {}).get(name)
            if not entry or "ms" not in entry:
                continue
            ms = entry["ms"]
            delta = f"{pct(ms, previous):+.1f}%" if previous else "-"
            colour = RESET
            if previous:
                d = pct(ms, previous)
                colour = RED if d > args.threshold else (GREEN if d < -args.threshold else RESET)
            ratio = f"{entry['ratio']:.2f}x" if "ratio" in entry else "-"
            when = (r.get("timestamp") or "")[:16].replace("T", " ")
            mark = "*" if r.get("dirty") else " "
            print(f"  {r.get('short', '?'):<9}{mark} {when:<18} "
                  f"{colour}{ms:>10.1f} {delta:>9}{RESET} {ratio:>8}")
            previous = ms
    print(f"\n{DIM}* = measured on a dirty tree{RESET}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", default=REFERENCE,
                    help=f"Runtime to show Ant's ratio against (default: {REFERENCE})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("update", help="Promote a manifest to the baseline and record it")
    p.add_argument("manifest")
    p.add_argument("--allow-dirty", action="store_true",
                   help="Baseline a manifest measured on a dirty tree")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("record", help="Append a manifest to the history, leaving the baseline alone")
    p.add_argument("manifest")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("diff", help="Compare a manifest against the baseline")
    p.add_argument("manifest")
    # Default resolved in cmd_diff: it depends on the manifest's tier, which is
    # not known until the file is read.
    p.add_argument("--threshold", type=float, default=None,
                   help=f"Time regression threshold in %% (default: "
                        f"{DEFAULT_TIME_THRESHOLD} full, {FAST_TIME_THRESHOLD} fast)")
    p.add_argument("--rss-threshold", type=float, default=DEFAULT_RSS_THRESHOLD,
                   help=f"Peak RSS regression threshold in %% (default: {DEFAULT_RSS_THRESHOLD})")
    p.add_argument("--size-threshold", type=float, default=DEFAULT_SIZE_THRESHOLD,
                   help=f"Binary growth threshold in %% (default: {DEFAULT_SIZE_THRESHOLD})")
    p.add_argument("--allow-regressions", action="store_true",
                   help="Report regressions but exit 0")
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("history", help="Print the recorded series per benchmark")
    p.add_argument("--benchmark", help="Only show benchmarks matching this substring")
    p.add_argument("--limit", type=int, default=20, help="Show only the last N runs (default: 20)")
    p.add_argument("--threshold", type=float, default=DEFAULT_TIME_THRESHOLD,
                   help="Colour a step past this %% (default: 5)")
    p.set_defaults(fn=cmd_history)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
