# Benchmarking Guide

Status: active
Last reviewed: 2026-07-28
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

## Two Tiers

The suite runs at two sizes. **The workloads are identical in both** — a tier
changes only which benchmarks run, on which runtimes, and for how many
repetitions. That is why one baseline serves both: a fast manifest diffs
against the same `bench-baseline.json`, and the benchmarks it skipped are
reported as not-run rather than missing.

| | fast | full |
| --- | --- | --- |
| benchmarks | 15 | 26 |
| runtimes | ant, txiki.js, Node | all five |
| hyperfine | 1 warmup, 6 runs | 2 warmup, 10 runs |
| wall time | ~85s | ~5 min |
| for | edit-test loops | nightly cron, pre-merge, CI |

The fast tier keeps one benchmark per subsystem and drops the rest. Deno and
Bun are full-tier only: Node is the reference the ratio column divides machine
noise out against, and txiki.js is the closest-peer small runtime, so those
three answer the question a mid-change run is actually asking.

A fast run **cannot** be promoted to the baseline. Both `bench.py` and
`bench_baseline.py update` refuse it — promoting a subset would shrink the
baseline to whatever the fast tier covered, and every benchmark it skipped
would read as "new" on the next full run.

## Running

| Command | What it does |
| ------- | ------------ |
| `just bench-fast` | Fast tier, print the tables. ~85s. |
| `just bench-fast-diff` | Fast tier, then diff against the baseline. The everyday check. |
| `just bench` | Full suite, print the tables. Changes nothing. |
| `just bench-record` | Full run, then append to the history. |
| `just bench-nightly` | Full run recorded to the history. What the cron calls. |
| `just bench-diff` | Full run, then diff against the baseline. Exits non-zero on a regression. |
| `just bench-update-baseline` | Clean-tree full run, then promote it to the baseline. |
| `just bench-history` | Print the recorded series. Takes `--benchmark <substr>`. |

`bench-update-baseline` refuses a dirty tree, and `bench_baseline.py update`
refuses a manifest whose revision is dirty or unknown — for the same reason the
compliance baseline does. A baseline has to be reproducible from a commit.

The everyday loop is `bench-fast-diff` while working and a full `bench-diff`
before landing; the baseline only moves when you have decided the new numbers
are the ones worth defending.

### Nightly

The full suite is meant to run nightly on the development machine, not in CI —
CI runners are too noisy for the numbers to mean much, and the history series
is only useful when consecutive rows come from the same hardware. Install it
with a crontab entry:

```
0 3 * * * cd /path/to/ant && /usr/bin/env just bench-nightly >> /tmp/ant-bench-nightly.log 2>&1
```

`bench-nightly` records to the history and leaves the baseline alone, so an
unattended run can never move the thing it is being compared against.

## Startup Floor And Work Time

Every benchmark's wall time includes the cost of starting the runtime process,
and those costs are not close: Ant starts in ~3.5ms, Node in ~18ms. Each run
measures this floor per runtime (median of 12 executions of a trivial script)
and reports it in its own box, then subtracts it from each mean to give a
**work** column with the percentage of wall time that was real work.

This matters because it decides whether a number means anything. Before it
existed, `ic_polymorphic` did 3ms of work inside a 15ms process and was
published as a compute ratio when it was mostly a startup ratio. Benchmarks are
now sized so Ant spends 250–400ms, which keeps work time above ~60% on every
runtime. `coldstart` is the deliberate exception: measuring startup is its job,
so a near-zero work time there is the correct answer.

The ratio-to-reference column is computed from work time, not raw means.

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

## The Ant-Only Group

`solo_http` and `solo_fs` carry `"runtimes": ["ant"]`. There is no portable
server or filesystem API across the five runtimes — Ant uses `Ant.serve`, Node
uses `node:http`, Deno and Bun each differ — so comparing them would mean
comparing different programs. They run on Ant alone and are tracked against
Ant's own history rather than a cross-runtime ratio. `src/http/`, `src/net/`,
`src/modules/server.c` and `src/modules/fs.c` had no coverage at all before
them; a one-sided number that moves is worth more than no number.

Both are self-contained: `solo_http` binds an ephemeral port in-process and
stops the server when done, and `solo_fs` works in a temp directory it removes
on exit.

## Adding A Benchmark

1. Write `benchmarks/<id>.js` and a `.ts` mirror. Print a **deterministic
   checksum** — that is what catches an engine computing the wrong answer
   quickly, which is how a broken `fannkuch` and an Ant `replace` bug were both
   found. Never put engine-specific values (stack strings, iteration order) in
   the checksum.
2. Size it so Ant lands in **250–400ms**. Below that, process startup dominates
   the faster runtimes; above it, the fast tier stops fitting its budget.
3. Verify it prints the same checksum on Ant, Node and txiki.js before trusting
   any timing from it.
4. Add an entry to `BENCHMARKS` in `bench/bench.py` with a `tier`. Default to
   `"full"`; promote to `"fast"` only if it covers a subsystem the fast tier
   would otherwise miss, and check `just bench-fast` still fits ~90s.

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
