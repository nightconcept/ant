#!/usr/bin/env python3
"""Manage the checked-in compliance baseline (docs/repo/compliance-baseline.json).

The baseline holds the most recent full-run manifest per tier, so that a
filtered slice run later (e.g. `run_compliance_tier3.py --filter foo`) can be
compared against "the last known-good full run" without re-running the whole
tier.

Subcommands
-----------
update <manifest.json>
    Store a manifest as the new baseline for its tier. Refuses manifests that
    are partial (`filter` is set) or unreproducible (dirty tree, no commit) -
    a baseline must describe one specific, reproducible, full run.

diff <manifest.json>
    Compare a manifest (full run or filtered slice) against the stored
    baseline for its tier, per category. Exits non-zero if any covered
    category regressed (new failures relative to baseline), unless
    --allow-regressions is passed.

See docs/repo/compliance.md for the full workflow.
"""
import sys
import json
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "docs" / "repo" / "compliance-baseline.json"

MAX_LISTED = 25


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_baseline(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "tiers": {}}
    return load_json(path)


def save_baseline(baseline: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, sort_keys=True)
        f.write("\n")


def _load_json_checked(path: Path, label: str) -> dict | None:
    try:
        value = load_json(path)
    except FileNotFoundError:
        print(f"error: {label} not found: {path}", file=sys.stderr)
        return None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {label} {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(value, dict):
        print(f"error: {label} {path} must contain a JSON object", file=sys.stderr)
        return None
    return value


def _manifest_errors(
    manifest: dict,
    *,
    label: str,
    require_full: bool = False,
    require_clean: bool = False,
    expected_commit: str | None = None,
    expected_branch: str | None = None,
) -> list[str]:
    errors = []
    if manifest.get("schema_version") != 1:
        errors.append(f"{label} has unsupported schema_version {manifest.get('schema_version')!r}")
    if not isinstance(manifest.get("tier"), int):
        errors.append(f"{label} has no integer 'tier' field")
    if not isinstance(manifest.get("categories"), dict):
        errors.append(f"{label} has no object-valued 'categories' field")
    if not isinstance(manifest.get("totals"), dict):
        errors.append(f"{label} has no object-valued 'totals' field")
    if require_full and manifest.get("filter") is not None:
        errors.append(f"{label} is partial (filter={manifest.get('filter')!r}); a full run is required")

    revision = manifest.get("revision")
    if not isinstance(revision, dict):
        errors.append(f"{label} has no object-valued 'revision' field")
        revision = {}
    commit = revision.get("commit")
    if not commit or commit == "unknown":
        errors.append(f"{label} has no known revision commit")
    if require_clean and revision.get("dirty"):
        errors.append(f"{label} was produced from a dirty working tree")
    if expected_commit and commit != expected_commit:
        errors.append(f"{label} commit {commit!r} does not match expected {expected_commit!r}")
    if expected_branch and revision.get("branch") != expected_branch:
        errors.append(
            f"{label} branch {revision.get('branch')!r} does not match expected {expected_branch!r}"
        )

    categories = manifest.get("categories")
    if isinstance(categories, dict):
        for name, category in categories.items():
            if not isinstance(category, dict) or not isinstance(category.get("failing"), list):
                errors.append(f"{label} category {name!r} has no failing-test list")
    return errors


def _report_errors(errors: list[str]) -> bool:
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return bool(errors)


def cmd_update(args) -> int:
    manifest_path = Path(args.manifest)
    manifest = _load_json_checked(manifest_path, "manifest")
    if manifest is None:
        return 1

    tier = manifest.get("tier")
    if tier is None:
        print(f"error: manifest {manifest_path} has no 'tier' field", file=sys.stderr)
        return 1

    if manifest.get("filter") is not None:
        print(
            f"error: refusing to baseline a filtered run (filter={manifest['filter']!r}). "
            "A baseline must come from a full, unfiltered run.",
            file=sys.stderr,
        )
        return 1

    revision = manifest.get("revision", {})
    if revision.get("dirty"):
        print(
            "error: refusing to baseline a manifest produced from a dirty working "
            "tree - the result is not reproducible from a commit alone.",
            file=sys.stderr,
        )
        return 1
    if not revision.get("commit") or revision.get("commit") == "unknown":
        print(
            "error: refusing to baseline a manifest with no known commit.",
            file=sys.stderr,
        )
        return 1

    baseline_path = Path(args.baseline)
    baseline = load_baseline(baseline_path)
    baseline.setdefault("schema_version", 1)
    baseline.setdefault("tiers", {})
    baseline["tiers"][str(tier)] = manifest
    save_baseline(baseline, baseline_path)

    totals = manifest.get("totals", {})
    print(
        f"Updated baseline for tier {tier} "
        f"({totals.get('passed', '?')}/{totals.get('total', '?')} = "
        f"{totals.get('pass_rate', '?')}%) at commit {revision.get('short', '?')}."
    )
    print(f"Baseline written to {baseline_path}")
    return 0


def _in_scope(test_name: str, filter_value: str | None) -> bool:
    if not filter_value:
        return True
    return filter_value.lower() in test_name.lower()


def cmd_diff(args) -> int:
    manifest_path = Path(args.manifest)
    manifest = _load_json_checked(manifest_path, "manifest")
    if manifest is None:
        return 1

    manifest_errors = _manifest_errors(
        manifest,
        label="manifest",
        require_full=args.require_full,
        require_clean=bool(args.expect_commit or args.expect_branch),
        expected_commit=args.expect_commit,
        expected_branch=args.expect_branch,
    )
    if _report_errors(manifest_errors):
        return 1

    tier = manifest.get("tier")
    if tier is None:
        print(f"error: manifest {manifest_path} has no 'tier' field", file=sys.stderr)
        return 1

    baseline_path = Path(args.baseline)
    try:
        baseline = load_baseline(baseline_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read baseline {baseline_path}: {exc}", file=sys.stderr)
        return 1
    base_tier = baseline.get("tiers", {}).get(str(tier))

    if base_tier is None:
        if args.require_baseline:
            print(f"error: no baseline recorded for tier {tier} in {baseline_path}", file=sys.stderr)
            return 1
        print(f"No baseline recorded for tier {tier} - nothing to diff against.")
        print(f"(Seed one with: python3 scripts/compliance_baseline.py update <full-run-manifest.json>)")
        return 0

    if args.require_baseline:
        baseline_errors = _manifest_errors(
            base_tier,
            label=f"tier {tier} baseline",
            require_full=True,
            require_clean=True,
        )
        if base_tier.get("tier") != tier:
            baseline_errors.append(
                f"tier {tier} baseline identifies itself as tier {base_tier.get('tier')!r}"
            )
        if _report_errors(baseline_errors):
            return 1

    filter_value = manifest.get("filter")
    manifest_categories = manifest.get("categories", {})
    base_categories = base_tier.get("categories", {})

    worse = []
    better = []
    unchanged = []
    new_categories = []

    total_newly_failing = []
    total_newly_passing = []

    for cat_name, cur_cat in sorted(manifest_categories.items()):
        base_cat = base_categories.get(cat_name)
        cur_failing = set(cur_cat.get("failing", []))

        if base_cat is None:
            new_categories.append((cat_name, cur_cat))
            total_newly_failing.extend(sorted(cur_failing))
            continue

        base_failing = set(base_cat.get("failing", []))
        in_scope_base_failing = {t for t in base_failing if _in_scope(t, filter_value)}

        newly_failing = sorted(cur_failing - base_failing)
        newly_passing = sorted(in_scope_base_failing - cur_failing)

        total_newly_failing.extend(newly_failing)
        total_newly_passing.extend(newly_passing)

        if newly_failing:
            worse.append((cat_name, cur_cat, base_cat, newly_failing, newly_passing))
        elif newly_passing:
            better.append((cat_name, cur_cat, base_cat, newly_failing, newly_passing))
        else:
            unchanged.append(cat_name)

    rev = manifest.get("revision", {})
    base_rev = base_tier.get("revision", {})

    print("=" * 72)
    print(f"Compliance diff: tier {tier} - {manifest.get('suite', '')}")
    print("=" * 72)
    print(f"Manifest : {manifest_path}")
    print(f"  commit : {rev.get('short', '?')}{' (dirty)' if rev.get('dirty') else ''}")
    print(f"  filter : {filter_value if filter_value else '(none - full run)'}")
    print(f"Baseline : {baseline_path}")
    print(f"  commit : {base_rev.get('short', '?')}{' (dirty)' if base_rev.get('dirty') else ''}")
    print(f"  categories covered by this run: {len(manifest_categories)}")
    print()

    if new_categories:
        print(f"New categories (no baseline data, {len(new_categories)}):")
        for cat_name, cur_cat in new_categories:
            print(f"  {cat_name}: {cur_cat['passed']}/{cur_cat['total']} passed, "
                  f"{cur_cat['failed']} failing (untracked before)")
        print()

    if worse:
        print(f"Regressed categories ({len(worse)}):")
        for cat_name, cur_cat, base_cat, newly_failing, newly_passing in worse:
            print(f"  - {cat_name}")
            print(f"      baseline: {base_cat['passed']}/{base_cat['total']} passed")
            print(f"      now     : {cur_cat['passed']}/{cur_cat['total']} passed")
            print(f"      newly failing: {len(newly_failing)}  newly passing: {len(newly_passing)}")
        print()

    if better:
        print(f"Improved categories ({len(better)}):")
        for cat_name, cur_cat, base_cat, newly_failing, newly_passing in better:
            print(f"  + {cat_name}")
            print(f"      baseline: {base_cat['passed']}/{base_cat['total']} passed")
            print(f"      now     : {cur_cat['passed']}/{cur_cat['total']} passed")
            print(f"      newly passing: {len(newly_passing)}")
        print()

    if unchanged:
        print(f"Unchanged categories: {len(unchanged)}")
        print()

    print(f"Net: {len(total_newly_failing)} newly failing, {len(total_newly_passing)} newly passing "
          f"(across {len(manifest_categories)} covered categories)")
    print()

    if total_newly_failing:
        print(f"Newly-failing tests ({len(total_newly_failing)}):")
        for name in total_newly_failing[:MAX_LISTED]:
            print(f"  - {name}")
        if len(total_newly_failing) > MAX_LISTED:
            print(f"  ... +{len(total_newly_failing) - MAX_LISTED} more")
        print()

    if total_newly_passing:
        print(f"Newly-passing tests ({len(total_newly_passing)}):")
        for name in total_newly_passing[:MAX_LISTED]:
            print(f"  + {name}")
        if len(total_newly_passing) > MAX_LISTED:
            print(f"  ... +{len(total_newly_passing) - MAX_LISTED} more")
        print()

    print("=" * 72)

    regressed = bool(worse) or bool(new_categories and any(c["failed"] for _, c in new_categories))
    if regressed:
        if args.allow_regressions:
            print("Regressions found, but --allow-regressions was passed: exiting 0.")
            return 0
        print("RESULT: REGRESSION")
        return 1

    print("RESULT: no regressions")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Store a full-run manifest as the tier's baseline")
    p_update.add_argument("manifest", help="Path to a manifest .json produced by a compliance run")
    p_update.add_argument("--baseline", default=str(BASELINE_PATH),
                          help="Baseline JSON path (default: checked-in repository baseline)")
    p_update.set_defaults(func=cmd_update)

    p_diff = sub.add_parser("diff", help="Compare a manifest against the stored baseline")
    p_diff.add_argument("manifest", help="Path to a manifest .json produced by a compliance run")
    p_diff.add_argument("--baseline", default=str(BASELINE_PATH),
                        help="Baseline JSON path (default: checked-in repository baseline)")
    p_diff.add_argument("--allow-regressions", action="store_true",
                         help="Report regressions without failing the exit code (for informational runs)")
    p_diff.add_argument("--require-baseline", action="store_true",
                        help="Fail if the tier baseline is absent, partial, dirty, or malformed")
    p_diff.add_argument("--require-full", action="store_true",
                        help="Fail unless the manifest describes a full, unfiltered run")
    p_diff.add_argument("--expect-commit",
                        help="Fail unless the manifest records this exact commit")
    p_diff.add_argument("--expect-branch",
                        help="Fail unless the manifest records this exact branch")
    p_diff.set_defaults(func=cmd_diff)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
