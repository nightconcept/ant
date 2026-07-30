# Post-Audit Correctness and Compliance Gates

Status: active
Last reviewed: 2026-07-30
Owner: Core Engineering

## Goal

Resolve the actionable findings from the 2026-07-30 adversarial review of the
last 20 commits on `dev`:

- make numeric array writes preserve ordinary JavaScript property semantics
  without giving back the performance win of the dense-element fast path;
- make `Object.defineProperties` and `Object.create` accept enumerable symbol
  descriptor keys;
- make Tier 2 and Tier 3 CI compare exact failing-test sets rather than totals;
- run the full Tier 3 suite weekly against both `main` and `dev`, with each
  branch reported and gated independently.

The outcome is a `dev` branch whose optimized element stores remain correct and
whose compliance automation enforces the policy already documented in
`docs/repo/compliance.md`.

## Explicit Non-Goal

Do not rewrite, split, revert, or otherwise churn commit `a3496f8c`
(`fix: bring tier 2 compliance to 100%`). Its mixed runtime, harness, and test
changes are already landed and well tested. The lesson applies to new work:
keep each runtime root cause separate, and keep harness/CI changes separate
from engine changes.

## Scope

### 1. Dense array write correctness

`js_arr_try_fast_set` currently writes directly to dense storage when the index
is in bounds. That bypasses:

- a non-writable own numeric property;
- an own accessor descriptor;
- an inherited numeric setter or inherited non-writable data property;
- strict-mode assignment failure behavior.

Retain a fast path for the proven ordinary dense case, but make it decline when
the generic `[[Set]]` algorithm has observable work to do. Determine the
cheapest reliable guard from the existing array shape, descriptor, prototype,
and invalidation machinery before choosing an implementation. Do not add a
prototype-chain walk to every ordinary dense write if an existing shape/epoch
guard can establish the same invariant.

Add focused regression coverage for:

- sloppy and strict assignment to an own non-writable index;
- own indexed accessors;
- an inherited indexed setter on a dense hole;
- an inherited non-writable indexed data property;
- the unchanged ordinary in-bounds dense store and append fallback paths.

### 2. Symbol descriptor keys

`object_define_properties` asks `js_own_property_keys` to omit symbols to avoid
wrongly enumerable built-in `@@toStringTag` properties. Fix the underlying
built-in symbol descriptor attributes instead of retaining the semantic
exception, then include enumerable symbol keys in the ordinary
`ObjectDefineProperties` path.

Audit both ordinary objects and proxies for the required ordering and
`[[Get]]` behavior. Cover at least:

- `Object.defineProperties(target, { [symbol]: descriptor })`;
- `Object.create(proto, { [symbol]: descriptor })`;
- non-enumerable symbol descriptor entries being ignored;
- accessor-backed descriptor entries being read once;
- mixed string/symbol ordering and proxy behavior;
- representative built-ins such as `JSON`, `Math`, iterators, and module
  namespace-like objects retaining non-enumerable `@@toStringTag`.

### 3. Exact compliance-set gates

Remove the inline pass-count comparisons from the `main`, `upstream`, and
weekly Tier 3 workflows. Route CI through
`scripts/compliance_baseline.py diff`, which already compares failing test
names per covered category and exits non-zero on a new failure.

CI must fail closed when:

- the expected baseline tier is absent;
- no manifest was produced;
- the manifest is partial when a full run was requested;
- the manifest revision or branch does not match the checked-out source;
- any previously passing covered test becomes a failure, even when the total
  pass count stays level or improves.

If the existing command cannot express those CI-only invariants cleanly, add a
small explicit option such as `--require-baseline` rather than recreating
baseline parsing in workflow YAML. Unit-test the comparison with synthetic
manifests, including a pass/fail swap whose totals are identical.

### 4. Weekly Tier 3 on `main` and `dev`

GitHub scheduled workflows are loaded from the repository's default branch,
which is `dev`; an unqualified checkout therefore does not test `main`. Keep
one scheduled workflow on the default branch, but give it an explicit branch
matrix containing `main` and `dev` and check out the matrix ref.

Each branch job must:

- build the exact checked-out branch;
- use that branch's checked-in compliance baseline;
- verify that the produced manifest identifies the expected commit and branch;
- run a full Tier 3 suite and exact failing-set comparison;
- upload artifacts named with the branch, for example
  `tier3-compliance-main` and `tier3-compliance-dev`;
- have an independently visible job conclusion so one branch cannot hide the
  other's failure.

Keep `workflow_dispatch`. Manual execution should test both branches by
default; a branch selector may be added only if the scheduled path still
unconditionally covers both. Use branch-aware concurrency keys and artifact
names so the jobs cannot cancel or overwrite each other.

Update `docs/repo/testing.md`, `docs/repo/compliance.md`, workflow comments, and
any dashboard links to describe the actual two-branch schedule and exact-set
gate.

## Constraints

- Tier 1 remains 100%.
- Tier 2 remains 100% on the final state.
- Tier 3 gains are welcome, but there may be no newly failing test relative to
  the appropriate checked-in baseline.
- Compare failing-test names, never only totals, rates, or rounded percentages.
- Preserve the common dense-array write performance. Run the focused
  microbenchmark first, then `just bench-fast-diff`; investigate any threshold
  regression rather than widening thresholds.
- Do not add suite-specific behavior to the runtime.
- Do not edit vendored or generated build output.
- Keep the work as separate reviewable commits: array semantics, symbol
  descriptors, baseline tooling, workflow wiring, and documentation/baseline
  refresh. Do not combine engine and harness changes.
- A baseline refresh is a final, clean-tree snapshot commit. It must not conceal
  a newly failing test.

## Task List

1. Reproduce and record the array descriptor/prototype failures on current
   `dev`; identify the cheapest invariant that safely admits a direct dense
   store.
2. Implement the guarded array store as its own commit and add focused runtime
   tests.
3. Run the relevant Test262 array/property slices and the fast benchmark before
   proceeding.
4. Inventory enumerable built-in symbol properties that motivated the symbol
   exclusion.
5. Correct those descriptors, include symbols in ObjectDefineProperties, and
   add ordinary/proxy regression tests as a separate commit.
6. Run focused `Object.defineProperties`, `Object.create`, symbol, and built-in
   descriptor Test262 slices.
7. Extend and unit-test `compliance_baseline.py` so CI can require a valid full
   baseline and matching revision without inline YAML parsing.
8. Replace Tier 2 and Tier 3 pass-count snippets in all affected workflows with
   the shared exact-set command.
9. Convert the weekly Tier 3 workflow to explicit `main` and `dev` jobs or a
   branch matrix, with branch-qualified checkout, concurrency, and artifacts.
10. Update repository testing/compliance documentation.
11. Run `just preflight`, a clean build, the full spec suite, Tier 1, Tier 2,
    relevant Tier 3 slices, and `just bench-fast-diff`.
12. Run or dispatch the weekly workflow and confirm both branch jobs produce
    artifacts and enforce a synthetic or controlled set regression correctly.
13. Run a final full Tier 3 comparison, review the exact newly-failing and
    newly-passing sets, and refresh the baseline only if justified.
14. Move this plan to `completed/` with final commands, manifests, CI run URLs,
    performance results, and remaining risks.

## Commit Shape

The intended sequence is:

1. `fix(array): preserve descriptors on numeric fast stores`
2. `fix(object): include symbol keys in property descriptor maps`
3. `test(compliance): enforce exact failing-set baselines`
4. `ci: run weekly tier 3 on main and dev`
5. `docs: describe branch-specific compliance gates`
6. optional clean baseline refresh, only after reviewing the full set diff

Commit subjects may change, but these boundaries should not. In particular,
the compliance tool change must be testable without depending on a workflow
run, and neither runtime fix belongs in the CI commits.

## Validation Status

In progress on `dev`, starting from `00874ed1`.

- `c48cfc4d` guards numeric dense stores when own descriptors or prototype
  semantics are observable. The focused runtime regression test passes, and
  the dense-array microbenchmark remains linear. `just bench-fast-diff`
  reported Array Operations at +5.0% (within its threshold); the command's
  only threshold failure was the unrelated HTTP Server Round-Trip benchmark
  at +6.1%.
- `ca820e42` includes enumerable symbol descriptor keys for ordinary and proxy
  property maps and corrects built-in `@@toStringTag` attributes. The new
  ordinary/proxy, accessor-once, ordering, built-in, and module namespace
  regressions pass.
- `3fc74fe6` adds fail-closed full-run, baseline, commit, and branch checks to
  `compliance_baseline.py`. Its seven synthetic-manifest unit tests pass,
  including an equal-total pass/fail swap.
- `aa542117` routes Tier 2 and Tier 3 workflows through the shared exact-set
  comparator and gives weekly Tier 3 explicit, independent `main` and `dev`
  matrix jobs with branch-qualified caches and artifacts.

Focused Test262 slices were also run. The relevant symbol-key and built-in tag
cases passed; remaining failures were pre-existing harness or feature gaps.
The broad clean-tree suites, branch baseline snapshots, and live two-branch
workflow dispatch remain to be completed before this plan can move to
`completed/`.

## Decision Log

- 2026-07-30: Explicitly excluded historical surgery on `a3496f8c`. Apply its
  process lesson prospectively.
- 2026-07-30: Require weekly Tier 3 coverage for both `main` and `dev`, not one
  branch standing in for the other.
- 2026-07-30: Chose the shared baseline tool as the single comparison surface;
  workflow-local Python must be removed rather than corrected in parallel.
- 2026-07-30: Put runtime correctness before CI wiring so the first trustworthy
  exact-set weekly run measures the corrected engine.
- 2026-07-30: Performance preservation is part of acceptance for the array
  repair, not a deferred optimization.
- 2026-07-30: CI uses explicit `--require-baseline`, `--require-full`,
  `--expect-commit`, and `--expect-branch` checks. Interactive filtered diffs
  retain their permissive missing-baseline behavior.
- 2026-07-30: Weekly Tier 3 uses a branch matrix rather than duplicated jobs;
  the matrix still yields separate conclusions, concurrency groups, caches,
  and artifacts for `main` and `dev`.

## Completion Criteria

This plan is complete only when:

- all focused array and symbol regressions pass;
- Tier 1 and Tier 2 are at 100%;
- a full Tier 3 exact-set diff reports zero newly failing tests;
- the dense write path has no material benchmark regression;
- CI has no pass-count-only compliance gates;
- scheduled and manually dispatched Tier 3 runs show separate green `main` and
  `dev` jobs with distinct artifacts;
- documentation matches the implemented branch and comparison behavior.

## Follow-Ups

Record newly discovered correctness or tooling issues here while executing the
plan. Do not expand this plan to rewrite historical commits or absorb unrelated
conformance improvements.
