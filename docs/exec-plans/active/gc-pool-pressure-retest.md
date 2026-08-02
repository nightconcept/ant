# GC Pool-Pressure Retest

Status: active
Last reviewed: 2026-07-29
Owner: theMackabu

## Goal

Reduce Ant's overall peak RSS while preserving enough speed to remain
competitive with txiki.js. Keep the collector experiment on a short-lived
branch from `main`, retain its measurement history, and track its relationship to the
upstream performance branch where the policy was first developed.

## Provenance

- Current experiment branch: `perf/gc-policy-retest`
- Current experiment commit: `576ad958`
- Original remote branch:
  `upstream/perf/silver-jit-elysia-parity`
- Original collector commit: `604bb956`
  (`extract GC telemetry and tune pool pressure floor and nursery band`)
- Original protocol/results commit: `085ab2df`
- `604bb956` is not an ancestor of `dev` or `upstream/master`, has no
  patch-equivalent commit on `dev`, and remains reachable only through the
  remote performance branch. No revert was found; the feature branch was
  never merged into upstream master.

The current experiment intentionally ports only the opt-in telemetry and the
1 MiB pool-pressure floor. It keeps the current `main` nursery adaptation,
forced-collection cadence, coroutine handling, and stack scanning.

## Measurement Results

Both variants were measured with `just bench-fast-diff` against baseline
`6dda539b`. These are performance-tier results, not compliance-tier results.

| Variant | Mean fast-tier time | Average fast-tier RSS | Gate result |
| --- | ---: | ---: | --- |
| Full historical collector policy | +1.3% | -7.1% | 3 regressions |
| 1 MiB pool floor plus telemetry | +0.8% | -9.4% | 2 regressions |

The current narrowed variant produced:

| Benchmark | Time | Peak RSS |
| --- | ---: | ---: |
| Rope String Concatenation | -11.6% | -29.6% |
| Richards OS Simulation | -7.2% | -48.9% |
| Exception Unwinding | -3.2% | -51.4% |
| GC Pressure & Promotion | -1.1% | -13.6% |
| Filesystem Churn | +2.2% | -46.9% |
| Object Graph & AST | +9.6% | +0.2% |
| JSON Serialization | +8.0% | -10.9% |

Object Graph was a clear fast-tier regression. JSON crossed the absolute
speed gate, but its Node-normalized ratio held and the benchmark tool marked
it as suspected machine noise. The full historical policy also regressed
Async & Microtasks, Object Graph, and Web Streams in the fast tier.

Raw manifests:

- Full historical policy:
  `.deps/compliance/logs/bench_20260729_034826.json`
- Narrowed 1 MiB policy:
  `.deps/compliance/logs/bench_20260729_035209.json`

## Decision Log

- 2026-07-29: Recovered the unmerged collector work from
  `upstream/perf/silver-jit-elysia-parity` and adapted it to current `dev`.
- 2026-07-29: Rejected the full historical policy as the default candidate
  after three fast-tier regressions.
- 2026-07-29: Narrowed the branch to telemetry plus the 1 MiB pool-pressure
  floor. This improved average fast-tier RSS by 9.4%, but retained a clear
  Object Graph slowdown.
- 2026-07-29: Keep the narrowed change available for now because its broad
  memory reduction may justify the speed tradeoff. Do not describe it as
  passing the performance gate.

## Validation Status

- `meson setup --reconfigure build`: passed.
- `meson compile -C build`: passed.
- Focused GC, async-generator liveness, and JIT rope-root tests: passed.
- `just preflight`: passed.
- `just bench-fast-diff`: completed twice; failed on the performance
  regressions recorded above.
- Compliance tiers 1, 2, and 3: not run; no compliance regression has been
  observed or claimed.
- Full benchmark tier and full spec suite: not yet run.

## Follow-Ups

1. Run the full benchmark tier before opening a pull request to `main`.
2. Run the broad spec suite and the appropriate compliance checks before
   treating the branch as landable.
3. Re-run JSON in a quiet paired session to distinguish noise from a real
   regression.
4. Attribute Object Graph's extra collections and determine whether pool
   pressure should be based on allocation kind or live pool bytes instead of
   one global floor.
5. Periodically check whether `604bb956` or an equivalent collector policy
   lands on `upstream/master`; remove redundant fork code if it does.
