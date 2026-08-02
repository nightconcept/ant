# Trunk PR Gates and Iterator Pilot

Status: ready for review
Last reviewed: 2026-08-01
Owner: Core Engineering

## Goal

Replace the `dev`/`main` delivery split with a protected, release-quality
`main` branch. All normal work starts on a short-lived branch and enters
`main` through a pull request. A single required `PR Gate` classifies the
change and runs the complete applicable validation. The first feature to use
the new route is the synchronous Iterator Helpers correctness and allocation
work identified from the compliance dashboard.

This plan also fixes the failed `v12.3.0` release publication. The publish job
does not check out the repository, so `gh release create` must receive the
repository explicitly instead of trying to discover it from `.git`.

## Current State

- `main` and `dev` have push-only CI workflows.
- `main` is the intended release branch and the release workflow accepts only
  revisions reachable from `main`.
- Tier 1 and Tier 2 are at 100%. Tier 3 is intentionally baseline-gated rather
  than literally at 100%.
- GitHub-hosted benchmark timings are not stable enough to be a merge gate.
  Performance is measured locally against the checked-in baseline and recorded
  nightly on consistent hardware.
- The failed `v12.3.0` run created neither a GitHub release nor a remote tag.
- `origin/main` and `origin/dev` have rewritten/parallel history. Do not merge
  or delete `dev` until their patch and tree differences have been audited.

## Target Branch Model

```text
feat/*  fix/*  perf/*  compliance/*  docs/*  ci/*
                         |
                         v
                    PR to main
                         |
                  required PR Gate
                         |
                 optional merge queue
                         |
                         v
                       main
```

- `main` is always release-quality.
- Direct pushes are disabled for normal work, including docs, chores, and CI
  changes. Emergency bypass is reserved for repository recovery.
- Feature branches start from current `main` and are deleted after merge.
- Releases continue to rebuild and validate an immutable SHA reachable from
  `main`.

## Meaning of a Green Gate

“All tests pass” means all required checks for the change succeed:

- Tier 1 is 100%.
- Tier 2 is 100% and has no exact failing-set regression.
- Tier 3 has no newly failing tests relative to the trusted `main` baseline.
  Tier 3 is not required to have a 100% aggregate pass rate.
- Every required platform build, repository check, and workflow check is
  successful.
- A performance-sensitive change has reviewed local benchmark evidence. This
  remains a review requirement until Ant has a stable self-hosted benchmark
  runner.

## Workflow Layout

### `.github/workflows/pr-ci.yml`

Triggers:

- `pull_request` targeting `main`;
- `merge_group` with `checks_requested` when the merge queue is enabled;
- `workflow_dispatch` for troubleshooting.

Do not add workflow-level `paths` filters. The workflow must always create the
required `PR Gate` check. A classifier job decides which internal jobs are
required.

Jobs:

1. `classify` computes the merge base and emits:
   `docs_only`, `workflow_changed`, `build_changed`, `runtime_changed`, and
   `performance_sensitive`.
2. `repo-knowledge` always runs knowledge and structure checks.
3. `workflow-lint` runs for `.github/workflows/**`, `.github/actions/**`, and
   CI tooling changes.
4. `build-and-test` runs the existing six-platform matrix for non-doc changes.
   The Linux glibc x64 entry continues to run Tier 1, which includes the full
   local spec suite.
5. `compliance-tier2` runs for code, test, build, or harness changes.
6. `compliance-tier3` runs a full exact-set comparison for runtime-sensitive
   changes and for every merge-group candidate. A later optimization may use
   filtered PR slices only after there is evidence they cannot hide shared
   semantic regressions.
7. `pr-gate` uses `if: always()` and inspects the classifier outputs plus every
   job conclusion. It fails on a failed, cancelled, or unexpectedly skipped
   required job. This is the only status check configured as required.

The workflow tests the pull request merge commit, not only the feature head.
For a merge-group event, inability to classify the diff falls back to the full
gate.

### Reusable workflow components

Keep the existing `.github/workflows/build-platform.yml`. Extract the repeated
Linux compliance build/setup into a reusable workflow so PR, post-merge,
scheduled, and release callers do not maintain separate toolchain recipes.
Inputs must include the immutable source revision, logical branch name, tier,
and trusted baseline source.

### `.github/workflows/main-ci.yml`

Retain a push trigger for `main` as post-merge verification of the exact landed
SHA and for artifact production. It is an alarm, not the merge boundary.

- Docs-only changes: repository checks.
- Workflow changes: repository checks and workflow lint; exercise affected
  reusable workflows where possible.
- Code/build changes: full platform matrix, Tier 1, Tier 2, and repository
  checks.
- Tier 3 remains on the PR/merge-group route for runtime changes and on its
  schedule as defense in depth.

### `.github/workflows/tier3-weekly.yml`

After `dev` is retired, reduce the matrix to `main`. Keep full exact-set
comparison, branch-qualified artifacts, manual dispatch, and non-cancelling
concurrency.

### `.github/workflows/release.yml`

Keep release validation and publication separate. It rebuilds the selected
`main` SHA on all release platforms and checks Tier 2 before publication.

## Trusted Compliance Baselines

A pull request must not be able to hide a regression by changing the baseline
it uses for its own check.

- Run the candidate from the pull request merge SHA.
- Read the comparison baseline from the pull request base SHA into a temporary
  path.
- Extend `scripts/compliance_baseline.py diff` with an explicit baseline path
  or baseline-ref option. Do not reproduce JSON comparison logic in YAML.
- Treat baseline refreshes as dedicated, reviewed changes generated from a
  clean full run.
- For `merge_group`, use the queue base or the last trusted `main` revision.

## Benchmark Policy

Benchmarks are evidence for performance-sensitive PRs, not a GitHub-hosted
required status check.

- During implementation: `just bench-fast-diff`.
- Before merging a performance-sensitive runtime change:
  `just bench-diff`.
- Nightly on consistent hardware: `just bench-nightly` records history without
  changing the baseline.
- Baseline promotion: `just bench-update-baseline` only from a reviewed clean
  full run.
- Dashboard: `just dashboard` displays checked-in results and is not a live
  benchmark execution.

The PR description for a performance-sensitive change records the manifest
path, fast/full gate results, material timing and RSS movement, and any accepted
trade-off. Until a stable self-hosted runner exists, review enforces this
requirement. GitHub-hosted absolute timings must not block merging.

## Phases

### Phase 1: Repair release publication

Objective: make the existing release job publish without requiring a checkout.

Branch: `fix/release-explicit-repo`, based on current `main`.

Files:

- `.github/workflows/release.yml`

Implementation:

- Add `--repo "$GITHUB_REPOSITORY"` to `gh release create`. Keep
  `GH_TOKEN`, the immutable `--target`, generated notes, title, and prerelease
  handling unchanged.
- Do not add a checkout solely to satisfy repository discovery.
- Keep the publish job's `contents: write` permission scoped to that job.

Verification:

```bash
nix shell nixpkgs#actionlint -c actionlint -ignore SC2129 .github/workflows/release.yml
git diff --check
gh release view v12.3.0 --repo nightconcept/ant
git ls-remote --tags origin refs/tags/v12.3.0
```

The two read-only release/tag checks must show no existing partial publication
before redispatch. After the PR lands, dispatch `Release` on `main` with
version `12.3.0`, blank revision, and the intended prerelease value. Verify the
tag, release, assets, checksums, and provenance identify the resolved `main`
SHA.

Rollback: revert only the release workflow commit.

Status: [x] complete

### Phase 2: Bootstrap the PR gate without a test PR

Objective: land the new workflow machinery under the current push-only policy,
without opening a dummy PR or enabling branch protection yet.

Branch: `ci/trunk-pr-gates`, based on `main` after Phase 1.

Files:

- `.github/workflows/pr-ci.yml` — new PR and merge-group entrypoint.
- `.github/workflows/main-ci.yml` — post-merge exact-SHA health workflow.
- `.github/workflows/build-platform.yml` — only reusable inputs/outputs needed
  by both callers.
- `.github/workflows/compliance-gate.yml` — reusable compliance build and
  exact-set job.
- `scripts/compliance_baseline.py` — accept a trusted baseline path/ref.
- Synthetic comparator tests — cover a PR that edits its own baseline.

Implementation requirements:

- Keep action permissions read-only unless a job demonstrably needs more.
- Pin third-party actions to immutable commits, following the existing repo
  convention.
- Give required jobs names unique to this workflow.
- Ensure `pr-gate` exists and concludes on docs-only, code, failure, cancelled,
  and merge-group paths.
- Do not remove the old push checks yet.
- Land this bootstrap through the repository's current process. This is the
  final planned change to `main` before the feature PR proves the new process.
- Do not create a synthetic success/failure PR. The Iterator feature in Phase
  4 is the first PR that exercises `PR Gate`.

Verification:

```bash
nix shell nixpkgs#actionlint -c actionlint -ignore SC2086 -ignore SC2129 .github/workflows/*.yml
python3 scripts/compliance_baseline.py --help
just preflight
git diff --check
```

After this phase lands, confirm the workflow is present on `main`, but do not
activate a required status check that GitHub has not observed yet.

Rollback: leave branch settings unchanged and revert the workflow/tooling PR.

Status: [x] complete

### Phase 3: Audit `dev` and prepare the trunk transition

Objective: establish that `dev` contains no unique work that would be lost,
while leaving branch protection and branch deletion until the Iterator PR has
proved the new gate.

Repository audit before deletion:

```bash
git fetch origin
git rev-list --left-right --count origin/main...origin/dev
git diff --stat origin/main..origin/dev
git log --cherry-pick --left-right --oneline origin/main...origin/dev
```

- Classify every non-patch-equivalent `dev` commit and every tree difference.
- Replay any genuinely missing change through its own PR to `main`; do not
  merge rewritten duplicate history blindly.
- Prepare the final archive tag target for `dev`; create/push the tag in Phase
  5 immediately before deletion.
- Retarget or close open PRs that target `dev`.

Verification:

```bash
git diff --check
git status --short --branch
```

Record the audit result in this plan before the feature PR opens. Do not change
GitHub protection or delete `dev` in this phase.

Rollback: none required; this phase is an audit and preparation step.

Status: [x] complete

### Phase 4: Exercise the system with Iterator Helpers

Objective: use a completed real correctness/performance change as the first PR
to `main`, then turn its observed green `PR Gate` into an enforced rule before
merging it.

Branch: `feat/iterator-helper-records`, based on `main` after Phases 2 and 3.

Files:

- `src/modules/iterator.c`
- `include/modules/symbol.h` only if the shared direct-iterator API belongs
  there after the local design is tested.
- focused tests under `tests/`
- a benchmark fixture only if the existing benchmark suite cannot attribute
  Iterator Helper work without changing unrelated workload definitions.

Implementation commits:

1. `perf(iterator): use interned iterator result keys`
   - Replace the two duplicate result constructors in `iterator.c` with the
     shared interned result path.
   - Delay result allocation until a helper actually returns a result.
   - Preserve observable `done` then `value` property order.
2. `fix(iterator): cache direct iterator records in helpers`
   - Cache `next` once as required by GetIteratorDirect semantics.
   - Accept plain iterator objects that have callable `next` without requiring
     `@@iterator`.
   - Propagate abrupt `next`, `done`, and `value` access correctly.
   - Reject non-object iterator results.
   - Forward and suppress `return` at the correct close/exhaustion points.

Focused tests cover `Iterator.from`, `map`, `filter`, `take`, `drop`, `every`,
`some`, `find`, `forEach`, `reduce`, and `toArray` for cached getters, plain
iterators, malformed results, throwing accessors, and iterator closing.

Local verification before opening the PR:

```bash
meson compile -C build
./build/ant tests/test_iterator_helpers.cjs
python3 scripts/run_compliance_tier3.py --filter built-ins/Iterator --log-fail
python3 scripts/compliance_baseline.py diff .deps/compliance/logs/tier3-latest.json
just bench-fast-diff
just bench-diff
just preflight
```

Implement and complete all local validation before opening the PR. The PR
records both benchmark manifest paths and the exact newly-passing and
newly-failing Iterator test sets. No newly failing Tier 3 test is acceptable.

This Iterator PR is the first live test of the process:

1. Open the completed feature branch against `main`.
2. Confirm the workflow creates the uniquely named `PR Gate` and that all
   classified jobs run against the merge candidate.
3. After GitHub has observed a successful `PR Gate`, activate the `main`
   ruleset requiring pull requests and that status.
4. If merge queue is desired, first confirm this PR produces the required
   `merge_group` check; otherwise require current-with-base for the pilot.
5. Merge the Iterator feature through the newly protected PR route.

Do not add an artificial failing commit to this feature merely to test CI. A
real failure encountered during implementation must be fixed normally before
merge.

Performance acceptance:

- no benchmark crosses the existing time, RSS, or binary-size gates;
- the focused helper workload shows fewer result-key allocations;
- a claimed speed or RSS improvement is supported by repeatable measurements;
- if performance is flat, keep only changes justified by correctness and
  maintainability.

Rollback: revert the atomic Iterator runtime commit; the PR infrastructure
remains in place. The implementation combined the planned result-path and
direct-record commits because they edit the same constructor call sites.

Status: [~] implementation and local validation complete; pilot PR pending

### Phase 5: Retire `dev` and confirm post-merge behavior

Objective: finish the single-trunk migration after its first successful feature
PR and prove the resulting branch remains healthy.

GitHub ruleset for `main`:

- require a pull request;
- require the unique `PR Gate` status;
- require current-with-base or the verified merge queue;
- require conversation resolution;
- block force pushes and deletion;
- apply to administrators where practical;
- keep emergency bypass narrowly assigned and documented.

Create and push `archive/dev-20260801` at the audited final `dev` tip. Then:

- change the repository default branch to `main`;
- retarget or close remaining PRs targeting `dev`;
- delete `dev` only after the archive tag is visible remotely;
- remove `.github/workflows/dev-ci.yml`;
- reduce the weekly Tier 3 matrix to `main`;
- update `AGENTS.md`, `docs/repo/testing.md`, `docs/repo/compliance.md`,
  `docs/repo/upstream-sync.md`, and active plans that prescribe `dev`.

- Confirm `main-ci.yml` validates the exact landed Iterator commit.
- Confirm the next scheduled/manual Tier 3 run compares `main` against its
  trusted baseline and uploads the manifest/log.
- Confirm `just dashboard` reflects a later intentional clean baseline refresh,
  not the dirty feature run.
- Confirm `just bench-nightly` records the landed commit on the benchmark host.
- Do not promote compliance or benchmark baselines merely to make a gate green.

Verification:

```bash
just dashboard
just bench-history --benchmark Generators
rg -n '\bdev\b|dev-ci' AGENTS.md docs .github/workflows
git ls-remote --heads --tags origin main dev archive/dev-20260801
git status --short --branch
```

Every remaining `dev` reference must be intentional historical context.

Move this plan to `docs/exec-plans/completed/` after recording workflow run
URLs, manifests, the release URL, the archive tag, and the Iterator PR result.

Status: [ ] not started

## Testing Strategy

- Workflow structure: `actionlint`, synthetic aggregator unit cases, then the
  completed Iterator feature as the first actual PR before ruleset activation.
- Compliance tooling: synthetic manifests prove trusted-base selection and
  equal-total failing-set swaps.
- Branch migration: patch-id and tree audit plus a recoverable archive tag.
- Runtime pilot: focused regression tests, filtered Iterator Test262, full PR
  Tier 3, full spec/Tier 1, and Tier 2.
- Performance: focused allocation attribution, fast/full local benchmark
  diffs, then nightly history on stable hardware.
- Release: verify no partial tag/release, redispatch, then inspect all assets
  and provenance.

## Known Risks

- A ruleset activated before `PR Gate` is observed can lock normal merges.
  Mitigate by using the completed Iterator PR to create the check, activating
  the rule only after it is green, and retaining a documented emergency bypass.
- Conditional jobs can appear successful when skipped. Mitigate with an
  always-running aggregator that knows which jobs classification required.
- A PR can edit a checked-in baseline. Mitigate by loading the trusted baseline
  from the base SHA.
- `main` and `dev` have rewritten histories. Mitigate with patch-id/tree audit
  and an archive tag instead of a blind merge or deletion.
- Full Tier 3 on runtime PRs increases latency. Use merge queue concurrency and
  caches first; relax only after measured evidence supports a safe classifier.
- GitHub-hosted performance measurements are noisy. Keep them informational
  until a stable self-hosted runner exists.

## Out of Scope

- Making Tier 3 literally reach 100%.
- Adding a GitHub-hosted absolute performance gate.
- Rewriting the release artifact format or versioning policy.
- Changing the `upstream` archival/sync purpose beyond replacing obsolete
  `dev` references.
- Implementing AsyncIterator, Iterator `zip`, `zipKeyed`, or `concat` in the
  first feature PR.
- Updating baselines before a clean full run has been reviewed.

## Decision Log

- 2026-08-01: Use short-lived branches and protected `main`; retire `dev` after
  an explicit history/tree audit.
- 2026-08-01: Require one stable aggregate `PR Gate`, with adaptive internal
  jobs and a conservative full fallback.
- 2026-08-01: Keep benchmarks local/nightly until stable hardware can produce a
  trustworthy required check.
- 2026-08-01: Use Iterator Helpers as the first feature PR because it exercises
  tests, Tier 3 exact-set comparison, and performance evidence together.
- 2026-08-01: Fix release publication by specifying the repository rather than
  adding an unnecessary checkout.
- 2026-08-01: Do not use a dummy PR to test the gate. Bootstrap the workflow,
  then use the completed Iterator feature as the first PR and activate
  protection after its `PR Gate` succeeds.

## Progress Log

- 2026-08-01: Plan written. Verified that the failed `v12.3.0` publication
  created neither a GitHub release nor a remote tag.
- 2026-08-01: Fixed release publication by passing `--repo` to `gh release
  create`; actionlint accepts the workflow. Redispatched Release run
  `30725514247`; it published `v12.3.0` at commit `51c501d7` with seven
  platform archives, `SHA256SUMS`, and build provenance.
- 2026-08-01: Added the adaptive PR gate, tested classifier and aggregate gate,
  trusted-base reusable compliance workflow, and adaptive post-merge `main`
  health workflow. The Iterator feature remains the first real PR.
- 2026-08-01: Audited `origin/dev` against `origin/main`. The branches differ
  by 15 and 12 graph commits, but `git cherry origin/main origin/dev` marks all
  12 `dev` commits patch-equivalent (`-`). Direct tree comparison shows only
  newer release, runtime, test, and documentation work on `main`; no unique
  `dev` patch needs replay. Preserve `dev` until the pilot PR merges, then tag
  its current tip before deletion.
- 2026-08-01: The bootstrap `main` run `30725500593` passed all six platform
  builds, Tier 1, Tier 2 exact-set comparison, and repository checks. Workflow
  lint alone failed because actionlint v1.7.7 did not support the existing
  `case()` expression. The Iterator branch updates both callers to v1.7.12.
- 2026-08-01: Completed the Iterator direct-record implementation and local
  validation before opening its PR. Focused tests pass; the full spec suite
  passes 3,672/3,672 across 98 files; Tier 2 passes 471/471. Filtered Test262
  manifest `tier3_20260801_175735_51c501d7-dirty.json` passes 367/514, with
  126 newly passing and zero newly failing tests against the trusted baseline.
  Fast benchmark manifest `bench_20260801_174627.json` and full manifest
  `bench_20260801_175534.json` cross no gates. Generators & Iterators improves
  from 325.0 ms to 312.6 ms (-3.8%), with flat RSS and +0.2% binary size.
  This dirty filtered run was preliminary evidence. The final commit-stamped
  manifest `tier3_20260801_181824_7fb474f9.json` passes 373/514, with 132 newly
  passing and zero newly failing tests. Source-path inspection confirms that
  helper `next()` no longer allocates its result object before it knows that it
  will return one, and result keys use the runtime's interned symbols. The RSS
  measurement is flat, so do not claim a measured peak-memory reduction.
- 2026-08-01: Kept the result-allocation and direct-record changes in one
  runtime commit. They modify the same helper-result control-flow hunks, so an
  independent revert would leave mismatched constructors and call sites. Revert
  the atomic Iterator commit if rollback is required.
