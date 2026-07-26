# Compliance Work Guide

Status: active
Last reviewed: 2026-07-26
Owner: theMackabu

This guide covers work whose goal is moving Ant's conformance numbers: Test262,
WPT, and Node.js compatibility. For ordinary validation scope, read
[testing.md](testing.md) instead.

## The Tiers

| Tier | Suite | Bar |
| ---- | ----- | --- |
| 1 | WinterTC / edge baseline | **Must be 100%.** A tier 1 failure is a release blocker and outranks any other compliance work. |
| 2 | Node.js compatibility | Pass rate must not drop. Increases are desirable. |
| 3 | Test262 / WPT / frameworks | Pass rate must not drop. Increases are the point of the work. |

## Definition Of Done

A compliance change is done when all of the following hold.

1. **Tier 1 is at 100%.** No exceptions, no "pre-existing" excuses.
2. **No tier 2 or tier 3 percentage regression** measured on the final state of
   the change. A net gain that hides a regression in one area is not done —
   diff the failing-test *lists*, not just the totals (see below).
3. **The change is small and upstreamable.** Prefer one root cause per commit,
   expressed the way the surrounding subsystem already expresses things. If a
   fix needs a new subsystem, a feature flag, or a suite-specific special case,
   it is the wrong shape — split it or write an exec plan first.
4. **Harness fixes are separated from engine fixes.** A runner bug that inflates
   the failure count is worth fixing, but land it as its own change so the
   engine delta stays legible.
5. **Anything the engine now does correctly has a test in `tests/`.** Test262 is
   the discovery mechanism, not the regression net — it is not run per-commit.

Explicitly *not* required: fixing every failure in an area. Landing a verified
partial improvement beats sitting on a large branch.

## Reading Logs

Every log records the commit it was produced at, in both the filename and the
header:

```
.deps/compliance/logs/tier3_<timestamp>_<short-sha>[-dirty].log
```

```
=== Tier 3 - Full Conformance (Test262 / WPT / Frameworks) ===
Started  : 2026-07-26 08:41:12
Commit   : 0ad56fb9...
Branch   : dev
Tree     : clean
```

**Check the commit before trusting a log.** A tier 3 run takes long enough that
logs routinely outlive the code they describe; failures already fixed on `HEAD`
look identical to live ones. If the log's commit is not an ancestor of your
work — or the tree was `dirty` — re-verify individual tests against the current
binary before acting on them.

Tier 3 logs are 20+ MB. Never read one directly; use the
`compliance-failures` skill, which ranks and groups the failures.

## The Per-Run Manifest

Every run that writes a log (`--log` or `--log-fail`) also writes a sibling
JSON manifest at the same path with `.json` instead of `.log` — a few KB
versus the log's tens of MB, so it is what agents should read first. It is
built in `SummaryTracker` (`scripts/compliance_common.py`) and has this shape:

```json
{
  "schema_version": 1,
  "suite": "Tier 3 - Full Conformance (Test262 / WPT / Frameworks)",
  "tier": 3,
  "started": "2026-07-26T08:53:35",
  "finished": "2026-07-26T09:14:02",
  "revision": { "commit": "...", "short": "...", "dirty": false, "branch": "dev", "subject": "..." },
  "filter": "language/module-code",
  "totals": { "total": 599, "passed": 474, "failed": 125, "pass_rate": 79.1 },
  "categories": {
    "Test262: language/module-code": {
      "total": 599, "passed": 474, "failed": 125,
      "failing": ["Test262: language/module-code/foo.js", "..."]
    }
  }
}
```

`filter` is the `--filter` value used for the run, or `null` for a full run.
`failing` lists only failing test *names*, sorted — no output — which is what
makes per-category diffing across runs cheap and precise.

## The Checked-In Baseline

`docs/repo/compliance-baseline.json` holds the most recent full-run manifest
per tier, keyed by tier number: `{"schema_version": 1, "tiers": {"1": {...},
"2": {...}}}`. **The tier 3 entry is not seeded** — a full tier 3 run is too
expensive to run casually, so `diff` (below) treats a missing tier baseline as
"nothing to compare", prints that, and exits 0. Seed it by running a full tier
3 pass and then `compliance_baseline.py update` on the resulting manifest once
one has been run and reviewed.

`scripts/compliance_baseline.py` has two subcommands:

- `update <manifest.json>` — store that manifest as the new baseline for its
  tier. Refuses (non-zero exit) a manifest with a non-null `filter` or a dirty
  revision — a baseline must describe one specific, reproducible, full run.
- `diff <manifest.json>` — compare a manifest (full run or a filtered slice)
  against the stored baseline for its tier, per category. Only categories the
  run actually covered are compared, so a `--filter` slice cannot look like a
  suite-wide regression. It lists newly-failing and newly-passing test names
  (capped, with exact counts) and exits non-zero if any covered category
  regressed. Pass `--allow-regressions` to report without failing the exit
  code.

## Measuring A Change Without A Full Run

A full tier 3 run is expensive. To attribute a delta:

```
python3 scripts/run_compliance_tier3.py --filter <path-substring> --log-fail
python3 scripts/compliance_baseline.py diff .deps/compliance/logs/tier3_<new-run>.json
```

`diff` does the failing-test-name comparison for you, scoped to the categories
the slice actually touched. Once a change is verified clean (or an improvement
is confirmed) on a full run, promote it with `compliance_baseline.py update` so
later slices compare against it.

Treat single-test movements with suspicion until reproduced. Runs before the
per-test scratch-file fix could clobber each other's sources and record false
passes.

## Harness Invariants

These are properties of the runner, not the engine. Preserve them.

- **Tests run in place.** The harness-prepended copy is written next to the
  original test as `ant_t262_tmp_<n>_<name>.js`, because Test262 reaches sibling
  files through relative specifiers (`./x_FIXTURE.js`, `import('./y.js')`) that
  cannot resolve from a shared scratch directory. Stale copies are swept at
  start and end of a run.
- **Scratch names are unique per test**, not per worker slot. A `idx % workers`
  name is unsafe under a thread pool.
- **`$262` is shimmed** from primitives ant actually exposes. Capabilities ant
  lacks (`agent`, `createRealm`, `IsHTMLDDA`) are deliberately left absent so
  those tests fail with an accurate error.

## Known Large Gaps

Areas where the failure count is dominated by an unimplemented feature rather
than by fixable bugs. Do not mine these for "easy wins".

- `built-ins/Temporal` and `intl402/Temporal` — Temporal is not implemented.
  ~6,600 failures, about 12% of the suite.
- `intl402/*` constructors — most Intl constructors are not constructible.
- Builtin `length` values. `js_mkfun` defaults arity to 0, so most builtins
  report `length === 0`. Correcting it means an arity per registration site
  across thousands of call sites; worth ~500 tests but not a small change.

## Open Trade-offs

- Because tests run in place, ant sees the Test262 checkout's `package.json` and
  runs them in CommonJS scope instead of as Scripts. Removing that manifest
  recovers a handful of `noStrict` tests that assert `this === global` but
  breaks ~60 `dynamic-import` tests, so it is left in place. Closing this
  properly needs an engine-side way to force Script semantics for a file.
