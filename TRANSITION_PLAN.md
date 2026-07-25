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
│ Phase 3: MIR Engine Alignment (themackabu/mir -> ../mir)│
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

**Progress note (2026-07-25):** Items 0, 2, 3, 4, 5, and 6 are done — see below.
Item 1 (`numbers.cc` -> `numbers.c`) is the only item left in Phase 2 and has not
been started; it is the long pole (Ryu/Grisu3 port) and should be scoped/planned
separately before starting.

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

#### Item 1 — `src/numbers.cc` -> `src/numbers.c` (long pole; start first, runs in parallel)
* Only `.cc` in the tree; TinyCC has **no C++**. It wraps the C++
  **double-conversion** library for ECMAScript-correct number formatting/parsing.
* `snprintf`/`strtod` alone will **not** reproduce shortest-round-trip
  `Number.prototype.toString`. Port a C implementation of **Ryu** (or Grisu3) for
  shortest double->string, plus hand-rolled `toFixed`/`toPrecision`/`toExponential`
  and a JS-rules parser (hex / `Infinity` / `NaN`).
* Then: remove [`vendor/double-conversion.wrap`](file:///Users/danny/git/ant/vendor/double-conversion.wrap);
  change `project('ant', ['c', 'cpp'], ...)` -> `['c']` and drop `cpp_std` in
  [`meson.build`](file:///Users/danny/git/ant/meson.build).
* **Guardrail:** `examples/spec/run.js --all` + `tools/wpt` number tests + number
  tests under `tests/`. This item lives or dies on conformance.

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

**Definition of done:** no C++ in the tree (`project()` languages = `['c']`,
double-conversion wrap gone); all packed structs use `#pragma pack` with
`_Static_assert` size locks; rejected builtins replaced; whole engine compiles
cleanly under `../mc -c` (enforced by CI); spec suite (`--all`) + number/WPT
tests pass. **Everything above is done except the C++ removal itself (Item 1)**,
which blocks marking Phase 2 fully complete.

**Explicitly not doing** (vs. the original C99-strip plan): rewriting VM dispatch
to `switch`, refactoring `({ ... })` macros, naming anonymous unions, or
macro-replacing `_Static_assert` / `_Alignof` — all accepted by TinyCC, so
touching them is pure risk with no benefit. `meson.build` `c_std=gnu23` may stay
(no C23-specific syntax exists in the tree; lowering it is optional churn).

---

### Phase 3: MIR Engine Alignment (`../mir`)

1. **Audit Fork API Diffs**:
   * Compare `themackabu/mir` headers with `../mir` API definitions.
   * Pull any custom MIR instruction variants, optimization flags, or helper functions into `../mir`.
2. **Update Swarm JIT Includes**:
   * Direct [`src/silver/swarm.c`](file:///Users/danny/git/ant/src/silver/swarm.c) to include headers from `../mir`.
   * Link the final executable directly against `../mir` build outputs.

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
