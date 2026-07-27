# 0004 — Async VM stack guard band sizing

- **Name:** async-vm-stack-guard-band
- **Hash:** d159ab94ed135064f0eb3ac210da45ab5bdab9d5
- **Date:** 2026-07-27
- **Status:** deferred — explicitly not taken

## Context

After [0003](0003-async-activation-frame-headroom.md), the largest single
component of an async activation VM is the stack guard band:

```
vm struct        96 B
stack           816 B   = (38 real slots + 64 guard) × 8   ← 512 B is guard
frames          288 B
               ------
               ~1200 B  × 50,000 concurrent activations
```

`SV_STACK_GUARD_SLOTS` is a flat 64 slots (`src/silver/engine.c:43`), added to
every VM's stack allocation. On the main VM that is rounding error. On 50,000
async activation VMs it is **~25 MB**.

Reaching the stated target for `js-bench` "Async & Microtasks" (< Deno's
77 MB peak RSS; currently 109 MB) essentially requires this change plus one
other.

## Why the guard exists

`sv_stage_frame_args` (`src/silver/engine.c:592`) reserves before every frame
push:

```c
int reserve = need + func->max_stack;
if (vm->sp + reserve > vm->stack_size) { /* grow */ }
```

with the comment: *"pushes in the dispatch loop are unchecked, so this is the
only point that guarantees they stay in bounds."*

So `sp` is bounded by `stack_size` **provided `func->max_stack` is correct**.
The guard band is slack that absorbs an under-reported `max_stack`, and the
assert immediately above it says so:

```c
/* If this trips, some function's computed max_stack under-reported its real
   operand depth and the caller has been writing into the guard band. */
assert(vm->sp <= vm->stack_size + SV_STACK_GUARD_SLOTS);
```

The guard is therefore **redundant under a correct compiler and load-bearing
under a buggy one**. Shrinking it does not change behaviour; it changes the
failure mode when `max_stack` is wrong — from an assert that fires in debug
builds to silent out-of-bounds writes in release.

## Decision

Deferred. Owner's call (2026-07-27): take unambiguously safe wins only; leave
the guard alone.

The memory is real and the analysis holds, but thinning a deliberate safety net
is not a trade to make for a benchmark number without separate sign-off.

## How to implement if revisited

Preferred shape — make the guard per-VM rather than a global constant, so the
main VM keeps its full margin:

1. Add `int guard_slots` to `sv_vm_t` (`include/silver/engine.h`).
2. `sv_vm_create_sized` takes the guard as a parameter; store it, and allocate
   `stack_size + vm->guard_slots`.
3. `sv_vm_limits` returns a guard per `sv_vm_kind_t`: keep 64 for
   `SV_VM_NORMAL`, use 8–16 for `SV_VM_ASYNC`.
4. Replace every textual `SV_STACK_GUARD_SLOTS` with `vm->guard_slots`. Sites:
   `engine.c` lines 65, 148, 151, 600, 618. **Line 618 matters** — it bounds
   the `args` pointer during a stack realloc; getting it wrong reads freed
   memory.
5. `sv_async_prepare_materialization` passes the async guard through.

Validation required before accepting:

- Build with `just debug` (asserts on) and run the full spec suite — the assert
  at `engine.c:600` is the tripwire for an under-reported `max_stack`.
- `just asan` build over `examples/spec/run.js --all` and the async benchmark;
  ASAN is what will actually catch a guard-band overrun.
- Test262 tier 3 must stay at the baseline pass count (32842/53434 at this
  hash) and tier 1 at 53/53.

Expected yield, **estimated not measured**: guard 64→8 saves 448 B/VM ≈ 22 MB
on the async benchmark, taking ~109 MB to ~87 MB. Reaching < 77 MB needs this
*and* the derived-promise elimination described in
[0001](0001-promise-combinator-native-slots.md) (~240 B/element).

## Options considered

**Shrink `SV_STACK_GUARD_SLOTS` globally.** Simplest diff, largest win, but
thins the margin on the main VM too, where the memory saved is irrelevant.
Strictly worse trade than the per-kind version.

**Drop the guard entirely and rely on the reservation.** Correct if and only if
`max_stack` is exact for every opcode path. The assert's existence says the
authors were not willing to bet on that. Would need a verification pass over
the compiler's `max_stack` computation first.

**Right-size the guard from the function's own `max_stack`.** The handoff path
already computes `headroom = max(max_stack)` over the copied frames; the guard
could be a small constant on top of that rather than a flat 64. Most principled
option, and cheap to compute at materialisation time. Untested.

**Leave async VMs alone; attack the count instead.** The deeper fix is not to
give each suspended activation a general-purpose VM at all, but to spill only
the live register state of the suspended frame — what V8/JSC do. That is a
substantial refactor of the suspend/resume path, and out of scope for a
perf pass, but it is the only option that removes the cost rather than shrinking
it.

## Consequences of deferring

- Async peak RSS stays ~109 MB against a 77 MB target. The benchmark gap is
  memory, not correctness.
- Any future attempt at the async memory profile must start here; the other
  components (vm struct, right-sized stack, one spare frame) are already at or
  near their floor.
