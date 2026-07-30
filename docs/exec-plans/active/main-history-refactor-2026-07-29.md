# Main History Refactor (2026-07-29)

Status: in progress
Last reviewed: 2026-07-29
Owner: Core Engineering

## Goal

Land the 67 commits currently in `main..dev` on `main` as a curated, linear
36-commit history, with no loss of tree content and no compliance or benchmark
regression.

## Scope

- Rewrite `main..dev` onto a new branch `main-merge` based at `main`
  (`13275217`). The requested name `dev/main-merge` is not creatable: `dev`
  exists as a ref, so `refs/heads/dev` cannot also be a directory.
- Drop history artifacts that exist only because of how the work happened:
  duplicated upstream commits, ancestry-restore merges, and a land-then-revert
  pair.
- Squash within single lines of work only. Keep every upstreamable spec fix as
  its own commit.
- Verify the rewrite, push, and let `main-ci.yml` gate it before `main` moves.

Out of scope: any behavior change, any new work, and the `upstream` repack
itself. This plan only reshapes commits that already exist.

## Constraints

- **Final tree must equal `dev`'s tree**, except for the generated baseline
  JSONs under `docs/repo/`, which legitimately differ because eight
  intermediate snapshots collapse into one.
- Tier 1 stays at 100%. Tier 2 stays at 100%. Tier 3 does not drop below the
  checked-in 63.1% baseline. Compare failing *sets*, not percentages
  ([../../repo/compliance.md](../../repo/compliance.md)).
- Upstream commit content and authorship are preserved verbatim. SHAs change,
  because they are replayed onto `main`; the true merge ancestry is retained on
  `dev`, which is what `just upstream-status` and future syncs read.
- `upstream` is a record of `theMackabu/ant`'s work kept for history and
  inspection, not a staging area for submission. "Upstreamable" is `main`'s
  standard.
- `dev` is not modified or deleted by this plan. `main-merge` survives until
  reviewed.

## Why The Current History Needs This

Four structural problems, all artifacts of process rather than of the work:

1. **Seven upstream commits appear twice.** Upstream rewrote its history
   mid-sync and `dev` carries both chains. All seven pairs are byte-identical
   patches (verified with `git patch-id --stable`); only the second chain is an
   ancestor of `upstream/master`.

   | dropped (pre-rewrite) | kept (on `upstream/master`) | subject |
   |---|---|---|
   | `7a048172` | `0c5bb973` | migrate away from stack-based coro (#62) |
   | `041792dc` | `76af457d` | remove non isolate global runtime struct |
   | `09e7bf09` | `9b4d6fcf` | move process onto the ant isolate |
   | `82ec1598` | `5aaae3f4` | make Object.create spec conformant |
   | `e68908d6` | `9838c9c1` | fix self-references inside symlinked packages |
   | `0b261cc4` | `e89e7289` | add thenable-job chain support |
   | `35818a94` | `8b22c065` | improve async ops |

2. **Three commits do the work of one import.** `920b27d6` merges the abandoned
   chain, `ac6152bf` squash-imports `707b9981`, and `c59cb13b` is an empty
   ancestry-restore merge. `ac6152bf` and `707b9981` share a patch-id, so the
   content lands once and the other two are bookkeeping.

3. **A land-then-revert pair.** `19146648` (`perf(async): right-size per-await
   VMs`) and `e122ffd9` reverting it as superseded by upstream #62. That
   sequencing existed to keep the *sync* legible; on a history where the import
   comes first, the commit should never exist.

4. **Eight commits are generated-data churn.** Each rewrites ~1500 lines of
   `docs/repo/bench-baseline.json` or a `compliance*-baseline.json`. They carry
   no review or bisect value and guarantee a conflict at every rebase step.

## Target History

Base: `main` (`13275217`). No merge commits. 36 commits.

**Ordering note.** The upstream block goes *first*, before our fork work, which
is not the order the work happened in. The reason is mechanical: replaying our
fork commits first and then upstream's leaves our code calling APIs upstream
renamed — a silent staleness git does not report as a conflict, because our code
and upstream's edits are in different hunks. Replaying upstream first inverts
that: every collision lands inside one of *our* commits, where resolving it is
legitimate, and each upstream commit stays verbatim. Verified empirically —
onto bare `main` all 8 upstream commits replay with one trivial conflict (the
nix hash); with our work underneath, they collide in `src/ant.c`,
`src/modules/math.c` and `packages/nix/vendor.nix`.

### 1–8: upstream, replayed verbatim

`0c5bb973`, `76af457d`, `9b4d6fcf`, `5aaae3f4`, `9838c9c1`, `e89e7289`,
`8b22c065`, `707b9981` — content and authorship unchanged. Six of the eight are
byte-identical patches by `git patch-id --stable`; the two that differ do so
only in hunk offsets, blob indices, and the *old* nix hash line being replaced.

### 9–10: the import's own consequences

| # | commit | from |
|---|---|---|
| 9 | `build(nix): refresh the vendor hash for the upstream import` | `2787e82e` |
| 10 | `fix(object): pin the defineProperty coercion instead of rooting via args` | new — see below |

### 11–35: fork work

| # | commit | replayed from |
|---|---|---|
| 11 | `fix(assert): compare BigInts by value, not by pointer` | `1873388a` |
| 12 | `fix(dataview): route element access through GetViewValue/SetViewValue` | `86c0c36b` |
| 13 | `feat(typedarray): add findLast and findLastIndex` | `dd9a755f` |
| 14 | `feat(compiler): apply NamedEvaluation to defaults and assignments` | `c2005005` |
| 15 | `perf(json): direct buffer serialization and allocation-free key snapshots` | `b2abecd5` + `d159ab94` |
| 16 | `perf(async): cut per-promise and per-await allocations` | `a555c7f5` + `02496b8d` |
| 17 | `chore(bench): import multi-runtime benchmark and compliance harness` | `ef6f53ed` |
| 18 | `fix(reflect): perform an ordinary [[Set]] in Reflect.set` | `f42a7494` |
| 19 | `fix(typedarray): resolve integer indices against the backing store` | `4c0ccac8` |
| 20 | `perf(vm): resolve element keys without building a string key` | `ade1a107` |
| 21 | `chore(repo): add a repeatable upstream sync process` | `115ca14b` + `24df3864` |
| 22 | `fix(child_process): drain stdio before emitting "close"` | `e9c32817` |
| 23 | `fix(parser): parse ``yield`` as an identifier outside generators` | `aa079c4b` |
| 24 | `fix(generator): reject ``next`` on an already-executing generator` | `78b946ed` |
| 25 | `fix(promise): route combinator elements through C.resolve and its then` | `de05bc2c` |
| 26 | `fix(object): define properties from own enumerable keys via [[Get]]` | `55b3c0cc` |
| 27 | `bench: two-tier suite with result history and a real CI gate` | `5c57c1d2` + `2b1ff51c` + `3fe45177` + `32011571` + `e9076ec7` + `983bf315` + `39992920` + `110dc457` |
| 28 | `fix: resolve the three tier 3 regressions the upstream import surfaced` | `8436030f` + `76dc93e5` |
| 29 | `tools: add just dashboard for compliance and bench snapshots` | `0f68f14e` + `7e5554c3` + `63b0a9c6` |
| 30 | `silver: cache accessors in property inline caches` | `6dda539b` |
| 31 | `gc: track pool pressure and lower the reserve floor` | `576ad958` + `c484d26d` + `8436ffa7` |
| 32 | `fix: align native Iterator method metadata` | `d151edad` |
| 33 | `fix: bring tier 2 compliance to 100%` | `30ad8d92` |
| 34 | `chore: refresh compliance and benchmark baselines` | `2613776c` + `ea1e82af` + `93165b1b` + `07421f3c` + `6281f93d` + `8d9fddf2` + `fbe3b395` + `80fc8b58` |
| 35 | `docs: gate main on tier 1/2/3 no-regression, redefine the upstream branch` | new |
| 36 | `docs: archive completed exec-plans, record this refactor` | new |

Dropped outright: the seven duplicate upstream commits, plus `19146648` and
`e122ffd9`.

Count: 67 commits become 36 — 15 upstream-authored become 8; 52 fork commits
including three merges become 25; three new commits (#10, #35, #36).

### The one new code commit

#10 is not a replay. `main` rooted the `Object.defineProperty` coerced key by
writing it back into the caller's rooted `args` array; upstream #62 turned the
builtin into a helper with no `args`. This is the exact hazard
[../../repo/upstream-sync.md](../../repo/upstream-sync.md) documents as its
worked example, and it is the one thing here the compiler caught rather than
git. `dev` resolved it inside the merge commit `920b27d6`, which neither parent
contains; a linear history has nowhere to put a merge-only resolution, so it
becomes its own commit. The code is identical to what `dev` shipped: split the
definition, pin `obj`/`prop`/`descriptor` under an explicit root scope, tail
call the body.

## Grouping Rationale

- **Spec fixes stay one per commit** (#11–14, 18–19, 22–26, 32). `compliance.md`
  requires small upstreamable changes; each of these is already one
  self-contained fix with its own test, and merging any two would make it
  un-sendable. This is deliberately where the count was not reduced.
- **Squashes stay inside one line of work.** `b2abecd5`+`d159ab94` are two
  halves of one JSON rewrite. `a555c7f5`+`02496b8d` is the async work plus the
  deletion of the two ADL entries `a555c7f5` itself added — squashed, ADL 0003
  and 0004 never exist, which is correct, since they document machinery that
  never survives to the tip. #26 is one benchmark tool iterated in place; only
  its final state has ever mattered.
- **Generated baselines collapse to one commit at the tip** (#33), which is the
  only point at which their numbers are true. The per-step percentages remain in
  the historical record via `compliance.md`'s commit-stamped logs.
- **The import is linear.** Per the branch layout in `AGENTS.md`, `main` is a
  release-quality presentation of the work; `dev` retains the real merge
  ancestry that `upstream-sync.md`'s tooling depends on.

## Task List

1. Write this plan and link it from the active index. *(done)*
2. Build `main-merge` at `main`, replaying the target history above.
3. Confirm tree equality against `dev` (only `docs/repo/*baseline*.json` and
   `bench-history.jsonl` may differ).
4. Build, then run `just preflight`, the spec suite, tier 1, tier 2, tier 3.
5. Push `main-merge`; wait for `main-ci.yml` to pass green.
6. Advance `main` to the reviewed branch. Leave `main-merge` in place.

## What The Risks Turned Into

All three predicted risks materialized, and all three are resolved.

- **Dropping `19146648` was not free.** `a555c7f5` called `sv_vm_create_sized`,
  an API only `19146648` introduced, and `adl/0001` cited the revert by SHA.
  Resolved by taking upstream's shape: the whole activation-VM block
  (`sv_async_prepare_materialization` and friends) stays deleted, which is what
  `dev` also ended up with — verified, `dev`'s final tree contains none of those
  four symbols. `adl/0001`'s prose now states that the combined measurement was
  taken on a tree carrying an experiment since dropped, instead of pointing at a
  commit this history does not have. This is the only intentional content
  difference from `dev`.
- **The five-file overlap was real** but smaller than feared once the upstream
  block moved first: `packages/nix/vendor.nix` (hash, superseded by #9),
  `src/modules/math.c` and `src/modules/buffer.c` (keep `utils.h`/`numbers.h`,
  drop the `runtime.h` upstream deleted), and `src/ant.c` (keep our native
  promise-combinator slots, adopt upstream's two-arg `js_obj_to_func`). Every
  resolution was checked against `dev`'s final file content, not guessed.
- **A vanished symbol did fail to compile rather than conflict** — the
  `defineProperty` prologue, commit #10 above.

## Decision Log

- 2026-07-29: Chose a linear `main` over preserving the merge. The merge was
  defensible — `upstream/master` forks from `8ba31b9b`, an ancestor of `main`,
  so a merge is the only way to keep upstream SHAs — but `dev` already records
  that ancestry, and `main` is the presentation branch.
- 2026-07-29: Kept upstream's eight commits individually rather than collapsing
  them, to preserve per-commit attribution and keep the `upstream` repack
  re-derivable.
- 2026-07-29: Verification scope set to tier 1 + tier 2 + tier 3 locally, with
  approval for the sandbox escalation the tier runs need.
- 2026-07-29: Put the upstream block first rather than preserving true
  chronology, after measuring that the alternative silently staled our code
  against renamed upstream APIs. See the ordering note above.
- 2026-07-29: `upstream` stops being a submission staging area and becomes a
  record of `theMackabu/ant`'s work; "upstreamable" moves to `main`. Landing on
  `main` now requires tier 1/2/3 no-regression against `dev`, compared as
  failing-test sets.

## Validation Status

Run on the 36-commit branch, whose source tree is byte-identical to `dev` — the
only differences from `dev` anywhere are twelve markdown files. That equality is
the strongest of these results: the binary is the same work, so the tier numbers
below are a confirmation rather than a discovery.

- Tree diff vs `dev`: 12 files, all markdown. Zero source, test, build or
  generated-data differences.
- `meson compile -C build`: passes. Needs `meson setup --reconfigure` first on a
  tree configured before this branch, because `src/gc/stats.c` is a new file and
  the configured build graph does not know it — otherwise it fails at link with
  undefined `gc_stats_enabled` / `gc_stats_note_remember`.
- `just preflight`, `just structure`, `just knowledge`: pass.
- Spec suite (`examples/spec/run.js --all`): 3672 passed, 0 failed.
- Tier 1: 100.0%. 0 newly failing, 0 newly passing.
- Tier 2: 466/466, 100.0%. 0 newly failing, 12 newly passing.
- Tier 3: 63.2%. 0 newly failing, 72 newly passing across 267 categories.
- `just bench-fast-diff`: no regression past the 6% time / 10% RSS / 25% size
  thresholds. Everything within run-to-run noise.

Two caveats worth stating rather than hiding:

- The tier 3 log is stamped `52abfd36`, a SHA that no longer exists — two commits
  were reworded afterwards to give them commit bodies. No file changed, so the
  result stands; `main-ci.yml` re-runs tier 2 at the final SHA and the weekly
  `tier3-weekly.yml` covers tier 3.
- Running the benchmarks rewrites `bench/versions.json` (timestamp and an
  embedded version string) even when the runtime set is unchanged, which
  `983bf315` was meant to stop. Discarded locally; the committed file matches
  `dev`. Worth a follow-up.

## Follow-ups

- `dev` still carries the old 67-commit history. Decide whether to reset it to
  `main` after this lands or leave it as the working record; nothing here
  modifies it.
- #33 (`bring tier 2 compliance to 100%`) is the one commit that mixes engine,
  test and harness changes — it touches `src/`, `tests/`, `src/pkg` and
  `scripts/compliance_common.py`. Left whole here; worth splitting along that
  seam if it is ever sent upstream.
