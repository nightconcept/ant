# Compliance Testing

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

Ant uses two named external/internal suites. Numeric compliance tiers are
retired.

| Suite ID | Display name | Corpus | Gate |
| --- | --- | --- | --- |
| `regression` | Ant Regression | `tests/test_*` and `examples/spec/*.js` | Must pass completely. |
| `test262` | Test262 | Complete pinned TC39 Test262 corpus | Must not gain failures or lose tests. |

Ant Regression is the required workflow gate. Test262 is a non-regression gate:
changes may improve its result, but may never introduce a newly failing test or
shrink the selected corpus.

## Commands

```text
just compliance-regression
just compliance-test262
just compliance-diff-regression
just compliance-diff-test262
```

Use the generic command for filters and limits:

```text
just compliance -- --suite regression --filter streams
just compliance -- --suite test262 --filter built-ins/Array --limit 100
```

Use `compliance-update-<suite>` only after a clean full run. The command refuses
a dirty tree or a filtered manifest.

## Corpus Pin

`.github/versions.json` pins Test262 to a full commit SHA. Do not update the pin
without a clean full run and a reviewed baseline change.

## Manifests and Logs

Each logged run writes two files:

```text
.deps/compliance/logs/<suite>_<timestamp>_<revision>.log
.deps/compliance/logs/<suite>_<timestamp>_<revision>.json
```

The stable link is `.deps/compliance/logs/<suite>-latest.json`.

Schema 2 manifests identify their suite explicitly:

```json
{
  "schema_version": 2,
  "suite_id": "regression",
  "suite": "Ant Regression"
}
```

## Baselines

`docs/repo/compliance-baseline.json` stores the trusted full-run manifest for
each named suite. The baseline diff compares exact failing-test sets by
category. A new failure fails the gate even if the aggregate pass rate is
unchanged. A missing test or smaller category also fails a full-run comparison.

CI uses these options for exact revision checks:

```text
--require-baseline
--require-full
--expect-commit <sha>
--expect-branch <branch>
```

## Test262 Rules

- Run tests from the pinned checkout.
- Skip fixture files.
- Write prepared files beside their source.
- Use a unique scratch name for each test.
- Supply the supported `$262` host methods.
- Keep unsupported host capabilities absent so failures remain accurate.
- Compare every full run against the trusted baseline.

## Definition of Done

A compliance change is complete when:

1. Ant Regression has no failures.
2. Test262 has no newly failing tests.
3. A full Test262 run has not lost any tests from the pinned corpus.
4. Each corrected external failure has an Ant Regression test when practical.
5. Harness changes and runtime changes are separate commits when practical.

## Failure Analysis

Use `.agents/skills/compliance-failures/parse_failures.py` for large logs. It
supports the `regression` and `test262` suite IDs.
