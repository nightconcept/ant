# Technical Debt Tracker

Status: active
Last reviewed: 2026-05-16
Owner: theMackabu

Use this file to record debt that is important enough to preserve but not yet
scheduled.

## Format

- Area:
- Issue:
- Impact:
- Proposed fix:
- Owner:
- Status:

## Open Items

- Area: `src/sandbox/backends/darwin.c` / macOS HVF VMM interrupts
  - Issue: The Darwin Hypervisor.framework backend currently continues when `hv_gic_config_set_msi_interrupt_range()` fails, and device bringup still includes legacy/polling/manual wake paths instead of a fully interrupt-driven virtio PCI model.
  - Impact: This is acceptable for sandbox bringup, but it leaves the backend less representative of the final VMM contract. Future virtio devices, networking, and lower-latency I/O may rely on proper MSI/MSI-X delivery instead of polling or legacy compatibility paths.
  - Proposed fix: Implement proper GIC MSI/MSI-X wiring for PCI virtio devices on Apple Silicon HVF, make block/net/vsock/9p completions use real device interrupts, then remove the legacy/polling/manual-wake bringup paths and any fallback code that only exists because MSI is missing.
  - Status: backlog

- Area: `src/modules/storage.c` / global `localStorage`
  - Issue: `JSON.stringify(globalThis)` can throw when it reaches the global `localStorage` property and no `--localstorage-file` or `localStorage.setFile()` path has been configured. Repro: `console.log(JSON.stringify(this));` currently reports `TypeError: Warning: --localstorage-file or localStorage.setFile were not provided with valid paths.`
  - Impact: Object inspection and serialization of broad global objects can fail because a host API accessor performs configuration validation too early. This is surprising behavior and unrelated code can trip over localStorage simply by enumerating or stringifying globals.
  - Proposed fix: Make the global `localStorage` property safe to read when unconfigured, either by returning an inert/lazy storage object that throws only when storage operations are used, or by omitting/marking the property so generic stringify/inspection does not invoke a throwing accessor.
  - Status: backlog

- Area: Silver closure allocation / function-object initialization
  - Issue: `sv_init_closure_function_object()` assigns `closure->func_obj` before proving that the backing function object and its required metadata were initialized successfully. Allocation failures in `mkobj()`, `.length` setup, or prototype setup can therefore leave a closure with an error or partially initialized `func_obj`.
  - Impact: This is an OOM-hardening issue rather than a normal JS-level repro; it likely needs allocator fault injection or a real process memory cap to observe reliably. If it does happen, the interpreter or JIT can expose a callable with invalid/incomplete function-object state.
  - Proposed fix: Make `sv_init_closure_function_object()` return a status value, assign `closure->func_obj` only after `mkobj()` succeeds, propagate failures from length/prototype setup, and have `sv_op_closure()` / `jit_helper_closure()` return the error instead of publishing `func_val`. Avoid fixing this by forcing generic bailout for `OP_CLOSURE`; that would risk large JIT/Newt regressions.
  - Status: backlog

- Area: `src/modules/readline.c`
  - Issue: Rendering assumes readline owns the full visible prompt line, so redraws are anchored to the logical prompt text instead of the terminal position where editing actually begins.
  - Impact: Full redraw paths can clobber externally rendered prefixes, boxed prompts, or other same-line UI written before `question()` or `prompt()` starts editing.
  - Proposed fix: Track an explicit render origin / prompt anchor, separate logical prompt text from the screen position where input begins, and make redraws preserve external prefixes and custom prompt chrome.
  - Status: open

- Area: `src/modules/process.c` / `src/modules/tty.c`
  - Issue: Stdio TTY stream setup still has split ownership. `process.c` creates `process.stdout` / `process.stderr`, installs stdout `rows` / `columns`, and keeps its own terminal sizing helper; `tty.c` later reshapes the same streams, reinstalls `rows` / `columns`, and keeps a separate terminal sizing helper. The stale SIGWINCH setter path has already been removed, but the duplicated ownership that allowed it to drift remains.
  - Impact: Future stdio or TTY changes can diverge between the process bootstrap path and the TTY module path, especially around descriptor shape, `getWindowSize()`, resize behavior, and platform-specific terminal sizing.
  - Proposed fix: Make `tty.c` the single owner of TTY stream shape and terminal sizing for stdout/stderr, leaving `process.c` to create or expose process streams and wire process-specific event-emitter behavior. Share one sizing helper or module-level API so `rows`, `columns`, and `getWindowSize()` all use the same implementation.
  - Status: backlog

- Area: Node-style stream duck typing
  - Issue: `src/modules/stream.c` still probes and calls arbitrary stream-like properties such as `.write`, `.end`, `.pause`, `.resume`, `.pipe`, `.read`, `.next`, `_read`, `_write`, `_transform`, and `.getReader`. Related ad-hoc stream/event probes also appear in `src/modules/fs.c` (`.destroy` / `.end`), `src/modules/zlib.c` (`.write` / `.end`), and `src/modules/child_process.c` (`.once`). Lower-confidence event-handler cases in `src/modules/worker_threads.c` (`.onmessage`) and `src/modules/abort.c` (`.onabort`) should be checked for consistent non-callable handling, but should not be treated as bugs without a concrete repro because handler properties are normal platform-style APIs.
  - Impact: Each call site currently decides for itself which missing or non-callable methods are ignored, treated as compatibility no-ops, or allowed to fail later. That makes Node-stream compatibility behavior harder to reason about and can hide inconsistent errors across modules.
  - Proposed fix: Start with `src/modules/stream.c`: add small helper gates such as `stream_get_callable_prop()`, `stream_is_node_writable_like()`, and `stream_is_reader_like()`, then make required-method errors and optional-method no-ops consistent. After that, route the `fs.c`, `zlib.c`, and `child_process.c` stream/event probes through shared helpers. Finally, audit `worker_threads.c` and `abort.c` only for consistent ignore-vs-call behavior on non-callable handler properties.
  - Status: backlog

- Area: Silver compiler
  - Issue: `sv_compiler_t` scratch storage is still allocated per compilation, so repeated compiles in a long-lived process pay allocator churn for locals, bytecode buffers, constants, atoms, upvalue descriptors, loops, srcpos data, and maybe slot-type scratch.
  - Impact: One-shot CLI compiles are fine, but a REPL, watch mode, embedder, or other long-lived process cannot yet recycle compiler scratch space across compiles.
  - Proposed fix: Add a real `compile_pool` scratch allocator after the `compile_ctx` extraction. Pool the resizable arrays for `locals`, `local_lookup_heads`, `code`, `constants`, `atoms`, `upval_descs`, `loops`, `srcpos`, and potentially `slot_types`. Keep `line_table` separate or make it poolable scratch, since it is derived from the current source buffer rather than a semantic cache.
  - Status: backlog

- Area: Shared helper utilities
  - Issue: Small helper logic such as ASCII character classification, casing, and similar utility code is duplicated across multiple runtime and support modules with local one-off implementations.
  - Impact: Repeated copies drift over time, make bug fixes harder to apply consistently, and add noise when adding or reviewing new modules.
  - Proposed fix: Audit duplicated helper patterns across `src/` and `include/`, identify the stable cross-cutting utilities, and centralize them in a small shared header or utility module with repo-wide call sites migrated incrementally.
  - Status: backlog

- Area: `src/modules/intl.c`
  - Issue: `Intl` is now present and passes the current compat-table target, but several behaviors are still simplified compatibility implementations rather than fuller ECMA-402 semantics.
  - Impact: `Intl.Collator`, `Intl.NumberFormat`, `Intl.DateTimeFormat`, and `Intl.Segmenter` can still diverge from web or Node behavior for anything beyond the currently covered compat surface.
  - Proposed fix: Continue expanding `Intl` incrementally: replace `strcoll`-only collation, deepen `resolvedOptions()`, make `DateTimeFormat` actually honor stored timezone and locale options, and move `Segmenter` closer to the expected iterable/result object shape.
  - Status: backlog

- Area: `src/modules/timer.c`
  - Issue: `node:timers/promises setInterval()` is still explicitly unimplemented.
  - Impact: Promise-based timer APIs remain incomplete and can block compatibility with code that expects the Node timers/promises interval surface.
  - Proposed fix: Implement `setInterval()` on top of the existing timer promise scheduling machinery, including cancellation and signal handling behavior consistent with the existing `setTimeout()` and `setImmediate()` support.
  - Status: backlog

- Area: `src/modules/dns.c`
  - Issue: `node:dns` is still a minimal shim centered on `dns.promises.lookup`.
  - Impact: Tooling or apps that expect more of the Node DNS surface still need polyfills or will fail outright.
  - Proposed fix: Expand the module incrementally from the existing lookup path, prioritizing the most commonly used sync, callback, and `promises` APIs needed by current ecosystem packages.
  - Status: backlog

- Area: `src/modules/crypto.c`
  - Issue: `crypto.subtle` is only partially implemented and still marked for extension beyond the current digest-oriented support.
  - Impact: Web Crypto compatibility is incomplete, which blocks packages and runtime features that expect a broader `SubtleCrypto` surface.
  - Proposed fix: Extend `crypto.subtle` method coverage incrementally, starting with the highest-value operations after digest and preserving the existing algorithm parsing entrypoints.
  - Status: backlog

- Area: `src/modules/worker_threads.c`
  - Issue: `node:worker_threads` is still a minimal compatibility implementation, and `Worker.postMessage` remains explicitly unimplemented.
  - Impact: Build tools and libraries that rely on real worker thread messaging or broader worker lifecycle behavior still cannot use the native surface directly.
  - Proposed fix: Expand worker thread support incrementally, starting with message passing and the most commonly used worker APIs, while preserving the existing lightweight process-backed architecture where practical.
  - Status: backlog

- Area: `src/modules/async_hooks.c`
  - Issue: `node:async_hooks` is still a minimal compatibility layer intended mainly to satisfy framework expectations.
  - Impact: Async context tracking semantics remain shallow, which can break libraries that rely on realistic async IDs, resources, or hook lifecycle behavior.
  - Proposed fix: Replace the placeholder async ID and resource behavior with real runtime-backed tracking, while keeping `AsyncLocalStorage` compatibility stable during the transition.
  - Status: backlog

- Area: Native cfunc ABI / iterator `next()` trampolines
  - Issue: The lightweight native-function ABI (`ant_cfunc_t`, registered via `js_mkfun` with a static `ant_cfunc_meta_t`) has no per-registration data channel — no userdata pointer and no QuickJS-style `magic` int. Any family of native callbacks that share logic but differ by one parameter therefore needs a named trampoline per variant. Current example: the six `*_iter_next` wrappers (array, string, map, set, typed array, headers) that each just call `js_iter_next_result(js, advance_*)`. That helper was introduced by PR #40 (issue #39) to fix unspecified-evaluation-order reads of an uninitialized `ant_value_t` in the old `js_iter_result(js, advance_*(js, &it, &value), value)` pattern, which GCC on Linux miscompiled (stale `value` read before the advance call) while Apple clang happened to evaluate in the safe order.
  - Impact: Source-level boilerplate only. The trampolines are zero runtime cost: `js_iter_next_result` is `static inline` and the advance function is a compile-time constant at each call site, so calls are devirtualized and inlined, and each wrapper keeps a distinct symbol in profiles and stack traces. Alternatives considered and rejected: `js_heavy_mkfun_native()` binding the advance pointer to one generic callback (adds a slot load plus an indirect call on the hot iterator path, allocates a heavier function object, requires a function-pointer-through-`void *` cast, and collapses profiler frames); macro-generated wrappers (pure taste, less greppable).
  - Proposed fix: Only if per-function registration data is wanted in several more places, add a QuickJS-style `magic` int to `ant_cfunc_meta_t` and pass it through to callbacks, letting one generic `iter_next` dispatch through a static advance table with no runtime pointer chasing. This is an engine-wide ABI change — every builtin signature, the call dispatcher, and the JIT native-call convention — so it must not be done just to delete the six iterator trampolines.
  - Owner: theMackabu
  - Status: backlog (deliberately deferred; revisit only alongside a broader cfunc ABI change)

- Area: Generational GC / open upvalues into suspended coroutine stacks
  - Issue: The closed-upvalue write barrier (`gc_upvalue_write_barrier`) covers closed cells only. An OPEN upvalue whose `location` was relocated into a materialized coroutine's heap-allocated VM stack (`sv_async_move_open_upvalues`) is not covered: if the owning generator/async object is promoted to old, minor GC scans neither the object (old objects are not traversed) nor the suspended VM stack (only `pending_coroutines` and mco stacks are scanned), so a young value written through such a cell between suspension and resumption is invisible to minor GC and can be freed while reachable.
  - Impact: Use-after-free requiring a specific interleaving: closure escapes a generator, generator suspends and is promoted, escaped closure writes a fresh heap value through the still-open relocated cell, minor GC runs before resumption. Pre-existing (predates the closed-cell barrier); no known in-the-wild repro.
  - Proposed fix: A per-isolate registry of live materialized VMs (`sv_vm_create(SV_VM_ASYNC)` / `sv_vm_destroy`), with minor GC scanning suspended VM stacks the way it scans `pending_coroutines`. Barrier-side alternatives are unsafe: remembering open cells and marking `*location` reads freed memory if the target VM is destroyed before the next GC (`sv_vm_destroy` does not close upvalues pointing into its stack).
  - Owner: theMackabu
  - Status: backlog

- Area: `src/streams/readable.c`
  - Issue: `ReadableStreamBYOBReader` is still explicitly unimplemented, and byte-source support is still called out as incomplete.
  - Impact: Web Streams byte-oriented consumers cannot rely on BYOB reader semantics, leaving an important platform feature gap for stream-heavy or browser-compatible code.
  - Proposed fix: Add real byte-source plumbing and implement `ReadableStreamBYOBReader` on top of it instead of routing byte sources through the default reader path.
  - Status: backlog

- Area: Dense array index writes bypass property attributes
  - Issue: The dense branch of `js_setprop_array_fast` (`src/ant.c`) stores straight into the element buffer whenever the index is inside the dense length, without consulting the property's attributes. `Object.freeze` and `Object.defineProperty` on an array index neither de-densify the array nor clear a flag, so a frozen array accepts writes, a non-writable index is overwritten, an accessor defined on an index is clobbered by the raw value, and a prototype setter for an unset index is shadowed by a new own data property. Node disagrees on all four. The VM-level fast path added alongside the typed-array work (`js_arr_try_fast_set`) deliberately routes exotic, frozen and non-extensible arrays to this same slow path, so it neither fixes nor widens the gap.
  - Impact: Four spec deviations on ordinary arrays, silently producing wrong values rather than throwing. Not currently visible in tier 2/3 numbers.
  - Proposed fix: Give the object a "plain elements" bit (the existing `flags.fast_array` is only set at allocation and growth, so it can be repurposed or joined by a sibling) and clear it in `Object.freeze`/`seal`/`preventExtensions` and in `defineProperty` when the key is an array index and the descriptor is not a plain writable/enumerable/configurable data descriptor. Both the dense branch and `js_arr_try_fast_set` then gate on that bit and de-opt to the general path once an array stops being plain.
  - Status: backlog

- Area: Typed array writes silently swallow a throwing coercion
  - Issue: `typedarray_write_value` (`src/modules/buffer.c`) converts through `js_to_number`, which returns a raw `double` and has no error channel. When `ToNumber` runs a user `valueOf` that throws, the store still happens (writing NaN) and the exception escapes the surrounding `try`/`catch`, surfacing later as an uncaught error. Node throws at the assignment. The BigInt64/BigUint64 cases are unaffected because they go through `buffer_require_bigint_value`, which does return an error value.
  - Impact: A throwing coercion during a typed-array element write is not catchable at the write site and corrupts the element. Pre-existing; unchanged by the integer-indexed fast path, which already propagates whatever `typedarray_write_value` returns.
  - Proposed fix: Give `js_to_number` an error channel (an out-parameter, or an `ant_value_t` returning sibling used on paths that can observe user code) and have `typedarray_write_value` return the error instead of storing. This touches every `js_to_number` caller, so it belongs with a broader coercion-API change rather than a local patch.
  - Status: backlog

- Area: Typed array integer indices are invisible to key enumeration and `has`
  - Issue: Element slots of an integer-indexed exotic object are own properties, but they live only in the backing store. `Object.getOwnPropertyDescriptor` now reports them (`builtin_object_getOwnPropertyDescriptor`), while `Object.keys` and `Reflect.has` do not: `Object.keys(new Float64Array(4))` returns the instance metadata names (`length`, `byteLength`, `byteOffset`, `BYTES_PER_ELEMENT`, `buffer`) instead of `["0","1","2","3"]`, and `Reflect.has(ta, "0")` is false. The metadata names should not be own enumerable properties of the instance at all.
  - Impact: Enumeration, spread, and `in` over typed arrays disagree with the spec. Not covered by the tests that the integer-indexed element work fixed.
  - Proposed fix: Give the typed-array object an `exotic_keys` implementation that yields the element indices, move the metadata names onto the prototype as accessors, and route `[[HasProperty]]` through the same canonical-index check that `buffer_typedarray_index_key` already provides.
  - Status: backlog

- Area: Non-canonical numeric string keys on typed arrays
  - Issue: `buffer_typedarray_index_key` recognises only the array-index form (digits, no leading zero). Other canonical numeric strings reaching the exotic getter/setter as string keys — `"-1"`, `"1.5"`, `"1e21"` — are still treated as ordinary property keys, so `ta["1.5"] = 7` defines a real property instead of being discarded. The numeric-key paths (`ta[1.5]`) and `defineProperty` are correct, the latter via `buffer_is_canonical_numeric_key`.
  - Impact: A narrow residual deviation: only string-literal non-index numeric keys, which are rare in practice.
  - Proposed fix: Route the exotic getter/setter through `buffer_is_canonical_numeric_key` the way `builtin_object_defineProperty` does, returning undefined / discarding the write when the key is canonical numeric but not a valid index.
  - Status: backlog

- Area: `String.prototype.replace` over deeply chained rope results
  - Issue: A chain of global `replace` calls, each applied to the result of the previous one, starts dropping characters and then throws `TypeError: oom`. Repro (`bench/benchmarks/regex_dna.js` is the workload it was found in): build a sequence from `["agctntkbmrswyvhdAGCTNTKBMRSWYVHD", "GGCC", "AAAA", "TTTT", "CCCC"]` joined with newlines, strip it with `.replace(/^>.*$/mg, "").replace(/\n/g, "")`, run the nine IUPAC `match` variants, then apply the eleven `[/B/g, "(c|g|t)"] ...` replacements in sequence. At 50000 sequence entries this is correct; at 70000 Ant returns 2127233 where node/txiki.js/deno/bun all return 2128000, and stderr carries an `oom` TypeError. It is not a plain size limit or a plain leak: the same eleven replacements over a 50000-entry string built without the newline/`match` phases run five times over with no divergence, and the failing string is under 1MB.
  - Impact: Silent wrong answers before the throw, which is worse than the throw. Any code doing repeated global replaces over a growing string can hit it. It is why `regex_dna` is pinned at one round of 50000 rather than sized like the rest of the suite, so that benchmark currently under-measures the regex engine.
  - Proposed fix: Find where the rope produced by `replace` loses length under nesting — most likely flattening or the length bookkeeping on the concatenation path in `src/gc/` — and add a regression test under `tests/` built from the repro above.
  - Status: backlog

- Area: RegExp instance properties are own data properties, not prototype accessors
  - Issue: `source`, `flags`, `hasIndices`, `global`, `ignoreCase`, `multiline`, `dotAll`, `unicode`, `unicodeSets` and `sticky` are created as own data properties on every RegExp instance, by the constructor (`regexp_init_flags` in `src/modules/regex.c`) and independently by the literal path (`sv_op_regexp` in `src/silver/ops/literals.h`). The spec puts all of them on `RegExp.prototype` as non-enumerable accessors, with only `lastIndex` as an own data property. Their attributes are now correct — nothing on an instance is enumerable, so `Object.keys`, spread, `JSON.stringify` and `Object.create`'s Properties argument all agree with Node — but the *location* still deviates: `Object.getOwnPropertyNames(/x/g)` lists eleven names where the spec says one, `hasOwnProperty("global")` is true where it should be false, and deleting or shadowing a flag on an instance behaves unlike the accessor it should be.
  - Impact: Own-property introspection over RegExp instances disagrees with the spec. `Object.keys` and enumeration are correct, so the common paths are unaffected; this is visible to code that reflects over instances. Also a duplication hazard — the two construction paths must be kept in sync by hand, and the enumerability fix had to be applied to each separately after the constructor-only fix left literals wrong.
  - Proposed fix: Move the ten flag properties to `RegExp.prototype` as getters backed by `SLOT_REGEXP_FLAGS_MASK`, which both construction paths already populate, and leave `lastIndex` as the sole own property. The blocker is that the engine reads these by name on hot paths (`js_getprop_fallback(js, rx, "sticky")`, `lkp(js, regexp, "source", 6)` and friends throughout `src/modules/regex.c`); those call sites should read the mask slot directly before the properties move, which is worth doing on its own.
  - Status: backlog
