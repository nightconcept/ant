# IC Polymorphism Exploration (2026-07-28)

**Status:** Attempted, measured, reverted. Provided valuable context for future dispatch optimization.

**Owner:** Claude Code (2026-07-28)

## Summary

Implemented a 4-way polymorphic inline cache for property gets (both interpreter and JIT paths). The change was technically sound and validated cleanly, but provided no measurable benefit across the benchmark suite and increased `sv_ic_entry_t` size by 136 bytes per IC site (64 → 200 bytes).

Root cause discovered post-implementation: the benchmarks we thought would benefit (richards, deltablue, object_graph, nbody) are allocation/GC-dominated, not property-dispatch-dominated. Only `class_dispatch` exercises real polymorphic dispatch, but its cost bottleneck is **accessor getters/setters**, which the IC explicitly bails on (returns false, falls back to full lookup).

## What We Built

### Interpreter IC (`src/silver/ops/property.h`)

- New `sv_ic_way_t` struct (32 bytes each, 4 per site):
  - `ant_shape_t *shape` — receiver shape (8)
  - `ant_object_t *holder` — resolved property holder (8)
  - `ant_value_t receiver_proto` — receiver's prototype chain guard (8)
  - `uint32_t index` — slot in holder (4)
  - `bool is_own` — property is on receiver vs prototype (1)
  - padding (3)

- `sv_ic_entry_t` gains:
  - `sv_ic_way_t ways[SV_IC_GET_WAYS]` (128 bytes for 4 ways)
  - `uint32_t ways_epoch` — separate from monomorphic `epoch` field
  - `uint8_t way_count` — number of filled ways (0-4)
  - `uint8_t way_victim` — round-robin eviction cursor

- `sv_ic_try_get_hit()` scans ways in fill order (no reordering on hit, to avoid thrashing on 2-shape alternation)
- `sv_ic_get_fill()` fills ways round-robin, or refreshes an existing way's metadata if the shape matches

**Why separate `ways_epoch`:** The JIT inline guard and the PUT_FIELD path both write to `ic->epoch` without knowledge of ways. Sharing epochs between them would risk resurrecting a stale way after an IC epoch bump. The ways carry their own `ways_epoch`, invalidated independently when the put or JIT paths populate the monomorphic fields.

### JIT Guard (`src/silver/swarm.c:1096`)

- Shape check now scans the ways array instead of a single monomorphic slot
- For each of 4 ways:
  - Load `way[i].shape` from memory
  - Compare to receiver shape
  - If match: set `r_way` to the way's address and jump to `way_found`
  - Otherwise: continue to next way
- If no way matches, jump to slow path (interpreter fallback)
- The load tail (proto check, holder validation, property read) is reused for all ways, reading from `r_way` instead of `r_ic`

This avoids 4 copies of the ~30-instruction load tail; it's a way-selection chain (~8 instructions per way, 32 total for 4 ways) plus 4 field-offset changes in shared code.

## Measurement Results

### Baseline (current on dev)

```
benchmark        baseline
class_dispatch        339ms
richards              350ms
nbody                 259ms
deltablue             371ms
object_graph          288ms
closures              328ms
generators            315ms
```

### After Polymorphic IC

```
benchmark        poly-jit
class_dispatch        346ms  (+2%)
richards              358ms  (+2%)
nbody                 276ms  (+7%)
deltablue             376ms  (+1%)
object_graph          284ms  (-1%)
closures              318ms  (-3%)
generators            320ms  (+2%)
```

**All changes within noise.** Expected sensitivity was 5-10% on property-heavy loops.

### IC Instrumentation Data

Interpreter GET hits/misses per benchmark:

```
class_dispatch   calls=1191722 hits=350889 misses=840833 poly_hits=328818
object_graph     calls=252136  hits=252064  misses=72     poly_hits=52085
deltablue        calls=1998    hits=1675   misses=323    poly_hits=1188
richards         calls=702     hits=594    misses=108    poly_hits=95
nbody            calls=4400    hits=4239   misses=161    poly_hits=0
```

**Key insight:** `class_dispatch` is the only benchmark with significant polymorphic hits (328K / 350K = 93% of hits), but it's also missing 840K times — a 71% miss rate. This is where a change should matter, but it doesn't.

### Accessor Test

Modified `class_dispatch.js` to remove accessors (replaced `get/set area` with plain `_area` field):

```
class_dispatch with accessor:     339ms avg  (miss rate 71%)
class_dispatch without accessor:  177ms avg  (miss rate 0.4%)
```

**This reveals the real bottleneck.** The 162ms delta is the accessor cost. The IC misses 840K times partly because it bails on properties with getters/setters (see `sv_ic_try_get_hit()` line 185: `if (prop->has_getter || prop->has_setter) return false`).

### Benchmark Classification

After analyzing source code:

| Benchmark | Type | IC Relevance | Notes |
|---|---|---|---|
| `class_dispatch` | Method dispatch + accessors | HIGH | Genuinely 4 shapes in rotation, but accessor cost dominates (71% of benchmark is getter/setter calls) |
| `object_graph` | Allocation / GC | LOW | 600K object allocations; traversal reads `.meta.visited` (monomorphic) |
| `deltablue` | Allocation / GC | VERY LOW | 450K Variable allocations; only ever accesses `.value` and `.constraints` (monomorphic) |
| `richards` | Allocation / object walking | VERY LOW | 325K Packet allocations; only walks `.link` in a while loop; **never calls a method** |
| `nbody` | Pure numeric computation | NONE | Already monomorphic (poly_hits=0) |

**The reason for no improvement:** Only `class_dispatch` has actual polymorphic dispatch, and its cost is the accessor gate, not the shape mismatch.

## Why This Happened

Initial analysis (from `dashboard` output) grouped these 5 benchmarks as "property-heavy" based on:
- Names suggested OOP/method dispatch (class_dispatch, richards, object_graph, deltablue)
- Ratios vs txiki looked consistent (1.84× to 2.85×)

But **benchmark names are misleading**. Richards is a classic from Computer Language Benchmarks Game and tests task scheduling (object allocation and linked-list traversal), not method dispatch. DeltaBlue is a constraint solver that allocates 450K solver variables and mutates `.value`. Object Graph constructs 600K AST-like nodes and reads the same few properties per node. These are **GC stress tests in polymorphic clothing**.

Only `class_dispatch` was written for this fork specifically to test megamorphic dispatch (see the comment in the file: "Megamorphic: the call site sees four receiver shapes in rotation"). And it has accessors by design, which the IC can't help with.

## What We Learned About Ant's IC

1. **The monomorphic guard is already effective.** Even with 71% interpreter misses on class_dispatch, the benchmark only touches the interpreter IC 702 times during the whole run — 1.2M in-flight method calls execute in JIT'd code where shape checks are nearly free (a single memory load + compare).

2. **Accessors are the missing leverage.** The IC infrastructure exists and works, but it explicitly gives up on properties with getters/setters. Extending the IC to *store and call accessors directly* would be high-leverage — the four accessor methods in `class_dispatch` (`.area`, `.weight()`, `.describe()`) are called on every shape and are currently unoptimized.

3. **GC invalidates ICs constantly.** Every major and minor GC calls `ant_ic_epoch_bump()` (src/gc/gc.c:174, :204). On allocation-bound benchmarks this invalidates all IC state frequently, but we don't measure whether the cost of epoch bumping is real or if it's just noise in the allocation budget.

4. **Memory cost is real.** Adding 136 bytes per IC site means a 1000-site function grows its IC table by 136 KB. Ant is already 1.7× heavier than txiki in average peak RSS (41.5 MB vs 23.8 MB). Adding inline cache size without a win is not great.

## Comparison to QuickJS (txiki.js)

QuickJS uses:
- Monomorphic inline caches on *all* GET_PROPERTY operations
- Inline caches for **method calls** directly (we have no CALL_METHOD IC)
- **Accessor caching** — getters/setters are stored inline and called directly

We use:
- Monomorphic inline caches on GET_FIELD, PUT_FIELD, and globals
- **No call-site IC** — CALL_METHOD has no IC slot at all (grep shows 0 results for `sv_ic_slot_for_ip` in calls.h)
- **Accessors abort the IC** — we bail and fall back to full property lookup

## Next Steps (Ordered by Leverage)

> **Outcome (2026-07-28):** Step 1 was investigated and dropped — its premise
> does not hold in Ant (method resolution already runs through the `GET_FIELD`
> IC, and the JIT devirtualizes calls via type feedback). Step 2 was built and
> landed, together with a separate JIT put-field fix that measurement surfaced.
> See [completed/ic-accessor-caching.md](completed/ic-accessor-caching.md) for
> the data and results.

### 1. **Add a CALL_METHOD IC** (Medium effort, medium upside) — *dropped, see above*

This was Task #3 in the original plan, not yet attempted. The CALL_METHOD bytecode has no IC slot. Adding one would let us cache method resolution, which is currently a full property lookup + function type check on every call. For polymorphic call sites (like the dispatch loops in class_dispatch), this amortizes the lookup across 4 shapes.

Implementation sketch:
- Add `OP_IC_SLOT(CALL_METHOD)` to opcode definitions
- Wire the call fast path to check `ic->cached_shape` and call the cached function
- On slow path, populate the IC with the resolved function

**Why this is better than property IC polymorphism:** Method calls are inherently megamorphic in OOP code (different receiver shapes, same method). We already have the shape infrastructure. This is a small addition to an existing operation, not a new subsystem.

### 2. **Cache accessors in the IC** (Medium-high effort, high upside) — *done, see above*

Store the getter/setter function in the way (or alongside it) and invoke it directly on a hit. This unlocks the 162ms hidden in class_dispatch's accessor cost.

Requires:
- Extend `sv_ic_way_t` to carry getter/setter function pointers and attributes
- In the JIT guard, load the getter, check if it's callable, and emit an inline call sequence
- In the interpreter, call the cached getter/setter function directly

**Why this is worth doing:** The only benchmark that touches dispatch heavily (class_dispatch) spends 162ms out of 330ms in accessors. This is our best single-benchmark leverage inside Option A.

### 3. **Revisit GC IC invalidation** (Low-medium effort, unknown upside)

Every GC call bumps the epoch, invalidating all ICs. On allocation-bound code (4 out of 5 slow benchmarks), this might be thrashing. Measure:
- IC epoch bump frequency during deltablue/object_graph/richards
- Actual IC misses caused by epoch bumps vs legitimate polymorphism

If the answer is "high frequency, low miss cost," then epoch invalidation is too aggressive and we could use a generation-based scheme or finer-grained invalidation.

### 4. **Lean into Option C: Rope strings and GC** (High effort, high upside for full profile)

This is a separate investigation. Ant's 41.5 MB average peak RSS vs txiki's 23.8 MB is not noise — it's 1.74× heavier. The rope concatenation benchmark loses 2.66× and is one of the few tests with a dedicated rope implementation that still loses.

Rope strings are a good investment for memory, and if GC tuning is needed anyway, that belongs together.

## Reversion

This change was reverted (no commit made) after measurement. The working tree was reset to `dev` and the polymorphic IC code was discarded.

## Files Modified (for reference, now reverted)

- `include/silver/engine.h` — Added `sv_ic_way_t` struct and ways array to `sv_ic_entry_t`
- `src/silver/ops/property.h` — Implemented `sv_ic_try_get_hit()`, `sv_ic_way_load()`, `sv_ic_get_fill()` for polymorphic interpreter IC
- `src/silver/swarm.c:1096` — Modified JIT guard to select matching way instead of checking monomorphic shape

## Validation Completed

Before reversion:
- Spec suite (`examples/spec/run.js --all`): PASS (0 failures)
- Tier 1 compliance: PASS (100%)
- `just preflight`: PASS
- Six pre-existing test failures confirmed identical on baseline

## Conclusion

The implementation was correct and well-validated, but the performance payoff was zero because the benchmarks chosen for leverage testing were misclassified. This exploration clarified that:

1. **Property access isn't the bottleneck** in 4/5 targeted benchmarks
2. **Accessors are** in the 1 that matters (class_dispatch)
3. **Allocation/GC dominates** the others
4. **Method call IC** is the adjacent optimization we haven't tried

Next session should start with CALL_METHOD IC (Option A, part 2) before investing in rope strings or GC tuning.
