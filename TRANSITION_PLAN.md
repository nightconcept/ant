# Ant Fork & Simplification Transition Plan

Status: active
Last reviewed: 2026-07-25
Owner: User & Antigravity

This execution plan outlines the step-by-step roadmap to fork and simplify **Ant**, transition the developer toolchain from Nix to **Mise**, make the engine compile under the custom `../mc` compiler (TinyCC) for dogfooding — removing the C++ dependency and fixing constructs TinyCC rejects, while keeping the GNU/C11 extensions it accepts — align the custom `../mir` engine, and streamline the build system.

---

## Architecture & Simplification Notes

### Keeping the Zig Package Manager (`src/pkg`)
Keeping `src/pkg/` significantly simplifies the initial fork transition:
* **No CLI Refactoring**: CLI commands in [`src/main.c`](file:///Users/danny/git/ant/src/main.c) (`init`, `install`, `add`, `publish`, `run`, `exec`, etc.) and [`cli/pkg.h`](file:///Users/danny/git/ant/include/cli/pkg.h) remain fully functional without needing `ANT_NO_PKG` macros or stubbing.
* **Full Package Compatibility**: Native npm/Ant package management and lockfile resolution continue working out of the box.

---

## Sequential Implementation Roadmap

```
┌────────────────────────────────────────────────────────┐
│ Phase 1: Nix to Mise Environment Migration (ACTIVE)   │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 2: Compile Engine Under ../mc (Empirical TinyCC)  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 3: MIR Engine Alignment (nightconcept/mir)       │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 4: Build System & Dogfooding (`../mc` Compiler)  │
└────────────────────────────────────────────────────────┘
```

---

### Phase 1: Nix to Mise Migration (Primary Focus)

1. **Remove Nix Infrastructure**:
   * Delete [`flake.nix`](file:///Users/danny/git/ant/flake.nix) and [`flake.lock`](file:///Users/danny/git/ant/flake.lock).
   * Delete [`packages/nix/`](file:///Users/danny/git/ant/packages/nix/) directory.
   * Delete [`.github/workflows/nix-cache.yml`](file:///Users/danny/git/ant/.github/workflows/nix-cache.yml).

2. **Clean Nix References from Scripts**:
   * In [`maidfile.toml`](file:///Users/danny/git/ant/maidfile.toml), replace `[tasks.shell]` (`nix develop --command zsh`) with standard shell execution or `mise` invocation.
   * In [`meson/pgo/build.sh`](file:///Users/danny/git/ant/meson/pgo/build.sh), remove mandatory `nix develop` checks and `ANT_PGO_IN_NIX_SHELL` environment wrappers.

3. **Create Root `mise.toml` Configuration**:
   * Configure environment tool pins: Node.js `22`, Python `3.12`, Zig `0.16.0`, Meson, Ninja, CMake.
   * Map developer tasks (`mise run setup`, `mise run build`, `mise run test`, `mise run dev`, `mise run preflight`, `mise run install`).

4. **Update Documentation**:
   * Update [`BUILDING.md`](file:///Users/danny/git/ant/BUILDING.md) and [`README.md`](file:///Users/danny/git/ant/README.md) to replace Nix environment setup instructions with `mise` setup instructions.

---

### Phase 2: Compile the Engine Under `../mc` (Empirical TinyCC Targeting)

**Goal:** The Ant engine compiles under `../mc` (TinyCC 0.9.28rc) and passes the
spec suite. Keep every extension TinyCC accepts; fix **only** the constructs it
actually rejects or mishandles.

**Framing note (2026-07-25):** The dogfooding target `../mc` is TinyCC, not a
strict ISO C99 compiler. Empirical smoke tests against `../mc/build/mc` show it
**accepts** the constructs the original plan wanted to strip — computed goto
(`goto *`), statement expressions `({ ... })`, `typeof`, anonymous
unions/structs, `_Static_assert`, `_Alignof`, C11 `_Atomic`/`<stdatomic.h>`,
`__builtin_expect`, `__builtin_clz`. Removing these would be pointless make-work
and would regress interpreter performance (the bytecode VM dispatch in
[`src/silver/engine.c`](file:///Users/danny/git/ant/src/silver/engine.c) relies
on computed goto). We therefore target TinyCC empirically instead of stripping to
pure C99.

Tests show TinyCC **rejects or mishandles** only: C++ (`numbers.cc`),
`__attribute__((packed))` (silently ignored — layout wrong), `__builtin_ia32_pause`
(unresolved reference), and `_Thread_local` with a non-zero initializer (reads
back 0).

**Progress note (2026-07-25):** Items 0–6 are all done — Phase 2 complete. Item 1
(`numbers.cc` -> `numbers.c`) was finished by transliterating the double-only
subset of the vendored C++ **double-conversion** library into a single pure-C
`src/numbers.c` (~3060 lines) rather than porting Ryu/Grisu3 fresh — the
transliteration preserves double-conversion's exact ECMAScript tie-breaking by
construction. Conformance was proven by a byte-for-byte differential against Node
(the same double-conversion algorithm V8 uses): a fixed tricky-value grid, a
20,000 random-double grid (240k output lines), and a parse grid all match
identically; the spec suite stays 98/0 and `scripts/mc-check.sh` now reports
**170/170** engine TUs compiling under `../mc` (numbers.c included).

One transliteration bug was found and fixed during integration: the four stack
`Bignum`s in `bignum_dtoa` were uninitialized (C has no default ctor like C++), so
the FIXED/PRECISION paths read garbage `delta_plus`/`delta_minus` and tripped the
`is_clamped` assertion — fixed by zeroing them (`src/numbers.c`, `bignum_dtoa`).

**Discovered during Item 1:** `numbers.cc` was *not* the only C++ in the aggregate
build — the vendored `ada` (URL parser) and `wasm-micro-runtime` subprojects are
also C++ and remain linked into `ant`. The top-level `project()` was still flipped
to `['c']` (and `cpp_std` dropped): Meson auto-detects C++ for those subprojects
and links libstdc++ for the final binary regardless, so the ant-owned engine is now
C-only while ada/wamr stay C++ (removing/porting those is out of Item 1 scope).

The full-tree triage (Item 6) surfaced TinyCC gaps beyond the ones found in the
initial smoke test, all fixed:
* `__has_include(x)` is recognized directly after `#if`/`#elif` but not when
  reached through another macro's expansion — broke yyjson's
  `yyjson_has_include(x)` wrapper on every TU that includes `yyjson.h`. Fixed by
  passing `-Dyyjson_has_include(x)=0` in `scripts/mc-check.sh` (yyjson is
  vendored/gitignored, so this is a compiler-invocation-level fix, not a vendor
  patch).
* TinyCC does not define `__GNUC__` (it self-identifies via `__TINYC__`).
  Vendor code gated on `defined(__GNUC__)` — c-ares' `ares_build.h`,
  wasm-micro-runtime's `ALIGNED_(x)` macro — fell through to `#error`/broken
  branches. **Do not** globally `-D__GNUC__=N` to paper over this: it breaks
  glibc's `features.h`, which gates its own compiler-support branches on the
  real `__GNUC__` (confirmed by testing — regressed the pass count from 163 to
  ~140). Fixed per-vendor instead, via tracked patches wired through each
  wrap's `diff_files`: `vendor/packagefiles/patches/c-ares-tinycc.patch` and
  `vendor/packagefiles/patches/wasm-micro-runtime-tinycc.patch`, both adding
  `|| defined(__TINYC__)` next to the `__GNUC__` check.
* TinyCC's bundled `<stddef.h>` predates C11 and has no `max_align_t`; its
  `<stdatomic.h>` has no `ATOMIC_*_LOCK_FREE` macros. Both fixed with small
  `#if defined(__TINYC__)` fallback shims local to `src/pool.c` and
  `src/modules/atomics.c`.
* `include/arena.h` and `include/types.h` used `bool` without including
  `<stdbool.h>`, relying on gcc's C23 (`gnu2x`/`gnu23`) implicit `bool` keyword.
  TinyCC doesn't implement that C23 keyword promotion, so this broke any TU
  that hit these headers before something else pulled in `<stdbool.h>`
  (`src/modules/v8.c`, `src/modules/sandbox.c`). Fixed by adding the explicit
  `#include <stdbool.h>` — this is a real portability bug, not TinyCC-specific,
  and is safe under the primary gcc/meson build too.

#### Item 0 — `../mc` compile harness (prerequisite) — DONE
* Script (`scripts/mc-check.sh`) runs `../mc/build/mc build -c` on each engine
  translation unit, deriving real per-TU include/define flags from Meson's
  `compile_commands.json` (`meson setup build` first) rather than guessing
  `-I` paths — this also covers vendored dependency headers.
* Reuse the generated headers meson already emits into `build/`
  (`messages.h`, `theme.h`, `meson/builtins/builtin_bundle_data.h`,
  `meson/snapshot/snapshot_data.h` — note the actual custom_target output
  names differ from the plan's original guess); do **not** wait on the Phase 4
  gen-driver. Generate them directly with
  `ninja -C build messages.h theme.h meson/builtins/builtin_bundle_data.h meson/snapshot/snapshot_data.h`.
* Produces the per-file pass/fail matrix that drove Item 6: currently
  **169/169 engine TUs pass** (excludes `src/main.c` and the still-C++
  `src/numbers.cc`, per plan scope).

#### Item 1 — `src/numbers.cc` -> `src/numbers.c` — DONE
* Was the only `.cc` in the tree; TinyCC has **no C++**. It wrapped the C++
  **double-conversion** library for ECMAScript-correct number formatting/parsing.
* Chose a **mechanical transliteration** of double-conversion's double-only paths
  (ieee/diy-fp/cached-powers/fast-dtoa/fixed-dtoa/bignum/bignum-dtoa/
  double-to-string/strtod/string-to-double) into one self-contained
  [`src/numbers.c`](file:///Users/danny/git/ant/src/numbers.c) over a fresh
  Ryu/Grisu3 port — this preserves the exact ECMAScript tie-breaking (round-half-
  up-to-larger) that `snprintf`/Ryu do **not** reproduce, by keeping the reference
  algorithm the tests were validated against. Single-precision `float` paths and
  the EcmaScriptConverter's configurability were dropped (config hardcoded:
  `UNIQUE_ZERO|EMIT_POSITIVE_EXPONENT_SIGN`, low=-6/high=21, prec padding 6/0). The
  JS-wrapper layer (whitespace-trim table, hex/bin/oct prefix parsers, the three
  StringToDouble flag configs) carried over verbatim.
* Done: removed `vendor/double-conversion.wrap` +
  `vendor/packagefiles/double-conversion/`; dropped `double_conversion_dep` from
  `meson/deps/meson.build`; flipped `project()` -> `['c']` and removed `cpp_std`
  in `meson.build`; removed the now-dead `src/*.cc` globs from `sources.json`;
  deleted `src/numbers.cc`.
* **Guardrail (all green):** spec suite `--all` stays 98/0; the five `tests/`
  number files pass; Node differential (fixed grid + 20k random doubles + parse
  grid) is byte-for-byte identical; `scripts/mc-check.sh` = 170/170 under `../mc`.

#### Item 2 — Packed structs: `__attribute__((packed))` -> `#pragma pack` — DONE
* TinyCC **silently ignores** `__attribute__((packed))` (test: `sizeof` 8 not 5)
  but **honors** `#pragma pack(push,1)` / `#pragma pack(pop)` (test: 5).
* 8 wire/ABI-critical structs: `src/sandbox/backends/linux/kvm_internal.h` (2),
  `src/sandbox/backends/shared/include/sandbox_backend/net_internal.h` (5),
  `src/sandbox/backends/shared/include/sandbox_backend/virtio_vsock.h` (1).
* Wrapped each in `#pragma pack` and added `_Static_assert(sizeof(T) == N, ...)`
  to lock layout (TinyCC supports `_Static_assert`). Verified with `../mc build -c`.

#### Item 3 — `__builtin_ia32_pause()` -> inline asm — DONE
* [`src/modules/atomics.c`](file:///Users/danny/git/ant/src/modules/atomics.c) line ~1039.
  Replaced with `__asm__ __volatile__("pause")` (verified OK), preserving the
  existing aarch64 `"yield"` guard nearby.

#### Item 4 — `_Thread_local` audit (verification only) — DONE
* TinyCC mishandles **non-zero** TLS initializers. All current usages
  (`src/utils.c:24-25`, `src/utf8.c:28`) are zero/`{0}`-initialized and are safe.
  Added `.github/agents/check_thread_local.js` (wired into `check_all.js` /
  `mise run preflight`) as the CI grep guard forbidding non-zero `_Thread_local`
  initializers; no code change needed.

#### Item 5 — `__attribute__` inventory (audit) — DONE
* 18 files use `__attribute__`. After Item 2, remaining usages are all cosmetic
  (`format`, `noinline`, `visibility`, `fallthrough`) and ignored/honored
  harmlessly by TinyCC (spot-checked by direct `../mc build -c` compile). No
  load-bearing `aligned` / `cleanup` usages remain. ARM inline asm (`mrs`) in
  `kvm_aarch64.c` / `gic.c` is aarch64-only — out of scope for the x86_64
  `../mc` target; deferred.

#### Item 6 — Full-tree compile-and-triage under `../mc` — DONE
* Ran Item 0's harness across all engine TUs and fixed the remaining TinyCC
  gaps it surfaced (see progress note above): yyjson's `__has_include`
  indirection, `__GNUC__`-gated vendor branches in c-ares and
  wasm-micro-runtime, missing `max_align_t`/`ATOMIC_*_LOCK_FREE` in TinyCC's
  bundled libc headers, and two of our own headers relying on C23's implicit
  `bool` keyword instead of including `<stdbool.h>`. **169/169 engine TUs now
  compile cleanly under `../mc -c`**; confirmed the primary gcc/meson build
  (`ninja -C build libant.a`) still links cleanly with the same changes.
* Added `.github/workflows/mc-check.yml` as a parallel CI job compiling the
  tree with `mc -c` (keep the meson/gnu23 build primary through Phase 2). This
  workflow is untested against real GitHub Actions runners in this session —
  verify the `mc` build step (`python3 scripts/build.py` via `mise`/zig) on
  first CI run. Full link + dogfood is Phase 4.

**Definition of done — MET:** ant-owned engine is C-only (`project()` languages =
`['c']`, `cpp_std` dropped, double-conversion wrap + dep + `src/numbers.cc` gone);
all packed structs use `#pragma pack` with `_Static_assert` size locks; rejected
builtins replaced; whole engine (incl. `numbers.c`) compiles cleanly under
`../mc -c` — **170/170** (enforced by CI); spec suite (`--all`) = 98/0 + number
tests pass + Node conformance differential identical. **Phase 2 complete.** Caveat:
vendored `ada` and `wasm-micro-runtime` remain C++ subprojects linked into `ant`
(Meson links libstdc++ for them automatically); removing/porting those is a
separate future item, not part of Phase 2's engine-dogfooding goal.

**Explicitly not doing** (vs. the original C99-strip plan): rewriting VM dispatch
to `switch`, refactoring `({ ... })` macros, naming anonymous unions, or
macro-replacing `_Static_assert` / `_Alignof` — all accepted by TinyCC, so
touching them is pure risk with no benefit. `meson.build` `c_std=gnu23` may stay
(no C23-specific syntax exists in the tree; lowering it is optional churn).

---

### Phase 3: MIR Engine Alignment (`nightconcept/mir`)

**Goal:** Swap out `themackabu/mir` for the updated [`nightconcept/mir`](https://github.com/nightconcept/mir) repository, updating build definitions for its restructured `src/` directory layout and ensuring required runtime APIs (`MIR_remove_module`) are exported.

1. **Repository Swap & Meson Overlay**:
   * Update [`vendor/mir.wrap`](file:///home/danny/git/ant/vendor/mir.wrap) to point to `https://github.com/nightconcept/mir.git` with `patch_directory = mir`.
   * Create [`vendor/packagefiles/mir/meson.build`](file:///home/danny/git/ant/vendor/packagefiles/mir/meson.build) mapping sources to `src/mir.c` / `src/mir-gen.c` and include directory to `src/`.
2. **API Parity in `nightconcept/mir`**:
   * Export `MIR_remove_module` in `src/mir.h` and `src/mir.c` of `nightconcept/mir` so [`src/silver/swarm.c`](file:///home/danny/git/ant/src/silver/swarm.c) can release compiled modules.
3. **Verification**:
   * Reconfigure Meson (`meson setup build --reconfigure` or `ninja -C build`), compile `ant`, run engine tests and spec suite.

---

### Phase 4: Build System Migration & Dogfooding (`../mc`)

1. **Pre-Build Code Generation Driver**:
   * Script pre-compilation generation steps:
     * `python3 meson/messages.py src/core/messages.toml > build/messages.h`
     * `python3 meson/theme.py src/highlight/theme.toml > build/theme.h`
     * `node src/tools/gen_builtin_bundle.js > build/builtin_bundle.h`
     * `node src/tools/gen_snapshot.js > build/snapshot.h`
2. **`../mc` Build Orchestration**:
   * Create a build script (`scripts/build.sh` or Makefile) that invokes `../mc -std=c99` on source targets listed in [`sources.json`](file:///Users/danny/git/ant/sources.json).
   * Link static vendor libraries and `libpkg.a` (compiled via Zig 0.16) into the final `ant` binary.
