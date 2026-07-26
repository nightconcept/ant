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

## Measuring A Change Without A Full Run

A full tier 3 run is expensive. To attribute a delta:

- Run the affected slice only: `python3 scripts/run_compliance_tier3.py --filter
  <path-substring> --log-fail`.
- Diff the failing-test *names* between the old and new logs. Comparing totals
  against a whole-suite log's category counts is unreliable — the categories do
  not line up with `--filter` substrings, and a stale baseline will invent both
  regressions and wins that are not there.
- Treat single-test movements with suspicion until reproduced. Runs before the
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
