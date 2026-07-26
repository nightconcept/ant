# Testing Guide

Status: active
Last reviewed: 2026-04-09
Owner: theMackabu

This guide keeps validation proportional to the change while still protecting runtime behavior.

## Common Commands

- Build the configured tree: `just build`
- Fresh setup and build: `just setup && just build`
- Run one runtime test: `./build/ant tests/test_<name>.cjs`
- Run the spec suite: `./build/ant examples/spec/run.js --all`
- Run compliance test suite: `just compliance --tier all --smoke`
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

### Build or toolchain changes

- Re-run the affected Meson flow (`maid setup`, `maid reconfigure`, or
  `maid build`).
- Validate any new repo-knowledge or workflow checks locally with
  `maid knowledge` and `maid structure`.

## CI Workflows By Branch

This fork runs three branch-scoped top-level workflows instead of one
workflow per concern. Each only triggers on `push`/`pull_request` targeting
its own branch, so a single commit fires exactly one of them.

- **`.github/workflows/dev-ci.yml`** (branch `dev`): `build` (all 7 platform
  binaries), `tier1` (Tier 1 compliance gate — fails if any Tier 1 test
  fails), `mc-check` (TinyCC compile check), `repo-knowledge` (doc-link and
  changed-file structure checks).
- **`.github/workflows/main-ci.yml`** (branch `main`): everything in
  `dev-ci.yml`, plus `compliance-benchmarking` — Tier 2/3 metric collection
  (`--allow-failures --log`) with a regression check against
  `docs/repo/compliance-baseline.json` (fails if passed-test counts drop),
  and the cold-start bench threshold assertion (`python3 bench/bench.py
  --check-thresholds --max-speed-lag 10.0 --max-size-growth 25.0`, never
  slower by >10% or larger by >25% vs Upstream Ant). All jobs gate merges to
  `main`.
- **`.github/workflows/upstream-ci.yml`** (branch `upstream`): identical job
  set and bar to `main-ci.yml`, kept as its own file so it can be retired
  independently once a change actually ships upstream.

Reusable/utility workflows are not part of any branch's automatic signal —
they're `workflow_call` targets or `workflow_dispatch`-only:
`build-platform.yml` (single-platform build, called by all 3 CI workflows),
`build-nanos.yml`, `build-musl-sandboxes.yml`, `build-single.yml` (manual
sandbox/single-platform builds).

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
