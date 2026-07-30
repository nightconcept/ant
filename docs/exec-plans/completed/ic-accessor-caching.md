# Inline-Cache Accessor Caching + JIT Put-Field Unification (2026-07-28)

**Status:** Landed.

**Owner:** Claude Code (2026-07-28)

Follow-on from [IC Polymorphism Exploration](ic-polymorphism-2026-07-28.md),
which ended with a ranked list of next steps. This plan records why step 1 of
that list was dropped and what was built instead.

## Why Step 1 (CALL_METHOD IC) Was Dropped

The prior plan proposed adding an IC slot to `CALL_METHOD` to cache method
resolution. Reading the code first showed that premise does not hold in Ant:

- `obj.m(args)` compiles to `DUP; GET_FIELD m; args...; CALL_METHOD`
  (`src/silver/compiler.c:3166`). Method resolution already happens in
  `GET_FIELD`, which has an IC. By the time `CALL_METHOD` runs, the callee is
  on the stack — there is no lookup left to cache.
- The JIT already devirtualizes `CALL_METHOD` through the call-target feedback
  buffer (`sv_tfb_get_call_target`, `src/silver/swarm.c:9196`).

The only real gap was that call-target feedback is monomorphic and disables a
site after `SV_CALL_FB_MISS_DISABLE` (4) target changes, so a 4-shape rotation
never devirtualizes. Measured upside of fixing that, on the one benchmark with
genuine polymorphic dispatch:

| micro (280K iterations) | ant | node |
|---|---|---|
| `s.weight()`, 4 receiver shapes | 145ms | 23ms |
| same call site, forced monomorphic | 126ms | – |

Polymorphic call-target feedback was worth at most ~19ms (13%). Accessors, by
contrast, were 3× behind txiki.js:

| micro (280K iterations) | ant | txiki.js | node |
|---|---|---|---|
| accessor get + set | 190ms | 63ms | 12ms |
| plain field read | 46ms | – | – |
| plain field **write** | 78ms | – | 9ms |

So the work went to accessors (step 2 of the prior plan), plus a plain-write
problem that measurement surfaced along the way.

## What Changed

### 1. JIT put-field went through the IC (`src/silver/glue.c`)

`jit_helper_put_field` did not use the inline cache at all — it called
`js_mkstr` (an allocation) and then generic `js_setprop`, on every JIT'd
property write. The interpreter's `OP_PUT_FIELD` had a full IC the JIT never
saw.

The body of `sv_op_put_field` was extracted into `sv_prop_put_field_ic`, and
the JIT helper now calls it, taking `func`/`bc_off` so it can reach the IC slot
(the MIR `pf_proto` prototype grew from 6 to 8 args). Plain JIT'd field writes
went 78ms → 48ms against a 46ms read-only floor.

This also removed a real divergence: `regexp_note_property_write` was being
skipped on the JIT path.

### 2. The GET/PUT ICs now cache accessors (`src/silver/ops/property.h`)

Previously both ICs bailed on any property with a getter or setter, so every
accessor access fell through to a full by-string lookup — and the fallback then
looked the property up *again* to fetch the accessor function.

No new IC state was needed: `ant_shape_prop_t` already carries `getter` and
`setter` inline, so a cached shape + index is enough to reach them.

- `sv_ic_try_get_hit` invokes `prop->getter` with the original receiver as
  `this` instead of returning false. Setter-only properties read as undefined.
- `sv_ic_probe_get_chain` reports accessors (`out_is_accessor`) rather than
  refusing to fill.
- `sv_prop_put_field_ic` gained a cached-setter path, filled by
  `sv_ic_put_fill_proto_accessor` on first miss.

### 3. Accessor entries are fenced off from the JIT's inline load tail

The JIT's `mir_emit_get_field_ic_fastpath` reads the cached slot directly. An
accessor entry has no readable slot, so serving one there would return garbage.

`SV_GF_IC_AUX_ACCESSOR_BIT` marks such entries. The JIT already loaded
`cached_aux` and tested the ACTIVE bit with `AND`/`BEQ`; that became
`AND (ACTIVE|ACCESSOR)` / `BNE ACTIVE` — same instruction count, so the fence
is free. `sv_gf_ic_note_success`/`note_miss` rebuild `cached_aux` wholesale and
were updated to preserve the bit.

### 4. Union hazard (caused a segfault; fixed)

`sv_ic_entry_t.guard` is a union: `receiver_proto` (a nanboxed value) overlaps
`add.from_shape` (a *retained* shape pointer). Giving PUT entries a proto guard
meant an entry could switch between the two representations, and the next
`sv_ic_set_add_transition` would call `ant_shape_release` on a nanboxed value.

`sv_ic_put_drop_add_guard` makes the transition explicit: it releases retained
shapes only when the entry actually holds an add transition, and is called at
every point that rewrites the entry. The ACCESSOR bit keeps the two states
mutually exclusive.

### 5. Cold paths forced out of line

`sv_prop_put_field_ic` and `sv_ic_try_get_hit` are `static inline` into the
interpreter's computed-goto dispatch loop, so code added to them costs *every*
opcode. The first version regressed fannkuch — which has no property access at
all in its hot loop — by 6.7%.

Moving the accessor guard chains and call sequences into `noinline` helpers
(`sv_ic_get_invoke_accessor`, `sv_ic_put_try_cached_accessor`,
`sv_ic_put_fill_proto_accessor`) recovered most of it (6.7% → 2.4%). Worth
remembering: **anything added to these functions is paid by the whole
interpreter loop.**

## Results

Head-to-head against a baseline binary built from the same tree, hyperfine,
min-of-runs:

| benchmark | baseline | new | delta |
|---|---|---|---|
| nbody | 302.9ms | 176.8ms | **-41.6%** |
| class_dispatch | 335.2ms | 207.7ms | **-38.0%** |
| richards | 318.9ms | 246.9ms | **-22.6%** |
| deltablue | 335.7ms | 271.4ms | **-19.1%** |
| object_graph | 295.6ms | 253.5ms | **-14.2%** |
| gc_pressure | 356.2ms | 334.3ms | -6.1% |
| proxy_trap | 278.8ms | 294.7ms | **+5.7%** |
| fannkuch | 1007.9ms | 1033.8ms | +2.4% |

Everything else within ±3%. Accessor micro: 190ms → 85ms (txiki.js 63ms).

### Accepted regressions

- **proxy_trap +5.7%** — JIT'd writes to exotic receivers now take
  `setprop_interned` (the interpreter's path) instead of `js_setprop`. This is
  the cost of the two paths agreeing; special-casing the JIT helper would
  reintroduce the divergence. Follow-up: find why `setprop_interned` is slower
  for proxies.
- **fannkuch +2.4%** — residual interpreter dispatch-loop growth. Confirmed not
  semantic: fannkuch's hot loop is entirely typed-array elements, and reverting
  the JIT guard change alone did not recover it.

## Benchmark Harness Bug Found

`bench/bench.py` copies `build/ant` to `bench/bin/ant` before running. That
copy is wrapped in `except Exception: pass`, and it had been failing with
`ETXTBSY` because a leaked `ant` process from an earlier session held
`bench/bin/ant` open for execution. **Every bench run since 2026-07-27 silently
measured a stale binary** — the first post-change suite run reported
class_dispatch at -1.0% when the real figure was -38.8%.

The copy now unlinks the target first (which is what makes replacing a busy
executable work) and raises instead of swallowing the error. Any recorded bench
results between 2026-07-27 and 2026-07-28, including the checked-in baseline at
`0f68f14e`, should be treated as suspect.

## Validation

- `examples/spec/run.js --all`: 0 failures
- Tier 1 compliance: 100%
- `just preflight`: pass
- New `tests/test_accessor_ic.cjs`: passes on both ant and node — covers warm-IC
  getters/setters, `this` binding, throwing accessors, setter-only and
  getter-only properties, own accessors, accessor↔data redefinition in both
  directions, own-property shadowing, prototype swap, deletion, a site
  alternating accessor/data receivers, and strict-mode assignment.

### Pre-existing bug found while writing tests

`assert.throws(() => { o.x = 2; }, TypeError)` does not catch the throw when the
arrow gets inlined — the error escapes to the caller. Reproduced on an unmodified
baseline build, so it is unrelated to this work, but it is a live correctness bug
in the JIT's inlining of a callee that throws through a host call. The test uses
`try`/`catch` to work around it.

## Follow-ups

1. `assert.throws` / inlined-arrow exception escape (above) — real bug, not
   triaged.
2. `setprop_interned` slowness for exotic receivers (proxy_trap).
3. Polymorphic call-target feedback — measured at ~13% of one micro, low
   priority relative to the above.
4. Own accessors on the PUT path are still uncached (only prototype setters are);
   the GET path caches both.
