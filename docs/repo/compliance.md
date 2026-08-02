# Compliance Work Guide

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

This guide defines the external conformance suites and the Ant regression suite.
Read [testing.md](testing.md) for normal change validation.

## Suites

| Suite ID | Display name | Corpus | Bar |
| --- | --- | --- | --- |
| `wintertc` | WinterTC | TC55 API-surface contract and pinned WPT subset | No new failures. The final conformance bar is 100%. |
| `regression` | Ant Regression | `tests/test_*` and `examples/spec/*.js` | No failures. |
| `test262` | Test262 | Complete pinned TC39 Test262 corpus | No new failures. Improvements are desirable. |

The WinterTC suite measures applicable Web Platform behavior. The suite does
not prove full conformance while required tests fail. WinterTC also requires
ECMA-262 conformance.

## Commands

Use these commands for full runs:

```text
just compliance-wintertc
just compliance-regression
just compliance-test262
```

Use the generic command for filters and limits:

```text
just compliance -- --suite wintertc --filter url --limit 20
just compliance -- --suite regression --filter streams
just compliance -- --suite test262 --filter built-ins/Array --limit 100
```

Use these commands to compare exact failing-test names:

```text
just compliance-diff-wintertc
just compliance-diff-regression
just compliance-diff-test262
```

Use `compliance-update-<suite>` only after a clean full run. The command refuses
a dirty tree or a filtered manifest.

## Corpus Pins

`.github/versions.json` pins WPT and Test262 to full commit SHAs. Do not update a
pin without a clean full run and a reviewed baseline change.

The WinterTC selection is in `tests/wintertc/wpt-manifest.json`. Each exclusion
has one of these reasons:

- `window-only`
- `server-required`
- `unsupported-harness`
- `outside-wintertc`

Do not exclude a test because Ant fails required behavior. Keep that test as a
visible failure.

The [WinterTC coverage matrix](wintertc-coverage.md) maps every TC55 interface,
method, and property to the local contract and selected WPT evidence.

## Manifests and Logs

Each logged run writes two files:

```text
.deps/compliance/logs/<suite>_<timestamp>_<revision>.log
.deps/compliance/logs/<suite>_<timestamp>_<revision>.json
```

The stable link is `.deps/compliance/logs/<suite>-latest.json`.

Schema 2 manifests have this identity:

```json
{
  "schema_version": 2,
  "suite_id": "wintertc",
  "suite": "WinterTC"
}
```

The manifest also records the revision, filter, totals, categories, and exact
failing-test names. Read the manifest before you read a large log.

## Baselines

`docs/repo/compliance-baseline.json` stores the trusted full-run manifest for
each named suite. The top-level `suites` object uses stable suite IDs.

The diff command compares failing-test sets by category. A better total cannot
hide a newly failing test. A filtered run compares only its selected categories.

CI uses these options for exact revision checks:

```text
--require-baseline
--require-full
--expect-commit <sha>
--expect-branch <branch>
```

The baseline tool has a temporary read-only bridge for the old schema. Old
Regression and Test262 baselines can support a migration pull request. The old
numeric WinterTC label has no mapping because it did not run WPT.

## WinterTC Harness Rules

- Run only `.any.js` files that the checked-in manifest selects.
- Run each source file as one named result.
- Resolve each `// META: script=` dependency from the pinned WPT checkout.
- Write each prepared file beside its source file.
- Use a unique scratch name for each test.
- Require the WPT testharness completion callback.
- Treat process exit zero without completion as a harness failure.
- Remove scratch files after each test and after each run.

Network-backed fetch tests require the WPT server. These tests remain visible as
`server-required` work until the runner supplies the required server environment.

## Test262 Harness Rules

- Run tests from the pinned checkout.
- Skip fixture files.
- Write each prepared file beside its source file.
- Use a unique scratch name for each test.
- Supply the supported `$262` host methods.
- Keep unsupported host capabilities absent so failures remain accurate.

## Definition of Done

A compliance change is complete when all applicable conditions are true:

1. Ant Regression has no failures.
2. WinterTC and Test262 have no newly failing tests.
3. Each corrected external failure has an Ant Regression test.
4. Harness changes and runtime changes are separate commits when practical.
5. The change is small enough for upstream review.

Full WinterTC conformance needs more evidence:

1. The API-surface contract passes.
2. All applicable selected WPT tests pass.
3. All exclusions describe browser-only or harness-only cases.
4. The coverage matrix includes every TC55-required interface and property.
5. Required ECMA-262 behavior passes.

## Failure Analysis

Use the `compliance-failures` skill for large logs. It supports these suite IDs:

```text
wintertc
regression
test262
```

Check the revision before you act on a failure. A dirty or superseded log does
not describe the current binary reliably.
