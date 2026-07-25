# Ant Fork & Simplification Transition Plan

Status: active
Last reviewed: 2026-07-25
Owner: User & Antigravity

This execution plan outlines the step-by-step roadmap to fork and simplify **Ant**, transition the developer toolchain from Nix to **Mise**, lower the compilation standard from **GNU23 / C++ down to pure C99** for dogfooding with `../mc`, align the custom `../mir` engine, and streamline the build system.

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
│ Phase 2: C Standard & Language Pruning (GNU23/C++ -> C99)│
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

### Phase 2: C Standard & Language Simplification (GNU23 / C++ -> C99)

1. **Convert C++ Files to C99**:
   * Refactor [`src/numbers.cc`](file:///Users/danny/git/ant/src/numbers.cc) into pure C99 (`src/numbers.c`) using standard C number formatting utilities (`snprintf`, `strtod`), eliminating the C++ compiler requirement for `../mc`.
2. **Resolve C11 Blockers**:
   * **Anonymous Unions/Structs**: Name inner anonymous structs/unions in [`include/silver/engine.h`](file:///Users/danny/git/ant/include/silver/engine.h) and update all member access sites across `src/silver/`.
   * **`_Static_assert`**: Replace `_Static_assert` in [`src/ant.c`](file:///Users/danny/git/ant/src/ant.c) and `engine.h` with a C99-compliant array macro:
     ```c
     #define STATIC_ASSERT(cond) typedef char static_assertion_##__LINE__[(cond) ? 1 : -1]
     ```
3. **Clean Up GNU Extensions**:
   * **Statement Expressions**: Refactor `({ ... })` macros in [`src/main.c`](file:///Users/danny/git/ant/src/main.c), [`src/silver/ast.c`](file:///Users/danny/git/ant/src/silver/ast.c), and [`src/silver/engine.c`](file:///Users/danny/git/ant/src/silver/engine.c) (`VM_CHECK`, `NEXT`) into standard `do { ... } while(0)` blocks or static inline functions.
   * **Attributes**: Guard `__attribute__((...))` usages behind `#ifdef __GNUC__`. Use `#pragma pack(1)` for packed structs in sandbox backends.
   * **Flexible Array Members**: Convert zero-length arrays `[0]` in [`src/ant.c`](file:///Users/danny/git/ant/src/ant.c) to standard C99 `[]`.

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
