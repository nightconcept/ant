#!/usr/bin/env python3
"""Pull theMackabu/ant into this fork, and tell our regressions from theirs.

The mechanical part of an upstream sync is `git merge`. The parts that are easy
to get wrong, and that this script exists to make routine, are:

  * knowing which of our commits a merge is about to collide with, before
    starting it;
  * comparing compliance before and after against the *same* Test262 checkout -
    a fresh clone picks up new tests and silently turns corpus growth into
    what looks like a regression;
  * deciding whether a regression the merge introduced is ours (a bad conflict
    resolution) or upstream's (a bug they shipped), which needs upstream built
    on its own and compared by failing-test *set*, not pass rate.

Subcommands
-----------
status
    Fetch upstream and report what is incoming: their commits, and the files
    both sides have touched since the merge base, annotated with the commits of
    ours that touched them. That annotation is the conflict-risk list - a file
    only we changed merges cleanly, a file we both rewrote needs a decision.

worktree <path> --rev <rev>
    Build a throwaway worktree at <rev>, seeded so it can build and run
    compliance without re-downloading anything: vendor packagecache and the
    extracted git-based subprojects are linked from this checkout, and the
    Test262 corpus is *pinned* to the one this checkout already has.

attribute <base.json> <merged.json> <upstream.json>
    Three-way compare of compliance manifests. Reports what the merge fixed,
    what it broke, and splits the breakage into "upstream ships this bug" and
    "our merge resolution caused this" by checking each new failure against
    upstream built standalone. Exits non-zero if any failure is ours.

See docs/repo/upstream-sync.md for the full playbook.
"""
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_REMOTE = "upstream"
UPSTREAM_BRANCH = "master"

# Subprojects meson checks out with git rather than unpacking from the
# packagecache; copying them saves a clone per throwaway worktree.
GIT_SUBPROJECTS = ("boringssl", "mimalloc", "crprintf", "ada", "mir", "skim")

BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def git(*args: str, cwd: Path = REPO_ROOT, check: bool = True) -> str:
    r = subprocess.run(
        ["git", *args], cwd=cwd, check=check,
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def upstream_ref() -> str:
    return f"{UPSTREAM_REMOTE}/{UPSTREAM_BRANCH}"


def cmd_status(args) -> int:
    ref = upstream_ref()
    print(f"{DIM}fetching {UPSTREAM_REMOTE}...{RESET}")
    git("fetch", UPSTREAM_REMOTE, "--prune")

    ours = args.branch
    base = git("merge-base", ours, ref)
    incoming = git("log", "--oneline", "--no-decorate", f"{ours}..{ref}").splitlines()
    outgoing = git("log", "--oneline", "--no-decorate", f"{ref}..{ours}").splitlines()

    print(f"\n{BOLD}merge base{RESET}  {git('log', '--oneline', '--no-decorate', '-1', base)}")
    print(f"{BOLD}ours{RESET}        {ours} ({len(outgoing)} commits ahead)")
    print(f"{BOLD}upstream{RESET}    {ref} ({len(incoming)} commits ahead)")

    if not incoming:
        print(f"\n{GREEN}up to date - nothing to merge.{RESET}")
        return 0

    print(f"\n{BOLD}Incoming commits{RESET}")
    for line in incoming:
        print(f"  {line}")

    their_files = set(git("diff", "--name-only", f"{base}..{ref}").splitlines())
    our_files = set(git("diff", "--name-only", f"{base}..{ours}").splitlines())
    both = sorted(their_files & our_files)

    print(f"\n{BOLD}Files changed by both sides{RESET} ({len(both)} of "
          f"{len(their_files)} incoming)")
    if not both:
        print(f"  {GREEN}none - expect a clean merge.{RESET}")
        return 0

    print(f"  {DIM}each is annotated with the commits of ours that touched it;{RESET}")
    print(f"  {DIM}a file only one of our commits owns is usually a revert-or-keep{RESET}")
    print(f"  {DIM}decision, not a hunk-by-hunk merge.{RESET}\n")
    for f in both:
        commits = git("log", "--oneline", "--no-decorate", f"{base}..{ours}", "--", f).splitlines()
        churn = git("diff", "--numstat", f"{base}..{ref}", "--", f).split("\t")
        added, removed = (churn[0], churn[1]) if len(churn) >= 2 else ("?", "?")
        print(f"  {CYAN}{f}{RESET} {DIM}(+{added}/-{removed} upstream){RESET}")
        for c in commits:
            print(f"      {c}")
    return 0


def cmd_worktree(args) -> int:
    dest = Path(args.path).resolve()
    if dest.exists():
        print(f"{RED}error: {dest} already exists.{RESET}", file=sys.stderr)
        return 1

    git("fetch", UPSTREAM_REMOTE, "--prune")
    add = ["worktree", "add", str(dest), args.rev]
    if args.branch:
        add = ["worktree", "add", str(dest), "-b", args.branch, args.rev]
    elif not git("rev-parse", "--verify", "--quiet", f"refs/heads/{args.rev}", check=False):
        add.insert(2, "--detach")
    git(*add)
    print(f"{GREEN}worktree{RESET} {dest} at {args.rev}")

    cache = REPO_ROOT / "vendor" / "packagecache"
    if cache.is_dir():
        link = dest / "vendor" / "packagecache"
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.exists():
            link.symlink_to(cache)
        print(f"{GREEN}vendor{RESET} packagecache linked")
    for name in GIT_SUBPROJECTS:
        src = REPO_ROOT / "vendor" / name
        if src.is_dir() and not (dest / "vendor" / name).exists():
            shutil.copytree(src, dest / "vendor" / name, symlinks=True)

    # Pinning the corpus is the whole point: a fresh clone of tc39/test262 adds
    # tests, and those show up in a before/after diff as failures the merge
    # "introduced". Both sides must read the same checkout.
    corpus = REPO_ROOT / ".deps" / "compliance" / "test262"
    if corpus.is_dir():
        link = dest / ".deps" / "compliance" / "test262"
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.exists():
            link.symlink_to(corpus)
        rev = git("log", "--oneline", "-1", cwd=corpus, check=False)
        print(f"{GREEN}test262{RESET} pinned to {rev or 'local checkout'}")
    else:
        print(f"{YELLOW}warning:{RESET} no Test262 checkout at {corpus} to pin - "
              f"run a tier 3 here first, then re-run so both sides share it.",
              file=sys.stderr)

    print(f"\nnext: meson setup {dest}/build {dest} && meson compile -C {dest}/build")
    return 0


def failing_set(path: Path) -> tuple[set[str], dict, dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    failing: set[str] = set()
    totals_by_cat: dict[str, int] = {}
    for cat, v in d.get("categories", {}).items():
        failing.update(v.get("failing", []))
        totals_by_cat[cat] = v.get("total", 0)
    return failing, d.get("totals", {}), totals_by_cat


def area(test: str, depth: int = 4) -> str:
    return "/".join(test.split("/")[:depth])


def cmd_attribute(args) -> int:
    base, base_totals, base_cats = failing_set(args.base)
    merged, merged_totals, merged_cats = failing_set(args.merged)
    up, _, _ = failing_set(args.upstream)

    print(f"{BOLD}Compliance across the merge{RESET}")
    print(f"  pre-merge : {base_totals.get('passed')}/{base_totals.get('total')} "
          f"({base_totals.get('pass_rate')}%)")
    print(f"  merged    : {merged_totals.get('passed')}/{merged_totals.get('total')} "
          f"({merged_totals.get('pass_rate')}%)")

    drift = {k for k in set(base_cats) | set(merged_cats)
             if base_cats.get(k) != merged_cats.get(k)}
    if drift:
        print(f"\n{RED}corpus drift:{RESET} these categories changed size between the "
              f"two runs, so the comparison below is not apples-to-apples:")
        for k in sorted(drift):
            print(f"    {k}: {base_cats.get(k)} -> {merged_cats.get(k)}")
        print(f"  Re-run both sides against one pinned Test262 checkout "
              f"(`sync_upstream.py worktree` does this).")

    fixed = base - merged
    broke = merged - base
    print(f"\n{GREEN}newly passing{RESET} {len(fixed)}   "
          f"{RED}newly failing{RESET} {len(broke)}")

    if fixed:
        print(f"\n{BOLD}What the merge fixed, by area{RESET}")
        counts: dict[str, int] = {}
        for t in fixed:
            counts[area(t)] = counts.get(area(t), 0) + 1
        for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:args.limit]:
            print(f"  {GREEN}{v:6}{RESET}  {k}")

    if not broke:
        print(f"\n{GREEN}No new failures - the merge is a clean win.{RESET}")
        return 0

    # A new failure that upstream also has, standalone, is a bug they shipped:
    # we inherit it by merging. One upstream does *not* have is ours, and means
    # a conflict resolution dropped or broke something.
    theirs = sorted(t for t in broke if t in up)
    ours = sorted(t for t in broke if t not in up)

    print(f"\n{BOLD}Inherited from upstream{RESET} ({len(theirs)}) "
          f"{DIM}- fails on {upstream_ref()} standalone too{RESET}")
    counts = {}
    for t in theirs:
        counts[area(t)] = counts.get(area(t), 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:args.limit]:
        print(f"  {YELLOW}{v:6}{RESET}  {k}")

    print(f"\n{BOLD}Caused by our merge resolution{RESET} ({len(ours)})")
    if not ours:
        print(f"  {GREEN}none - every new failure is upstream's.{RESET}")
        return 0
    for t in ours[:args.limit]:
        print(f"  {RED}{t}{RESET}")
    if len(ours) > args.limit:
        print(f"  {DIM}... and {len(ours) - args.limit} more{RESET}")
    print(f"\n{RED}Fix these before landing the merge.{RESET}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="Fetch upstream and report incoming work and conflict risk")
    p.add_argument("--branch", default="dev", help="Our branch to compare against (default: dev)")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("worktree", help="Create a build-ready worktree with a pinned Test262 corpus")
    p.add_argument("path", help="Where to create the worktree")
    p.add_argument("--rev", required=True, help="Revision to check out (e.g. upstream/master)")
    p.add_argument("--branch", help="Create this branch at --rev instead of detaching")
    p.set_defaults(fn=cmd_worktree)

    p = sub.add_parser("attribute", help="Three-way manifest diff: ours vs upstream's regressions")
    p.add_argument("base", help="Manifest from the pre-merge commit")
    p.add_argument("merged", help="Manifest from the merged branch")
    p.add_argument("upstream", help=f"Manifest from {upstream_ref()} built standalone")
    p.add_argument("--limit", type=int, default=25, help="Max rows to list per section")
    p.set_defaults(fn=cmd_attribute)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
