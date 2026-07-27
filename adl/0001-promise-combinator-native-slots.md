# 0001 — Promise combinator bookkeeping in native slots

- **Name:** promise-combinator-native-slots
- **Hash:** d159ab94ed135064f0eb3ac210da45ab5bdab9d5
- **Date:** 2026-07-27
- **Status:** accepted

## Context

`Promise.all` / `allSettled` / `any` tracked their per-element state on
JS-visible properties of internal objects. `src/ant.c` carried a standing
`TODO` above `promise_all_iter_cb` naming exactly this.

Per element the combinator did:

```c
js_setprop(js, resolve_obj, js_mkstr(js, "index", 5),   tov(index));
js_setprop(js, resolve_obj, js_mkstr(js, "tracker", 7), tracker);
js_setprop(js, reject_obj,  js_mkstr(js, "tracker", 7), tracker);
```

and re-allocated `js_mkstr(js, "remaining", 9)` on *every* settle.

`js_mkstr` always allocates — there is no interning on that path — and storing
a string key also copies it into the property table. Measured with temporary
counters in `js_mkstr`: **6 string allocations per element**, confirmed by
diffing allocation traces between N=10 and N=1010.

For `Promise.all` over 50,000 promises: 301,632 string allocations.

## Decision

Move all combinator bookkeeping to internal slots. Added to
`ANT_INTERNAL_SLOT_LIST` in `include/common.h`:

`SLOT_PCOMB_INDEX`, `SLOT_PCOMB_TRACKER`, `SLOT_PCOMB_RESULTS`,
`SLOT_PCOMB_REMAINING`, `SLOT_PCOMB_RESOLVED`.

These objects are never reachable from user JS, so this is behaviour
preserving. It is also *more* spec-correct: the anonymous built-in resolve /
reject functions from `PerformPromiseAll` should have no observable `index` or
`tracker` properties at all.

**Write barrier.** `js_setprop` emitted a generational write barrier;
`set_slot` does not. Reference-valued slots therefore use `set_slot_wb`
(tracker, results, errors). Number and boolean slots use plain `set_slot`.
Getting this wrong is a use-after-free under minor GC, not a perf bug — the
tracker is reachable only through these slots.

Slots are traced by the GC at `src/gc/objects.c:381-384`
(`ant_object_extra_slots` → `gc_mark_value`), so no marking change was needed.

## Measurement

Linux x86_64, `meson compile -C build` release, best-of-5.
Benchmark: `Promise.all` over 50,000 resolved promises.

| | strings allocated | time | peak RSS |
|---|---|---|---|
| baseline | 301,632 | 0.14 s | 85.3 MB |
| after | 1,627 | 0.10 s | 75.5 MB |

Combined with 0002, on `js-bench/benchmarks/async.js`:
0.15 s / 115.2 MB → 0.12 s / 109.1 MB. That measurement was taken on a tree
that also carried an activation-VM sizing experiment, since dropped — upstream
#62 replaced per-await activation VMs with heap `sv_activation_t` snapshots — so
some of the gain is not attributable to this change.

Compliance: spec suite 3672/3672. Test262 tier 3 **32842/53434 both before and
after** (identical pass count). Tier 1 53/53.

## Options considered

**Keep properties, intern the key strings.** Would cut the allocation but keep
shape transitions and property-table storage, and would leave the properties
observable. Rejected: strictly worse than slots on both counts.

**Pack index+remaining into one slot as a bitfield.** Saves one slot per
handler object. Not measured; the remaining per-element cost is dominated by
whole objects, not slots. Only worth revisiting if handler objects themselves
are eliminated.

**Eliminate the derived promise from the internal `then`.** `Promise.all` calls
`builtin_promise_then` and discards the returned promise — one wasted
`ant_object_t` (152 B) plus `ant_promise_state_t` (88 B) per element. *Not
done*, because `then` performs a SpeciesConstructor lookup that is observable
when `Promise` is subclassed, and the derived promise's creation is observable
through a subclass executor. Doing this safely requires a "pristine Promise"
guard (constructor untouched, `Symbol.species` untouched, prototype intact)
with correct invalidation — note that value-overwrite without a shape change
means a shape-version guard alone is insufficient. Worth roughly 240 B/element;
revisit if the promise combinators are
revisited.

## Consequences

- Five new internal slots. The enum is `SLOT_MAX = 255`; ample headroom.
- Any future combinator work must use `set_slot_wb` for reference values.
- `Promise.any` now stores its errors array in `SLOT_PCOMB_RESULTS` (shared
  slot id with `all`'s results) — same role, different combinator, never both.
