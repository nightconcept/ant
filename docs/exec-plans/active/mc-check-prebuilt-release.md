# Execution Plan: Prebuilt `mc` Releases for the mc-check Gate

Status: active
Last reviewed: 2026-07-26
Owner: theMackabu

## 1. Background

[Run 30210872643](https://github.com/nightconcept/ant/actions/runs/30210872643/job/89816750454)
("Tier 1 Compliance (Gate)") failed at `meson setup` with:

```
meson.build:1:0: ERROR: Unknown C std ['gnu23']. Possible values are
['none', ..., 'gnu2x', 'gnu11', 'gnu17', 'gnu18', 'gnu2x', ...]
```

Root cause: `compliance-tier1.yml` and `compliance-benchmarking.yml` install
Meson via `apt-get install -y meson`, which on `ubuntu-latest` resolves to
Meson 1.3.2 — too old to know the `gnu23` alias that `meson.build`'s
`default_options` requests (`c_std=gnu23`, meson.build:4). This is unrelated
to `mc` and is **Task 0** below: an independent, small fix that should land
first since it's currently red on `dev`.

Separately, `nightconcept/mc` (a Zig-built CLI wrapping TinyCC, see
[nightconcept/mc](https://github.com/nightconcept/mc)) already backs
`mc-check.yml`'s "Compile engine TUs with ../mc (TinyCC)" job — a strict
compile-check gate (`scripts/mc-check.sh`) that feeds each engine `.c`
translation unit through `mc build` using the flags from
`compile_commands.json`, independent of the production build. Today that job:

- Only runs `on: pull_request` / `workflow_dispatch` — not on every push.
- Rebuilds `mc` from source every single run (`Checkout mc` +
  `python3 scripts/build.py` in `mc-check.yml`), which is the slow step
  standing in the way of running it "always" (every push, not just PRs).

Decision (confirmed with the user): `mc` stays a compile-check gate, not the
production compiler. Production `ant` builds (`build.yml`,
`compliance-tier1.yml`, `compliance-benchmarking.yml`, platform builds) keep
using clang/gcc/zig cc as they do today — `meson.build` stays compiler-agnostic
so contributors and other CI can use whatever toolchain they need. "Use mc to
build ant always" means: widen `mc-check.yml` to run on every push/PR, made
affordable by pulling a prebuilt `mc` binary instead of rebuilding it from
source each time.

Release strategy (confirmed): a single moving `latest` pre-release in
`nightconcept/mc`, overwritten on every successful build of `mc`'s primary
branch. Ant's CI always pulls the `latest` tag; if it's missing (new repo,
deleted release, fork without releases), fall back to building `mc` from
source as today.

Note: `mc`'s default/primary branch is `dev` (it has no `main` branch — only
`dev` and `mir`), so the release job triggers on `push` to `dev`, not `main`.

## 2. Goal

1. `nightconcept/mc` cuts a `latest` pre-release on every successful build of
   its default branch, with per-platform binaries attached as release assets.
2. `ant`'s `mc-check.yml` pulls the `linux-x64` asset from that `latest`
   release instead of checking out and building `mc` from source, falling
   back to source-build if the release/asset isn't available.
3. `mc-check.yml` runs on every push (not just PRs), since the per-run cost
   drops from "build all of TinyCC + Zig frontend" to "download one binary."
4. `compliance-tier1.yml` / `compliance-benchmarking.yml` stop relying on
   apt's outdated Meson package, fixing the linked failure.

## 3. Constraints

- `mc`'s existing `mc.yml` CI already builds `linux-x64`, `macos-arm64`, and
  `windows-x64` via a `unix`/`windows` matrix and uploads them as
  `actions/upload-artifact` (7-day retention, not a release) — reuse this
  build matrix rather than duplicating it.
- `mc-check.yml` currently only runs on `ubuntu-latest`, so only the
  `linux-x64` asset is consumed for now. Keep the release job producing all
  three platforms anyway (mc.yml already does), since other ant CI jobs may
  want a prebuilt `mc` later (nanos/musl/platform builds), but ant-side
  consumption of non-linux assets is out of scope for this plan.
- `nightconcept/mc` has no existing `gh release` tags today — this is a new
  mechanism, not a change to an existing one.
- Overwriting a `latest` tag/release on every push requires deleting the prior
  release + tag (or using an action that supports `tag_name` reuse) — must
  handle "release already exists" without failing the workflow.
- Keep `mc-check.yml`'s fallback-to-source-build path so ant CI doesn't hard
  depend on `nightconcept/mc`'s release infrastructure staying up, and so
  forks of `ant` (which won't have permission to assume a specific upstream
  release layout changes) keep working.

## 4. Task List

### Task 0 — Fix the actually-broken job (independent, do first) — DONE
- `compliance-tier1.yml` and `compliance-benchmarking.yml` now install Meson
  via `pip install --break-system-packages -U meson` instead of
  `apt-get install -y meson` (ninja-build/clang stay on apt). Confirmed a
  current PyPI Meson (1.11.2) is available, well past when the `gnu23` alias
  was added.
- Validation still pending: needs a live CI run to confirm
  `meson setup build -Dbuildtype=release` now succeeds with `c_std=gnu23`.

### Task 1 — `nightconcept/mc`: cut a `latest` pre-release — DONE
- Added a `release` job to `mc`'s `.github/workflows/mc.yml`, gated on
  `needs: [unix, windows]` and `if: github.event_name == 'push' &&
  github.ref == 'refs/heads/dev'` (mc's default branch is `dev`, not `main`).
- Downloads the `mc-*` artifacts from the matrix jobs
  (`actions/download-artifact`, `pattern: mc-*`, `merge-multiple: true`) into
  `dist/`, then runs `gh release delete latest --yes --cleanup-tag || true`
  followed by `gh release create latest dist/* --prerelease --target
  "$GITHUB_SHA"`.
- Committed directly to `mc`'s `dev` branch (commit `d193456`) per explicit
  instruction — no PR was opened (one was opened and then closed at the
  user's request; the change instead landed as a direct push).
- Validation still pending: needs the next push to `dev` to confirm the
  `release` job actually creates/updates the `latest` pre-release with all
  three platform assets.

### Task 2 — `ant`: consume the `latest` mc release in `mc-check.yml` — DONE
- Replaced the unconditional "Checkout mc" + "Build mc" steps with a
  `Download latest mc pre-release` step (`id: mc-download`,
  `continue-on-error: true`) that runs `gh release download latest -R
  nightconcept/mc -p 'mc-linux-x64' -O mc/build/mc`, `chmod +x`, and a
  `test -s` sanity check.
- The old checkout/setup-zig/build-from-source steps are kept but now gated
  on `if: steps.mc-download.outcome != 'success'`, so any failure to fetch
  the release (missing release, renamed asset, rate limit, corrupt download)
  falls back to the previous behavior instead of going red.
- `scripts/mc-check.sh`'s expectation of `../mc/build/mc` relative to the ant
  repo root is unchanged — both the download and fallback paths land the
  binary at that same location.

### Task 3 — `ant`: widen `mc-check.yml` triggers — DONE
- `mc-check.yml`'s `on:` now includes `push` alongside `pull_request` and
  `workflow_dispatch`.
- Not yet promoted to a required status check — see Follow-ups.

## 5. Decision Log

- 2026-07-26: Confirmed `mc` stays a compile-check gate, not the production
  compiler — production builds keep using clang/gcc/zig cc; `meson.build`
  stays compiler-agnostic.
- 2026-07-26: Confirmed release strategy is a single moving `latest`
  pre-release, overwritten each build of mc's primary branch, over
  per-commit tags plus a `latest` pointer.
- 2026-07-26: `mc`'s primary/default branch is `dev`, not `main` (no `main`
  branch exists) — the release job triggers on push to `dev`.
- 2026-07-26: User asked for a PR on the `mc` change, then immediately
  retracted ("no don't open a PR"); the opened PR (`nightconcept/mc#1`) was
  closed and the change was instead pushed directly to `mc`'s `dev` branch
  per explicit follow-up instruction ("commit push it straight to dev").

## 6. Validation Status

Tasks 0–3 implemented (see task list above). Not yet validated with a live
CI run in either repo — next `ant` push should be checked for: (a) Tier 1
Compliance passing `meson setup`, (b) `mc-check.yml`'s download step
succeeding once `mc`'s `dev` push produces a `latest` release, and (c) the
fallback path still working if forced (e.g. by temporarily pointing the
download step at a nonexistent tag).

## 7. Follow-ups

- If other ant CI jobs (build-platform.yml, build-musl-sandboxes.yml,
  build-nanos.yml) later want a prebuilt `mc` for their own compile-checks,
  extend Task 2's download step to pick the right per-OS/arch asset instead
  of hardcoding `mc-linux-x64`.
- Consider whether `mc-check.yml` should become a required status check once
  it runs on every push and the fallback path has proven itself.
