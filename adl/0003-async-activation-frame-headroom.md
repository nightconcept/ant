# 0003 — Async activation VM frame headroom

- **Name:** async-activation-frame-headroom
- **Hash:** d159ab94ed135064f0eb3ac210da45ab5bdab9d5
- **Date:** 2026-07-27
- **Status:** accepted

## Context

When a lazy-start async function suspends at an `await`, its frames are moved
off the caller's VM onto a dedicated activation VM
(`sv_async_prepare_materialization`, `src/silver/ops/async.h`). That VM stays
alive for as long as the await is pending, so its size is multiplied by the
number of *concurrently suspended* async calls.

`js-bench/benchmarks/async.js` holds 500 chains × 100 recursion depth =
**50,000 concurrently-live activations**. Instrumenting `sv_vm_create_sized`
showed 50,002 VMs totalling **67.2 MB** — the single largest cost in a 115 MB
run.

Per-VM composition, measured (`sv_frame_t` = 144 B, `sv_vm_t` = 96 B):

```
vm struct        96 B
stack           816 B   = (38 real slots + 64 guard) × 8
frames          432 B   = (frame_count 1 + 2) × 144
               ------
               1344 B   × 50,002 = 67.2 MB
```

The stack is already right-sized — `sv_vm_create_sized(js, stack_count +
headroom, ...)` computes the real need. The frame count was not: it allocated
`frame_count + 2`, so a single-frame activation got three frames and used one.

## Decision

Allocate `frame_count + 1` instead of `frame_count + 2`.

One spare frame absorbs the common "resume, then call one function" shape
without a realloc. Deeper growth is already handled — `sv_vm_grow_frames`
doubles on demand and is invoked from the three call sites that push a frame
(`engine.c:790`, `:1442`, `:1535`).

Safety is unchanged: the guard band and the `sv_stage_frame_args` reservation
logic are untouched.

## Measurement

Linux x86_64, release, best-of-5, `js-bench/benchmarks/async.js`.

| frames | VM bytes | time | peak RSS |
|---|---|---|---|
| `+2` (baseline) | 67.2 MB | 0.15 s | 115.2 MB |
| **`+1` (chosen)** | **60.0 MB** | **0.12 s** | **109.1 MB** |
| `+0` (measured, not taken) | 52.8 MB | 0.13 s | 107.4 MB |

Compliance: spec suite 3672/3672. Test262 tier 3 32842/53434, identical to
baseline. Tier 1 53/53.

## Options considered

**`frame_count + 0`.** Measured: a further 2.1 MB and no time regression *on
this benchmark*. Not taken, because it guarantees a `sv_vm_grow_frames` realloc
on every resume that calls any function — `max_frames == frame_count` leaves no
room at all. The async benchmark happens not to punish this, but it is a churn
risk for workloads that resume-and-call in a loop, and the win over `+1` is
small. Revisit only with a broader benchmark set that includes resume-heavy
shapes.

**Single allocation for vm + stack + frames.** Would save two malloc headers
(~32 B/VM, ~1.6 MB here) and improve locality. Not attempted: growth paths
(`sv_vm_reserve_stack`, `sv_vm_grow_frames`) realloc the buffers independently,
so a combined block needs an "is inline" flag and a migrate-on-first-growth
path. Moderate complexity for a small measured ceiling — estimate only, not
measured.

**Pool/recycle activation VMs.** Rejected on analysis for this workload: the
50,000 activations are concurrently live, so there is nothing to recycle and
peak RSS is unaffected. Would only help create/destroy churn in
sequential-await workloads.

**Shrink the stack guard band.** The largest remaining item at 512 B/VM. Split
out into [0004](0004-async-vm-stack-guard-band.md) — deliberately deferred.

## Consequences

- Activation VMs now have exactly one spare frame. Any future change that makes
  resumption push more than one frame before the next check should re-measure.
- The remaining per-VM cost is dominated by the guard band (512 B of ~1200 B).
  Further memory work on async has to go through 0004.
