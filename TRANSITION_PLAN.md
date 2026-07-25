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

#### Item 0 — `../mc` compile harness (prerequisite)
* Script (`scripts/mc-check.sh`) runs `../mc/build/mc build -c` on each engine
  translation unit with meson's include dirs (`-Iinclude -Ibuild -Ivendor/...`).
* Reuse the generated headers meson already emits into `build/`
  (`messages.h`, `theme.h`, `builtin_bundle.h`, `snapshot.h`); do **not** wait on
  the Phase 4 gen-driver.
* Produces the per-file pass/fail matrix that drives Item 6.

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

#### Item 2 — Packed structs: `__attribute__((packed))` -> `#pragma pack`
* TinyCC **silently ignores** `__attribute__((packed))` (test: `sizeof` 8 not 5)
  but **honors** `#pragma pack(push,1)` / `#pragma pack(pop)` (test: 5).
* 8 wire/ABI-critical structs: `src/sandbox/backends/linux/kvm_internal.h` (2),
  `src/sandbox/backends/shared/include/sandbox_backend/net_internal.h` (5),
  `src/sandbox/backends/shared/include/sandbox_backend/virtio_vsock.h` (1).
* Wrap each in `#pragma pack` and add `_Static_assert(sizeof(T) == N, ...)` to
  lock layout (TinyCC supports `_Static_assert`).

#### Item 3 — `__builtin_ia32_pause()` -> inline asm
* [`src/modules/atomics.c`](file:///Users/danny/git/ant/src/modules/atomics.c) line ~1039.
  Replace with `__asm__ __volatile__("pause")` (verified OK), preserving the
  existing aarch64 `"yield"` guard nearby.

#### Item 4 — `_Thread_local` audit (verification only)
* TinyCC mishandles **non-zero** TLS initializers. All current usages
  (`src/utils.c:24-25`, `src/utf8.c:28`) are zero/`{0}`-initialized and are safe.
  Add a CI grep guard forbidding non-zero `_Thread_local` initializers; no code
  change.

#### Item 5 — `__attribute__` inventory (audit)
* 18 files use `__attribute__`. After Item 2, cosmetic kinds (`noreturn`,
  `format`, `unused`, `always_inline`) are ignored harmlessly by TinyCC. Verify
  no load-bearing `aligned` / `cleanup` usages remain (none found so far). ARM
  inline asm (`mrs`) in `kvm_aarch64.c` / `gic.c` is aarch64-only — out of scope
  for the x86_64 `../mc` target; note and defer.

#### Item 6 — Full-tree compile-and-triage under `../mc`
* Run Item 0's harness across all engine TUs; fix remaining TinyCC gaps (libc
  header differences, other unsupported `__builtin_*`, etc.), then link and run
  the spec suite.
* Add a parallel CI job compiling the tree with `mc -c` (keep the meson/gnu23
  build primary through Phase 2). Full link + dogfood is Phase 4.

**Definition of done:** no C++ in the tree (`project()` languages = `['c']`,
double-conversion wrap gone); all packed structs use `#pragma pack` with
`_Static_assert` size locks; rejected builtins replaced; whole engine compiles
cleanly under `../mc -c` (enforced by CI); spec suite (`--all`) + number/WPT
tests pass.

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
