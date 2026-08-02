# Platform Toolchains

Status: active
Last reviewed: 2026-07-26
Owner: theMackabu

## Goal

Restore the Nix flake as the supported developer and package toolchain on
Linux and macOS, while retaining mise only for Windows tool provisioning.
Keep Meson as the underlying build workflow. Retain `just` as optional
shorthand on Unix and as the Windows bootstrap entrypoint without duplicating
its recipes in mise.

## Background

Commit `0bfada5579492189013f3ccee6e3f4d16644019e` removed the Nix flake and
`packages/nix/` in favor of a global `mise.toml`. That mise configuration
unconditionally exports `CC=clang`, `CXX=clang++`, and a macOS `SDKROOT`.
On Linux this selects a compiler that may not exist and exports an invalid
macOS SDK path. A failed `meson setup build --wipe` then leaves `build/`
unconfigured, so the following `just build` also fails.

Upstream `theMackabu/ant` master at
`8ba31b9b2d7e44d441758d8514373542cda762e3` still contains a working Nix
layout:

- `flake.nix` and `flake.lock`
- `packages/nix/toolchain.nix` selecting LLVM 21
- `packages/nix/shell.nix` with Darwin-only SDK and binutils settings
- `packages/nix/package.nix`, `vendor.nix`, and version helpers

The flake serves two separate purposes. Its `packages.ant` output makes Ant
buildable as a Nix package with `nix build .#ant`, while
`devShells.default` supplies the environment loaded by `nix develop` and
direnv. Upstream's package derivation declares the full build tool set, but
its dev shell currently declares only LLVM 21 Clang, compiler-rt, and
binutils. This fork must add the user-facing build tools to the dev shell for
`just setup` to work on a clean machine.

The upstream files are a baseline, not a blind revert. This fork changed the
MIR wrap and Meson build graph after the Nix removal, so the restored package
and fixed-output vendor hash must be validated against the current tree.

## Scope

- Restore and adapt the upstream flake, lock file, and `packages/nix/`.
- Use the flake dev shell on Linux and macOS through `.envrc`.
- Keep the upstream Cachix substituter configuration.
- Reduce `mise.toml` to Windows-only tool declarations.
- Remove compiler, SDK, and task definitions from mise.
- Keep setup, build, test, and validation recipes in the root `justfile` as
  optional aliases for the documented Meson commands.
- Update build documentation for the platform split.

Restoring the upstream `nix-cache.yml` workflow is out of scope initially.
The fork's branch-specific CI should be changed separately after local Linux
and macOS flake validation establishes the intended cache/build behavior.

## Decisions

1. Nix owns the complete Unix developer toolchain. The dev shell supplies
   LLVM 21, compiler runtime and binutils, Meson, Ninja, CMake, pkg-config,
   Node.js 22, Python, Git, curl, Zig 0.16, and `just`.
2. mise remains a checked-in Windows bootstrap, but each tool is restricted
   with `os = ["windows"]`. This avoids relying on mise's newer `auto_env`
   platform-config discovery and makes the existing root config inert on Unix.
3. mise does not set `CC`, `CXX`, or `SDKROOT`. Windows compiler selection
   remains the responsibility of the supported MSYS2 CLANG64 environment.
   This matches current CI, which installs the
   `mingw-w64-clang-x86_64-toolchain` and selects `clang`, `clang++`,
   `llvm-ar`, `llvm-ranlib`, and LLD.
4. mise does not duplicate tasks. `BUILDING.md` continues to teach direct
   Meson commands on Unix. On Windows, `just setup` invokes the idempotent
   PowerShell bootstrap from `scripts/bootstrap-windows.ps1` before
   configuring Meson, and `just build` compiles the configured tree.
5. `.envrc` uses `use flake . --accept-flake-config` so non-interactive direnv
   evaluation can accept the flake's checked-in Cachix substituter and key.
   Developers must still explicitly run `direnv allow`.
6. Restore the complete Nix package expression, not only the dev shell, so
   `nix build .#ant` remains a reproducible packaging path.

## Task List

### 1. Restore the Nix baseline

- Restore `flake.nix`, `flake.lock`, and `packages/nix/` from upstream master
  commit `8ba31b9b2d7e44d441758d8514373542cda762e3`.
- Add Meson, Ninja, CMake, pkg-config, Node.js 22, Python, Git, curl, Zig
  0.16, and `just` to the dev shell because upstream currently puts those
  tools only in the package derivation and this fork replaced Maid with Just.
- Preserve the upstream platform conditional that exports `SDKROOT` only on
  Darwin.
- Explicitly clear `SDKROOT` on Linux so a parent shell or legacy mise
  activation cannot leak a Darwin SDK into Meson.
- Review the package expression against the current Meson and npm generation
  flow.

### 2. Adapt vendor and package inputs

- Recompute `packages/nix/vendor.nix`'s fixed-output hash from the current
  wraps, including the fork's `nightconcept/mir` revision and Meson overlay.
- Confirm that the prebuilt `src/tools/node_modules` symlink still causes the
  current `meson/npm_ci.py` step to skip networked `npm ci`.
- Confirm Zig 0.16 and `ranlib` are resolved from the Nix environment.

### 3. Restrict mise to Windows

- Convert each `mise.toml` tool entry to an OS-restricted Windows entry.
- Remove the entire `[env]` table.
- Remove all `[tasks.*]` entries, leaving the `justfile` as the only task
  definition.
- Verify `mise install`, `just setup`, and `just build` from PowerShell.

### 4. Update documentation

- Document `direnv allow`, `nix develop`, `just setup`, and `just build` as the
  Linux/macOS convenience path, while keeping the direct Meson commands as the
  primary instructions.
- Document `mise install` plus MSYS2 CLANG64 prerequisites as the Windows path.
- Explain that mise supplies userland build tools on Windows but not the
  compiler or MSYS2 runtime.
- Document the checked-in PowerShell bootstrap as the preferred, idempotent
  way to install or repair the MSYS2 CLANG64 environment.
- Remove stale Maid references where the Just migration already superseded
  them.
- Make clear that `.envrc` is a Unix convenience: direnv loads the flake on
  Linux/macOS, while Windows ignores it and activates mise instead.

### 5. Validate

Linux:

```sh
direnv exec . clang --version
direnv exec . zig version
direnv exec . just setup
direnv exec . just build
nix build .#ant --accept-flake-config --print-build-logs
just preflight
```

macOS, on both x86_64 and aarch64:

```sh
direnv exec . xcrun --show-sdk-path
direnv exec . just setup
direnv exec . just build
nix build .#ant --accept-flake-config --print-build-logs
```

Windows, from PowerShell:

```powershell
mise trust
mise install
mise current
just setup
just build
.\build\ant.exe --version
```

Also run:

```sh
nix flake check --accept-flake-config
just knowledge
just structure
```

## Validation Status

- Confirmed upstream master and the local `upstream/master` ref both point to
  `8ba31b9b2d7e44d441758d8514373542cda762e3`.
- Confirmed the upstream flake exposes both `packages.ant` and the default
  dev shell for all default systems.
- Confirmed upstream confines `SDKROOT` and Darwin binutils to Darwin.
- Confirmed current mise exports macOS settings on Linux and causes Meson's
  missing-Clang failure.
- Confirmed `.envrc` syntax locally.
- Restored the flake and confirmed it evaluates for all default systems.
- Confirmed the Linux dev shell provides Clang 21.1.8, Meson 1.10.2, Ninja
  1.13.2, CMake 4.1.2, Node.js 22.22.2, Python 3.13.12, Zig 0.16.0, Just
  1.50.0, and pkg-config 0.29.2.
- Confirmed `just setup` and `just build` complete in the Linux Nix dev shell
  and compile all 1,122 targets.
- Confirmed the resulting binary reports its version, executes JavaScript, and
  links its runtime libraries from the Nix store.
- Updated the fixed-output vendor hash for the current wraps and confirmed the
  complete `nix build .#ant` package derivation builds and fixes up
  successfully.
- Confirmed the package source filter excludes generated build trees, local
  dependency caches, direnv state, agent worktrees, and downloaded vendor
  directories while retaining tracked wrap and package overlay inputs.
- Confirmed current Windows CI uses MSYS2 CLANG64 and LLVM tools; the
  `BUILDING.md` MINGW64/GCC instructions are stale.
- Reconciled the Windows-only mise configuration with the idempotent
  PowerShell/MSYS2 bootstrap added on `origin/dev`.
- macOS validation requires macOS x86_64 and aarch64 hosts.
- Windows validation requires an MSYS2 CLANG64 host.

## Risks and Follow-ups

- The upstream vendor fixed-output hash is stale after the MIR wrap change and
  must not be copied without regeneration.
- `--accept-flake-config` trusts the Cachix endpoint and public key committed
  in `flake.nix`; any future cache change needs explicit review.
- Building all four Unix architecture combinations belongs in CI after local
  validation. Restoring the old master-only cache workflow unchanged would not
  match this fork's protected `main` pull-request gate and `upstream` record
  workflow.
- mise's Windows downloads and MSYS2 CLANG64 packages can overlap.
  Documentation should name which installation owns each executable to avoid
  mixed PATHs.
