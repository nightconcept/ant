# 0002 — Iterator result objects use interned keys

- **Name:** iterator-result-interned-keys
- **Hash:** d159ab94ed135064f0eb3ac210da45ab5bdab9d5
- **Date:** 2026-07-27
- **Status:** accepted

## Context

Every iterator step allocates a fresh `{value, done}` result object — required
by spec, since the result is user-observable. `js_iter_result` in
`include/modules/symbol.h` built it with:

```c
js_set(js, result, "done",  js_false);
js_set(js, result, "value", value);
```

`js_set` takes a `const char *` and, when adding a property that does not yet
exist, allocates a JS string for the key. So each iteration step allocated two
key strings on top of the result object itself.

Found by diffing `js_mkstr` traces between N=10 and N=1010 elements of a
`Promise.all`: the only per-element strings left after 0001 were exactly
`"value"` and `"done"`, one each. Average string length 4.5 bytes = (5+4)/2,
confirming the attribution.

This is not promise-specific — it is on the path of every `for...of`, spread,
destructuring, and `Array.from` over an iterator.

## Decision

Use the already-existing intern cache. `ant_t` carries `js->intern.done` and
`js->intern.value` (populated in `js_init_intern_cache`, `src/ant.c:3233`), and
`mkprop_interned` (declared in `include/internal.h`) takes a pre-interned key.

```c
mkprop_interned(js, result, js->intern.done,  js_false, 0);
mkprop_interned(js, result, js->intern.value, value,    0);
```

Zero allocation, and no hashing either — `js_mkprop_fast` would still intern
(hash) the literal on every call; using the cached pointer skips that too.

Two invariants deliberately preserved:

- **Key order stays done-then-value.** It is observable via `Object.keys` on
  the result object. Changing it to match V8's `{value, done}` would be a
  compliance risk for no gain.
- **No write barrier needed.** `result` is freshly allocated and therefore in
  the nursery; the barrier only matters for old→young stores.

## Measurement

Linux x86_64, release, best-of-5.

Per-element string allocations in the `Promise.all` path went from 2 to 0.
Across N=50,000, total strings for the combined 0001+0002 change:
301,632 → 1,627 (the remainder is process startup).

Contribution is folded into the 0001 numbers — the two changes were measured
together on the same build:

| | time | peak RSS |
|---|---|---|
| baseline | 0.14 s | 85.3 MB |
| after 0001+0002 | 0.10 s | 75.5 MB |

Compliance: the legacy spec-suite aggregate was 3672/3672 (98 files). Test262 had an identical pass
count to baseline, 32842/53434.

## Options considered

**Cache a singleton result object and mutate it.** Illegal — the result object
escapes to user code and must be a fresh object per step.

**Pre-build a shape for `{done, value}` and stamp it.** Would skip two property
additions entirely, not just the key allocation. Larger change touching the
shape system; not attempted. This is the natural next step if iterator-heavy
workloads stay hot — the result object itself (152 B) is now the dominant
per-step cost, not the keys.

**Extend the intern cache with more literals.** `js->intern` already holds
`length`, `prototype`, `constructor`, `name`, `message`, `get`, `set`,
`arguments`, `callee`, and `idx[0..9]`. Any `js_set`/`js_get` with a hot string
literal is a candidate for the same treatment. A trace with the temporary
`ANT_STRTRACE` counter (see 0001) will find them.

## Consequences

- `include/modules/symbol.h` now depends on `mkprop_interned` from
  `internal.h` and on the `js->intern` cache being initialised. Both are set up
  before any iterator can run.
- Benefit is global, not confined to promises: all iteration protocols.
