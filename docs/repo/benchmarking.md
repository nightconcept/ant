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
| hyperfine | 1 warmup, 5 runs | 1 warmup, 5 runs |
| wall time | ~75s | ~2m55s |
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
| `just bench-fast` | Fast tier, print the tables. ~75s. |
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
and reports it in its own box, then subtracts it from each time to give a
**work** column with the percentage of wall time that was real work.

This matters because it decides whether a number means anything. Before it
existed, `ic_polymorphic` did 3ms of work inside a 15ms process and was
published as a compute ratio when it was mostly a startup ratio. Benchmarks are
now sized so Ant spends 250–400ms, which keeps work time above ~60% on every
runtime. `coldstart` is the deliberate exception: measuring startup is its job,
so a near-zero work time there is the correct answer.

The ratio-to-reference column is computed from work time, not raw times.

## Why The Fastest Sample, Not The Mean

Benchmark noise is one-sided. Scheduling, interrupts, cache eviction and
thermal effects can only make a sample *slower* — nothing makes the machine
faster than it is capable of. So the fastest sample is the cleanest estimate of
the real cost, and the mean estimates "the cost plus whatever else the machine
was doing".

Measured over 8 independent invocations of 6 benchmarks, drift between
invocations of **identical code** — which is exactly what a spurious regression
looks like:

| estimator | runs | median | p90 | max |
| --- | --- | --- | --- | --- |
| mean | 10 | 1.8% | 3.9% | 6.9% |
| mean | 6 | 2.6% | 5.7% | 8.2% |
| trimmed mean (drop 2 slowest) | 6 | 2.2% | 3.8% | 7.1% |
| **min** | **5** | **1.5%** | **3.1%** | **3.9%** |
| min | 10 | 0.8% | 1.4% | 3.7% |

The minimum of 5 runs is more stable than the mean of 10 while taking half the
samples. That is what pays for both tiers getting faster and the gate getting
*tighter* at the same time: the threshold went from 5% to 6% while the actual
noise it has to clear more than halved. The old 5% sat below the mean's own
6.9% worst case — the gate was under its noise floor and fired on unchanged
code.

Both tiers use the same estimator **and the same run count**, deliberately. The
minimum is biased by how many samples it picks from — min of 10 runs sits ~0.7%
below min of 5 on the same workload — so differing run counts would inject that
bias as a phantom regression on every fast run diffed against a full baseline.

`mean`, `median` and `stddev` are still recorded in the manifest for
diagnostics; only the gate changed.

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

- **time** — default 6%, on the fastest sample, and a delta must also be worth
  at least **1.5ms** in absolute terms. The floor exists because a percentage
  alone misjudges very short benchmarks: `coldstart` runs in ~5.4ms and drifts
  up to 1.27ms run to run, which is 21% — it would fail constantly while
  measuring nothing. Every other benchmark sits at 280–410ms, where 6% is
  17–25ms, so the floor is inert for them. Manifests predating the `best` field
  are gated on the mean, where the older combined-standard-deviation check
  still applies.
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
   would otherwise miss, and check `just bench-fast` still fits its budget.

## The History

`docs/repo/bench-history.jsonl` is append-only, one JSON object per recorded
run: commit, timestamp, runtime versions, and Ant's time, RSS, and reference
ratio per benchmark. It exists because a threshold only catches a single bad
step. Five changes that each cost 2% pass every diff and cost 10% together;
`just bench-history` makes that shape visible.

Rows are printed in timestamp order, not file order, and rows measured on a
dirty tree are marked `*` — treat those as indicative only.

## CI

**No benchmark gate runs in CI** — not for speed, not for memory. `bench.py
--check-thresholds` still exists and still fails when there is nothing to
compare against, but no workflow calls it.

The reason is that the comparison is not valid across machines. The gate diffs
absolute milliseconds against `bench-baseline.json`, which is recorded wherever
`just bench-update-baseline` was run, so on a GitHub runner every benchmark reads
15–47% slower with no code change. Normalising by the ratio to node does not
rescue it: between two runs of identical Ant code on one machine with the same
node build, Ant's own fastest-sample time drifts at worst 5.4% while node drifts
15% (28% once its ~18ms startup floor is subtracted), so the reference is noisier
than the subject.

The full measurement, and what re-enabling it would take, is recorded in
[../exec-plans/tech-debt.md](../exec-plans/tech-debt.md). Do not re-add the step
without a baseline recorded on the runner class CI uses — it will fail on every
push.

Until then, performance is checked locally: `just bench-fast-diff` against a
locally-recorded baseline is a valid Ant-vs-Ant comparison, and
`bench-history.jsonl` carries the trend.

## Recording A Decision

Performance work that changes an architectural trade-off belongs in the
[ADL](../../adl/README.md), which requires real measurements and a named
baseline. The manifest path and commit from the run backing the entry are what
make it checkable later.

## Related

- Correctness tiers and their bars: [compliance.md](compliance.md)
- Validation scope: [testing.md](testing.md)
- Architecture Decision Log: [../../adl/README.md](../../adl/README.md)
