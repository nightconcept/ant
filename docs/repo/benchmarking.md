# Benchmarking Guide

Status: active
Last reviewed: 2026-07-27
Owner: theMackabu

How Ant's performance is measured and how it is kept from drifting. Compliance
answers "is it correct"; this answers "is it still fast", and it is tracked the
same way — a checked-in baseline, a per-run manifest, and a diff that fails on
regression.

For correctness tiers read [compliance.md](compliance.md).

## The Two Halves

`bench/bench.py` runs each benchmark under Ant and the reference runtimes
(txiki.js, Node, Deno, Bun) via `hyperfine`, measures peak RSS and binary size,
prints the comparison tables, and writes a manifest to
`.deps/compliance/logs/bench_<timestamp>.json` with a `bench-latest.json`
symlink beside it.

`scripts/bench_baseline.py` is the memory. It promotes a manifest to
`docs/repo/bench-baseline.json`, appends every recorded run to
`docs/repo/bench-history.jsonl`, and diffs a new run against the baseline.

## Running

| Command | What it does |
| ------- | ------------ |
| `just bench` | Run and print the tables. Changes nothing. |
| `just bench-record` | Run, then append to the history. Use after an ordinary change. |
| `just bench-diff` | Run, then diff against the baseline. Exits non-zero on a regression. |
| `just bench-update-baseline` | Clean-tree run, then promote it to the baseline. |
| `just bench-history` | Print the recorded series. Takes `--benchmark <substr>`. |

`bench-update-baseline` refuses a dirty tree, and `bench_baseline.py update`
refuses a manifest whose revision is dirty or unknown — for the same reason the
compliance baseline does. A baseline has to be reproducible from a commit.

The everyday loop is `bench-record` after a change and `bench-diff` before
landing one; the baseline only moves when you have decided the new numbers are
the ones worth defending.

## Reading A Diff

Each benchmark reports time, peak RSS, and Ant's ratio against a reference
runtime (Node by default, `--reference` to change), plus binary size for the
run as a whole.

**The ratio column is a cross-check, not a gate.** Machine-wide noise — a busy
CPU, a different laptop, a thermal-throttled run — moves Ant and Node together
and leaves the ratio roughly where it was. A regression that shows up in
absolute time but not in the ratio is usually the machine; the diff says so
when it sees that shape. The converse is not true: for very fast benchmarks the
reference is itself noisy, so a moved ratio on its own means little.

Gating is on Ant's absolute numbers:

- **time** — default 5%. A delta must also exceed the two runs' combined
  standard deviation before it counts, so ordinary jitter does not fail a
  build. Manifests written before `stddev` was recorded fall back to the
  percentage alone.
- **peak RSS** — default 10%.
- **binary size** — default 25%. A runtime that gets faster by getting much
  larger is still a regression for an embeddable engine.

Benchmarks present on only one side are listed as added or missing and never
counted as regressions, so adding to `BENCHMARKS` does not break the gate.

## The History

`docs/repo/bench-history.jsonl` is append-only, one JSON object per recorded
run: commit, timestamp, runtime versions, and Ant's time, RSS, and reference
ratio per benchmark. It exists because a threshold only catches a single bad
step. Five changes that each cost 2% pass every diff and cost 10% together;
`just bench-history` makes that shape visible.

Rows are printed in timestamp order, not file order, and rows measured on a
dirty tree are marked `*` — treat those as indicative only.

## CI

`main` and `upstream` run `bench/bench.py --check-thresholds --max-speed-lag
10.0 --max-size-growth 25.0`, which diffs the run against the checked-in
baseline and fails the job on a regression. `--max-speed-lag` is the time
threshold and `--max-size-growth` the binary-size threshold.

If there is no baseline yet, the check **fails** rather than passing quietly —
a gate with nothing to compare against is not a gate, and the previous silent
pass is what let this go unnoticed. Seed one with `just bench-update-baseline`.

## Recording A Decision

Performance work that changes an architectural trade-off belongs in the
[ADL](../../adl/README.md), which requires real measurements and a named
baseline. The manifest path and commit from the run backing the entry are what
make it checkable later.

## Related

- Correctness tiers and their bars: [compliance.md](compliance.md)
- Validation scope: [testing.md](testing.md)
- Architecture Decision Log: [../../adl/README.md](../../adl/README.md)
