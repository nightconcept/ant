---
name: compliance-failures
description: Analyze ant compliance test run failures. Use when investigating which compliance tests failed, triaging tier 2 (Node.js compat) or tier 3 (Test262/WPT) failures, deciding what to work on next, or parsing the large tier logs in .deps/compliance/logs. Turns multi-MB [FAIL] logs into ranked, grouped, actionable failure lists.
---

# Compliance failure analysis

Ant's compliance suite (`just compliance`, `scripts/run_compliance*.py`) writes one
log per tier to `.deps/compliance/logs/tier{1,2,3}_<timestamp>_<shortsha>[-dirty].log`,
plus a sibling JSON manifest at the same path with `.json` instead of `.log`. Tier 3's
log is huge (20+ MB, ~50k tests) — never read it directly. Use the parser instead.

- **Tier 1** — WinterTC / edge baseline (tiny, expected 100%).
- **Tier 2** — Node.js compat suite (`tests/*.cjs|*.js`, hundreds of tests).
- **Tier 3** — Full conformance: Test262 / WPT / frameworks (~50k tests).

## Start with the manifest, not the log

Every run's `.json` manifest (schema documented in `docs/repo/compliance.md`) is a
few KB: totals, per-category totals, and each category's sorted list of failing
test *names* (no output). Read it directly for a cheap, structured first pass:

```
cat .deps/compliance/logs/tier3_<latest>.json | python3 -m json.tool
```

To check whether a change regressed anything, diff a run's manifest (full or a
`--filter` slice) against the checked-in baseline:

```
python3 scripts/compliance_baseline.py diff .deps/compliance/logs/tier3_<run>.json
```

This compares per category (only categories the run covered, so a filtered slice
can't look like a suite-wide regression), lists newly-failing / newly-passing
tests, and exits non-zero on any regression (`--allow-regressions` to report
without failing). After a verified full run, promote it to the baseline with
`compliance_baseline.py update <manifest.json>` — it refuses filtered or
dirty-tree manifests, since a partial or unreproducible run must never become
the baseline. The tier 3 baseline is not yet seeded (a full run takes too long
to do casually); `diff` prints a notice and exits 0 when a tier has no baseline.

Reach for `parse_failures.py` below (and the raw `.log`) when you need the
*captured output* of a failure — the manifest only has names.

## Log format

Only failures are written out (passes are counted in the trailing `Summary` block).
Every failure is one block, identical across tiers:

```
[FAIL] <test name> (<time>ms)
--- output ---
<captured stdout/stderr; the thrown error is near the end>
--------------
```

The thrown error appears as a line like `TypeError: ...`, `Error: <assertion msg>`,
`ReferenceError: 'x' is not defined`, or a bare `TIMEOUT after N.0s`. Test262
assertion failures rethrow as a generic `Error:` carrying the harness message
(e.g. `Error: Expected SameValue(...) to be true`).

## Workflow

Run from the repo root. The parser auto-selects the latest log per tier.

1. **Overview** — counts + error-type breakdown for every tier:
   ```
   python3 .claude/skills/compliance-failures/parse_failures.py
   ```
2. **Where the failures cluster** (best starting point for tier 3):
   ```
   python3 .claude/skills/compliance-failures/parse_failures.py --tier 3 --group category
   python3 .claude/skills/compliance-failures/parse_failures.py --tier 3 --group message
   ```
   `--group message` normalizes variable bits (quotes, numbers) so near-identical
   failures collapse into one ranked bucket — the fastest path to "one fix clears N
   tests".
3. **Drill into a suspect area** — every failing test + its one-line error:
   ```
   python3 .claude/skills/compliance-failures/parse_failures.py --tier 3 --filter Temporal
   python3 .claude/skills/compliance-failures/parse_failures.py --tier 2 --list
   ```
4. **Feed follow-up tooling** — full structured data:
   ```
   python3 .claude/skills/compliance-failures/parse_failures.py --tier 3 --json
   ```
   Each failure: `{test, time, error_type, message, category}`.

Other flags: `--log <path>` parses a specific (e.g. older) log file.

## Staleness

Every log records the commit and tree state it was produced at (`Commit:` /
`Branch:` / `Tree:` in the header, and `<shortsha>[-dirty]` in the filename).
Tier 3 runs take long enough that a log routinely outlives the code it
describes. The parser checks whether the log's commit is still an ancestor of
`HEAD` and prints a prominent warning at the top of every report if:

- the commit is not an ancestor of `HEAD` (already superseded — the failure
  may already be fixed),
- the tree was dirty when the log was produced (not reproducible from the
  commit alone), or
- no commit can be determined at all (old logs that predate this tracking).

Pass `--require-current` to turn that warning into a non-zero exit, e.g. to
gate a "these failures are still live" claim in CI or a PR description.
`--json` output carries the same information per tier under a `"staleness"`
key instead of printing the banner.

## Triage guidance

- A large `--group message` bucket usually means one root cause. E.g. thousands of
  `ReferenceError: '$262' is not defined` means the Test262 host global isn't
  provided by the harness — a runner/harness fix, not an engine bug.
- Separate **harness/runner** failures (missing `$262`, `import/export in CommonJS`,
  timeouts) from genuine **engine conformance** gaps (`Expected SameValue`, bad
  property descriptors). Fix harness issues first; they inflate the failure count.
- Prefer categories with many failures and a single dominant message — highest
  leverage per fix. Tier 1 should stay at 100%; a tier 1 regression is top priority.

## Maintenance

The block format is shared by all tiers and stable. If the runner's output format
changes, update `FAIL_RE` / `ERR_RE` / `DASHES_RE` in `parse_failures.py` and
re-check that the `Unknown` error-type count stays near zero (it means extraction
missed the thrown error).
