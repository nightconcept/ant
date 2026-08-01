# Testing Guide

Status: active
Last reviewed: 2026-07-30
Owner: theMackabu

This guide keeps validation proportional to the change while still protecting runtime behavior.

## Common Commands

- Build the configured tree: `just build`
- Fresh setup and build: `just setup && just build`
- Run one runtime test: `./build/ant tests/test_<name>.cjs`
- Run the spec suite: `./build/ant examples/spec/run.js --all`
- Run compliance test suite: `just compliance --tier all --smoke`
- Check performance while working: `just bench-fast-diff` (~75s)
- Validate repo knowledge docs: `just knowledge`
- Validate changed-file boundaries: `just structure`
- Ask the harness what to run for the current diff: `just validate_changes`


## Validation By Change Type

### Runtime behavior in `src/modules/`, `src/esm/`, or `src/builtins/`

- Run the most specific `tests/test_<name>.cjs` coverage you can find or add.
- Run `./build/ant examples/spec/run.js <spec_name>` when the change affects shared runtime
  semantics or built-ins used broadly across the platform.

### Engine behavior in `src/silver/`, `src/gc/`, or runtime core files

- Rebuild with `maid build`.
- Run focused regression tests first.
- Run `./build/ant examples/spec/run.js --all` before landing behavior changes.
- These are the paths where performance moves. Run `just bench-fast-diff` while
  iterating and a full `just bench-diff` before landing. See
  [benchmarking.md](benchmarking.md) for the tiers.

### Build or toolchain changes

- Re-run the affected Meson flow (`maid setup`, `maid reconfigure`, or
  `maid build`).
- Validate any new repo-knowledge or workflow checks locally with
  `maid knowledge` and `maid structure`.

## CI Workflows By Branch

This fork does not use pull requests — all work lands via direct pushes to
`dev`, `main`, or `upstream`. Each branch has its own top-level workflow that
triggers only on `push` to that branch (plus `workflow_dispatch` for manual
runs), so a single push fires exactly one of them.

- **`.github/workflows/dev-ci.yml`** (branch `dev`): `build-and-test` (all 6
  platform binaries, with the WinterTC gate running in the Linux x64 build
  and failing it if any test fails), `repo-knowledge` (doc-link and
  changed-file structure checks).
- **`.github/workflows/main-ci.yml`** (branch `main`): everything in
  `dev-ci.yml`, plus `compliance-tier2` — Tier 2 metric collection
  (`--allow-failures --log`) followed by an exact failing-test-set comparison
  with that branch's `docs/repo/compliance-baseline.json`. The gate fails
  closed if the baseline or full manifest is absent or invalid, the manifest
  identifies a different source revision, or any covered test newly fails.
  All jobs gate merges to `main`. Tier 1 is already gated inside
  `build-platform.yml`, so a push is checked against tiers 1 and 2.
- **`.github/workflows/upstream-ci.yml`** (branch `upstream`): identical job
  set and bar to `main-ci.yml`. `upstream` is a record of `theMackabu/ant`'s
  work kept for history and inspection, so this workflow exists to tell us when
  that record stops building — not to clear anything for submission.
- **`.github/workflows/tier3-weekly.yml`** (schedule): tier 3 is ~50k
  Test262/WPT tests, too slow to sit in front of a push, so it runs weekly
  (Mondays 04:00 UTC) plus on demand. A two-entry matrix explicitly checks out
  `main` and `dev`; each independently builds that ref, runs the full suite,
  compares exact failing-test names with that branch's checked-in baseline,
  and uploads `tier3-compliance-main` or `tier3-compliance-dev`. Branch-aware
  concurrency prevents the two jobs from cancelling one another.

**No performance gate runs in CI.** The bench threshold assertion compared
absolute milliseconds against a baseline recorded on a developer machine, which
cannot hold on a runner, and the ratio-based alternative is defeated by the
reference runtime being noisier than Ant itself. Both the reasoning and the
measurements are in [../exec-plans/tech-debt.md](../exec-plans/tech-debt.md);
speed and memory are checked locally with `just bench-fast-diff`.

Compare tiers as failing-test *sets*, not percentages: a net-positive rate can
still hide a newly failing test, and only the sets separate the two. Baselines
belong to the branch that checks them in; do not reuse a manifest or baseline
refresh from another branch merely because its aggregate totals match.

Reusable/utility workflows are not part of any branch's automatic signal —
they're `workflow_call` targets or `workflow_dispatch`-only:
`build-platform.yml` (single-platform build, called by all 3 CI workflows),
`build-nanos.yml`, `build-musl-sandboxes.yml`, `build-single.yml` (manual
sandbox/single-platform builds).

## Cutting a Release

Use the **Release** workflow and select the `main` branch in GitHub's **Use
workflow from** selector. Enter the `MAJOR.MINOR.PATCH` release version
(currently `12.3.0`); an optional `v` prefix is accepted and the created tag
is always `vMAJOR.MINOR.PATCH`. Leave **revision** blank to build
the `main` head captured when the workflow starts. To rebuild an earlier main
commit, enter its full 40-character SHA; the workflow rejects any SHA not
reachable from `main`. Set **prerelease** only for an intentionally
pre-release publication.

The workflow runs Tier 1 through the Linux x64 platform build and a Tier 2
exact-failing-set gate before it creates a Git tag or GitHub Release. Tier 3
remains the scheduled/on-demand regression suite rather than a release gate.
It builds every asset from the resolved SHA, then attaches target archives,
`SHA256SUMS`, and `provenance.json`. Normal pushes to `main` never publish a
release.

Platform builds cache downloaded vendor sources, npm downloads, Zig build
outputs, and up to 200 MB of compiler outputs per platform. Compiler and Zig
caches rotate weekly and restore the previous compatible entry. Full Meson
build directories are deliberately not cached.

## Notes

- Keep new tests close to the behavior they protect so future agent runs can
  discover the expected pattern quickly.
- In sandboxed agent sessions, builds and broad validation commands such as
  `maid build`, or `./build/ant examples/spec/run.js --all` may need broader system access.
  Pause and get explicit user approval before retrying them with sandbox
  escalation.
- In sandboxed agent sessions, `./build/ant examples/spec/run.js --all` can fail
  in the `fetch` spec because outbound network access is blocked. Treat that as
  an expected sandbox limitation, and prefer targeted spec files when the
  change does not need networked coverage.
- If the right validation is expensive or unavailable, document the gap in the
  associated [execution plan](../exec-plans/index.md).
