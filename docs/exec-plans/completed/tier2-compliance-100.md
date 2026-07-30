# Tier 2 Compliance to 100%

Status: completed
Last reviewed: 2026-07-29
Owner: Core Engineering

## Goal

Move the local tier 2 suite from 452/465 to 100% without weakening runtime
semantics, while preserving tier 1 at 100% and avoiding tier 3 regressions.

## Scope

- Repair stale or invalid test contracts currently counted as tier 2 failures.
- Fix the remaining Node compatibility defects in `node:assert`, CLI dispatch,
  custom inspection, package lifecycle execution, and the REPL.
- Keep harness/test corrections separate in intent from runtime corrections.
- Harden the compliance runner where a stress workload or stale binary can
  distort the metric.

## Constraints

- Do not make CommonJS accept static ESM syntax; the affected files are modules
  and must use `.mjs`.
- Do not change JavaScript semantics to satisfy invalid legacy expectations.
- Tier 1 remains 100%.
- Compare exact tier 2 and tier 3 failure lists, not only percentages.

## Task List

1. Correct the eight stale test/suite contracts identified by the
   `tier2_20260729_082444_d151edad` run.
2. Correct nested exception capture in `node:assert`.
3. Prefer an explicit existing script file over a same-named package script.
4. Correct `AbortSignal` inspection and make the test clean up timers on error.
5. Correct lifecycle `node-gyp` discovery.
6. Correct static import handling in the interactive REPL.
7. Run focused tests, `just preflight`, tier 1, and full tier 2. Run targeted
   tier 3 slices for any shared engine behavior.

## Decision Log

- 2026-07-29: Treat test-contract cleanup as a harness change with no claimed
  tier 3 delta.
- 2026-07-29: Keep the `node:assert` fix scoped to consuming nested-call
  exceptions; Test262's JavaScript assertion harness already passes its native
  throw coverage.
- 2026-07-29: Require executable provenance to agree with the revision stamped
  into compliance output before promoting a baseline.
- 2026-07-29: Adversarial review rejected the initial green result because it
  hid direct-eval semantics, removed the GC stress case from automation, and
  mishandled synchronous exceptions in async assertion helpers. The final
  implementation retains all valid coverage and adds a focused assertion test.
- 2026-07-29: A full failure-list diff, not the rounded percentage, is the Tier
  3 gate. The final run has 30 newly passing tests and zero newly failing tests.

## Validation Status

- Baseline tier 2: 452/465 (97.2%), 13 failures.
- Tier 3 reference: 33743/53431 (63.2%), 19688 failures.
- Final tier 2: 466/466 (100%), 0 failures.
  Manifest: `.deps/compliance/logs/tier2_20260729_093256_d151edad-dirty.json`.
- Final tier 1: 1/1 (100%); full spec suite 3672/3672 across 98 files.
  Manifest: `.deps/compliance/logs/tier1_20260729_093250_d151edad-dirty.json`.
- Final tier 3: 33773/53431 (63.2%), 19658 failures. Exact comparison against
  the reference has 30 newly passing tests and zero newly failing tests.
  Manifest: `.deps/compliance/logs/tier3_20260729_093111_d151edad-dirty.json`.
- `just preflight`: passed.
- The manifests are intentionally marked dirty and cannot be promoted as
  reproducible baselines until the changes are committed and rerun cleanly.

## Follow-ups

- Replace the broad `tests/test_*` tier 2 discovery rule with durable suite
  classification if per-test metadata alone is not sufficient.
