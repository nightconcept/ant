# 0005 — Promise state free list

- **Name:** promise-state-free-list
- **Hash:** d159ab94ed135064f0eb3ac210da45ab5bdab9d5
- **Date:** 2026-07-27
- **Status:** rejected — implemented, measured flat, reverted

## Context

`ant_promise_state_t` is 88 bytes and is `calloc`'d one-per-promise in
`get_promise_data` (`src/ant.c`), freed in the GC sweep
(`src/gc/objects.c:685`). Instrumented counts on
`js-bench/benchmarks/async.js`: **101,002 allocations**. On a `Promise.all`
with `.then` over 50,000 elements: 150,002.

The reasoning going in: at ~104 B including allocator header, that is ~10 MB of
promise state, and six figures of malloc/free pairs is measurable churn.
Recycling through a free list would drop the headers and keep the allocator out
of a hot path.

## Decision

Rejected. Implemented, measured, found to produce **no change**, and reverted
rather than kept on the strength of the argument.

## Measurement

Implementation: intrusive free list, freed entry's first word reused as the
link (so the pool costs no extra memory), entries handed back zeroed to match
the `calloc` contract. `promise_state_release` exported via
`include/gc/objects.h` and called from the sweep.

Two workloads, Linux x86_64, release, best-of-3:

**Concurrent — `async.js`** (101,002 states, nearly all live simultaneously):

| | time | peak RSS |
|---|---|---|
| calloc/free | 0.13 s | 109.5 MB |
| free list | 0.13 s | 109.3 MB |

**Churn — 300,000 sequential `await Promise.resolve(i)`** (states created and
collected continuously, never all live):

| | time | peak RSS |
|---|---|---|
| calloc/free | 0.11 s | 12.5 MB |
| free list | 0.11–0.12 s | 12.3 MB |

Flat on both. Two reasons, and they cover the whole space:

1. **Concurrent workloads have nothing to recycle.** All 101,002 states are
   live at peak, so the free list is empty exactly when it would need to
   supply. Peak RSS is set by live-set size, which a pool cannot change.
2. **Churn workloads are already served by glibc's tcache.** An 88-byte
   allocation is a per-thread cache hit; a hand-rolled free list is not
   meaningfully faster than the fast path it replaces.

## Options considered

**Keep it anyway for non-glibc allocators.** musl's mallocng has no equivalent
per-thread cache, so the churn case *might* show a win there. Not measured — no
musl build was to hand. If Ant's musl sandbox targets ever become a perf
concern, this is worth re-running before dismissing; the patch is small and the
shape is recorded above.

**Shrink `ant_promise_state_t` instead.** The real lever for the concurrent
case, since that is live-set size rather than allocator behaviour. 88 bytes is
`value` + `trigger_parent` + two GC list pointers + a 32-byte inline handler +
`handlers` pointer + id/count/state/flags. The inline handler is the obvious
target — it exists so the single-handler case avoids a `UT_array`
(`promise_handler_append`, `src/ant.c:169`), which is a good trade for speed
but costs 32 B on every promise including those that never get a handler. Not
attempted; would need its own measurement.

**Inline the state into `ant_object_t`.** Removes the separate allocation and
its header entirely. Rejected on sight: `ant_object_t` is 152 B and shared by
every object in the heap; adding 88 B to all of them to save an allocation on
promises is a large net loss.

## Consequences

- No code change landed. `get_promise_data` still `calloc`s;
  `src/gc/objects.c` still `free`s.
- Recorded so the next person costing out promise memory starts from
  "the allocation count is not the problem, the live-set size is" rather than
  re-deriving it.
- General lesson for this log: allocation *counts* are a hypothesis, not a
  result. This one looked compelling at 101,002 allocations and was worth
  exactly nothing.
