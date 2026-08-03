# Building Ant

Depending on what platform or features you need, the build process may
differ. After you've built a binary, running the
test suite to confirm that the binary works as intended is a good next step.

If you can reproduce a test failure, search for it in the <br>
[Ant issue tracker](https://github.com/theMackabu/ant/issues) or file a new issue.

## Table of contents

- [Supported platforms](#supported-platforms)
  - [Platform list](#platform-list)
  - [Supported toolchains](#supported-toolchains)
  - [Official binary platforms and toolchains](#official-binary-platforms-and-toolchains)
- [Building Ant on supported platforms](#building-ant-on-supported-platforms)
  - [Prerequisites](#prerequisites)
  - [Unix and macOS](#unix-and-macos)
    - [Unix prerequisites](#unix-prerequisites)
    - [macOS prerequisites](#macos-prerequisites)
    - [Building Ant](#building-ant-1)
    - [Installing Ant](#installing-ant)
    - [Running tests](#running-tests)
    - [Building a debug build](#building-a-debug-build)
    - [Building an ASan build](#building-an-asan-build)
    - [Speeding up frequent rebuilds when developing](#speeding-up-frequent-rebuilds-when-developing)
    - [Troubleshooting Unix and macOS builds](#troubleshooting-unix-and-macos-builds)
  - [Windows](#windows)
    - [Windows prerequisites](#windows-prerequisites)
    - [Building Ant](#building-ant-2)
- [Meson build options](#meson-build-options)

## Supported platforms

### Platform list

Ant builds and runs on the following platforms. Official CI builds are
produced for each platform listed below.

| Operating System | Architectures | Variant      | Static | Notes                        |
| ---------------- | ------------- | ------------ | ------ | ---------------------------- |
| GNU/Linux        | x64           | glibc        | No     | Ubuntu 22.04 (CI)            |
| GNU/Linux        | aarch64       | glibc        | No     | Ubuntu 22.04 (CI)            |
| GNU/Linux        | x64           | musl         | Yes    | Alpine Edge (CI)             |
| GNU/Linux        | aarch64       | musl         | Yes    | Alpine Edge (CI)             |
| macOS            | x64           | darwin       | No     | macOS 15 (CI)                |
| macOS            | aarch64       | darwin       | No     | macOS 15 (CI)                |
| Windows          | x64           | clang64/msys | No     | MSYS2 CLANG64 toolchain (CI) |

### Supported toolchains

Ant is built with the GNU C23 standard (`-std=gnu23`). A compiler with
C23 support is required.

| Operating System | Compiler Versions                     |
| ---------------- | ------------------------------------- |
| Linux            | GCC >= 14 or Clang >= 18              |
| macOS            | Xcode CLT (Apple Clang) or LLVM >= 18 |
| Windows          | LLVM/Clang via MSYS2 (CLANG64)        |

### Official binary platforms and toolchains

CI binaries are produced using:

| Binary package         | Platform and Toolchain                       |
| ---------------------- | -------------------------------------------- |
| ant-linux-x64          | Ubuntu 22.04 (glibc), LLVM/Clang             |
| ant-linux-aarch64      | Ubuntu 22.04 (glibc), LLVM/Clang             |
| ant-linux-x64-musl     | Alpine Edge (musl), statically linked, Clang |
| ant-linux-aarch64-musl | Alpine Edge (musl), statically linked, Clang |
| ant-darwin-x64         | macOS 15 Intel, LLVM/Clang                   |
| ant-darwin-aarch64     | macOS 15 ARM, LLVM/Clang                     |
| ant-windows-x64        | MSYS2 CLANG64 toolchain                      |

## Building Ant on supported platforms

### Prerequisites

The following tools are required to build Ant regardless of platform:

- **C compiler** with C23 support (GCC >= 14 or Clang >= 18)
- **[Meson](https://mesonbuild.com/)** build system (and Ninja backend)
- **[CMake](https://cmake.org/)** (for the tlsuv subproject)
- **pkg-config**
- **Node.js** >= 22 and **npm** (used to generate bundled JavaScript sources at
  build time)
- **[Zig](https://ziglang.org/)** 0.16.x (builds the package manager component)
- **Git**

Dependencies are vendored as Meson subprojects under `vendor/`
and are fetched automatically:

- aklomp-base64 0.5.2
- Ada URL 4.0.0
- argtable3 3.3.1
- BoringSSL `297b11798a0ed6bc7736aa57328909a4afbbf67a`
- c-ares
- crprintf `HEAD`
- double-conversion
- google-brotli 1.1.0
- libffi 3.5.2
- libuv 1.52.0
- llhttp 9.3.1
- LMDB (OpenLDAP LMDB 0.9.33)
- mimalloc 3.3.2 (optional runtime allocator)
- minicoro `HEAD`
- MIR `HEAD`
- nghttp2 1.68.0
- PCRE2 10.47
- Simde
- Skim
- tlsuv 0.40.13
- utf8proc 2.10.0
- uthash 2.3.0
- uuidv7-h `HEAD`
- wasm-micro-runtime `92f40918bbfad35546a1512b10bd25eaa31add4d`
- wirecall
- yyjson 0.12.0
- zlib-ng 2.3.3

### Unix and macOS

#### Unix prerequisites

The supported development environment on Linux and macOS is the checked-in
Nix flake. Install [Nix](https://nixos.org/download/) with flakes enabled,
then enter the shell from the repository root:

```bash
nix develop --accept-flake-config
```

The shell provides LLVM/Clang 21, Meson, Ninja, CMake, pkg-config, Node.js 22,
Python, Git, curl, Zig 0.16, and Just. `--accept-flake-config` accepts the
Cachix substituter and public key declared in `flake.nix`.

For automatic shell activation, install
[direnv](https://direnv.net/) and
[nix-direnv](https://github.com/nix-community/nix-direnv), then run once:

```bash
direnv allow
```

The checked-in `.envrc` loads the same flake. It is intended for Linux and
macOS; Windows development uses mise as described below.

To build the reproducible Nix package rather than enter the development shell:

```bash
nix build .#ant --accept-flake-config
./result/bin/ant --version
```

If you cannot use Nix, install the prerequisites manually:

- Ubuntu/Debian:

  ```bash
  sudo apt-get install python3 python3-pip gcc-14 g++-14 ninja-build cmake \
    pkg-config nodejs npm
  pip3 install meson
  ```

- Fedora:

  ```bash
  sudo dnf install python3 gcc gcc-c++ ninja-build cmake pkgconf \
    nodejs npm
  pip3 install meson
  ```

- Alpine (musl):
  ```sh
  apk add clang lld llvm meson ninja cmake pkgconf nodejs npm \
    musl-dev \
    util-linux-dev util-linux-static linux-headers libunwind-dev libunwind-static
  ```

You will also need Zig 0.16.x installed:

```bash
# Zig (download from https://ziglang.org/download/)
# Or via package manager if available
```

#### macOS prerequisites

The Nix flake described above is the supported macOS development environment.
It discovers the active Xcode SDK while supplying the remaining toolchain.
For a manual setup instead:

- Xcode Command Line Tools (provides Apple Clang):

  ```bash
  xcode-select --install
  ```

- Install remaining tools via [Homebrew](https://brew.sh):

  ```bash
  brew install meson ninja llvm node
  ```

- Zig:

  ```bash
  # install 0.16.0
  brew install zig
  ```

#### Building Ant

> [!IMPORTANT]
> If the path to your build directory contains a space, the build will likely
> fail.

To build Ant:

```bash
meson subprojects download
meson setup build
meson compile -C build
```

Run these commands inside `nix develop`, or let direnv load the flake first.
Meson runs `npm ci` in `src/tools` automatically before generating the bundled
JavaScript headers; no separate npm install step is needed.

Alternatively, use the checked-in `justfile`:

```bash
just setup       # downloads subprojects and configures build/
just build       # compiles
just run <file>  # builds and runs a JS file
```

> [!TIP]
> Use `just run <file>` during development to build and execute in one step.

To verify the build:

```bash
./build/ant --version
./build/ant -e "console.log('Hello from Ant ' + Ant.version)"
```

Ant versions are generated as `major.minor.build.patch`. The
`meson/ant.version` file defines the numeric release fields:

```ini
major=12
minor=0
patch=2
```

Meson fills the `build` field with the short git hash, so a build from
`64324a91...` reports `12.0.64324a91.2`. The Meson `build_timestamp` option is
still embedded as `ANT_BUILD_TIMESTAMP` and shown by `ant --version`; it is not
part of the version string.

#### Installing Ant

You can install the built binary using:

```bash
just install
```

This copies the binary to the directory of an existing `ant` installation, or
falls back to `~/.ant/bin/`. It also creates an `antx` symlink.

Alternatively, copy the binary manually:

```bash
cp ./build/ant /usr/local/bin/ant
```

#### Running tests

To run a single test:

```bash
./build/ant tests/test_async.cjs
```

To run the spec suite:

```bash
./build/ant examples/spec/run.js
```

> [!NOTE]
> Remember to recompile with `meson compile -C build` (or `just build`)
> between test runs if you change code in the `src/` directory.

#### Building a debug build

A debug build disables optimizations and LTO, and preserves debug symbols:

```bash
meson subprojects download
CC="ccache $(which clang)" \
  meson setup build --wipe --buildtype=debug \
  -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false -Dunity=off
meson compile -C build
```

Or with Just:

```bash
just debug
just build
```

When using the debug build, core dumps will be generated in case of crashes.
Use `lldb` or `gdb` with the debug binary to inspect them:

```bash
lldb ./build/ant core.ant
(lldb) bt
```

#### Building an ASan build

[ASan](https://github.com/google/sanitizers) can help detect memory bugs.

> [!WARNING]
> ASan builds are significantly slower than release builds. The debug flags
> are not required but can produce clearer stack traces when ASan detects
> an issue.

```bash
meson subprojects download
CC="ccache $(which clang)" \
  meson setup build --wipe \
  -Db_sanitize=address -Doptimization=0 -Db_lto=false -Dstrip=false -Db_lundef=false
meson compile -C build
```

Or with Just:

```bash
just asan
just build
```

Then run tests against the ASan build:

```bash
./build/ant tests/test_gc.js
```

#### Speeding up frequent rebuilds when developing

If you plan to frequently rebuild Ant, installing `ccache` can greatly
reduce build times.

> [!TIP]
> Using both `ccache` and `lld` together provides the best rebuild
> performance. `ccache` caches compilation, while `lld` speeds up linking
> (which cannot be cached).

On GNU/Linux:

```bash
sudo apt install ccache
export CC="ccache gcc"    # add to your .profile
```

On macOS:

```bash
brew install ccache
export CC="ccache cc"     # add to ~/.zshrc
```

Using `lld` as the linker also speeds up link times:

```bash
export CC_LD="$(which ld64.lld)"  # macOS with brew llvm
# or
export CC_LD="$(which lld)"       # Linux
```

> [!NOTE]
> LTO is enabled by default with 8 threads (`b_lto=true`,
> `b_lto_threads=8`). Disable it with `-Db_lto=false` for faster iteration
> during development.

#### Profile-guided optimization

Release builds automatically use LLVM PGO data when a matching profile exists
at `meson/pgo/profiles/ant-<system>-<cpu>.profdata` and the C/C++ compiler is
Clang-compatible. For example, macOS ARM64 uses
`meson/pgo/profiles/ant-darwin-aarch64.profdata`.

To regenerate the profile and produce a final PGO build:

```bash
./meson/pgo/build.sh
```

The script uses the current shell toolchain. Generate and consume a profile
with the same Clang/LLVM version so the profile data remains compatible.

PGO can also be controlled explicitly with Meson:

```bash
meson setup build -Dpgo=enabled   # require a matching profile
meson setup build -Dpgo=disabled  # ignore checked-in profiles
```

#### Troubleshooting Unix and macOS builds

Stale builds can sometimes result in errors. Clean the build directory and
reconfigure:

```bash
rm -rf build
meson setup build
meson compile -C build
```

If you encounter "file not found" errors for vendored dependencies:

```bash
meson subprojects download
```

If the build runs out of memory, reduce parallelism:

```bash
meson compile -C build -j2
```

### Windows

#### Windows prerequisites

Ant on Windows is built using the MSYS2 CLANG64 toolchain. This matches the
Windows CI build.

> [!IMPORTANT]
> Native MSVC builds are not currently supported.

1. Install [mise](https://mise.jdx.dev/installing-mise.html) for Windows, for
   example with `winget install jdx.mise` or `scoop install mise`.
2. From PowerShell in the repository root, install Just and Zig as pinned by
   `mise.toml`:
   ```powershell
   mise trust
   mise install
   ```
3. Bootstrap and build:
   ```powershell
   just setup
   just build
   ```

`just setup` is idempotent on Windows. It installs MSYS2 with winget when
`C:\msys64` (or `MSYS2_ROOT`) is absent, ensures the complete CLANG64 build
toolchain is installed with pacman, performs a full MSYS2 system upgrade, and
configures the Meson build directory. Rerunning it repairs missing or stale
packages without reinstalling packages that are already current. The bootstrap
also checks minimum versions of the MSYS2 tools known to match the Windows CI
build.

mise supplies only Just and Zig on Windows. MSYS2 supplies Clang, binutils,
pkg-config, Node.js, Python, Meson, Ninja, CMake, NASM, ccache, and the CLANG64
runtime. The Justfile puts the CLANG64 directories first on `PATH`, matching
Windows CI tool resolution. The mise configuration is OS-restricted and is
inert on Linux and macOS.

To provision MSYS2 manually instead, install
[MSYS2](https://www.msys2.org/) and these packages:

```bash
pacman -S mingw-w64-clang-x86_64-toolchain \
  mingw-w64-clang-x86_64-meson mingw-w64-clang-x86_64-ninja \
  mingw-w64-clang-x86_64-cmake mingw-w64-clang-x86_64-lld \
  mingw-w64-clang-x86_64-nodejs mingw-w64-clang-x86_64-pkgconf \
  mingw-w64-clang-x86_64-nasm mingw-w64-clang-x86_64-ccache
```

#### Building Ant

From PowerShell in the repository root:

```powershell
just setup
just build
```

> [!NOTE]
> Windows builds use `-Dc_std=gnu2x` instead of `gnu23` due to MinGW
> toolchain compatibility.

To verify:

```bash
./build/ant.exe --version
```

## Meson build options

Configure options are set via `meson setup` or `meson configure`:

| Option              | Type    | Default    | Description                                           |
| ------------------- | ------- | ---------- | ----------------------------------------------------- |
| `jit`               | boolean | `true`     | Enable the JIT compiler                               |
| `allocator`         | combo   | `system`   | Runtime malloc implementation (`mimalloc`, `system`)  |
| `static_link`       | boolean | `false`    | Statically link the final binary                      |
| `linker_map`        | boolean | `false`    | Emit a linker map for the Ant binary                  |
| `codesign`          | boolean | `true`     | Codesign the Ant binary on Darwin                     |
| `embed_example`     | feature | `auto`     | Build the libant embed example                        |
| `native_tuning`     | feature | `disabled` | Optimize for the current build host CPU               |
| `pgo`               | feature | `auto`     | Use matching `meson/pgo/profiles/*.profdata` profiles |
| `pgo_generate_dir`  | string  | (empty)    | Directory for raw LLVM PGO profiles                   |
| `build_timestamp`   | string  | (auto)     | Embedded build timestamp metadata                     |
| `build_git_hash`    | string  | (auto)     | Git hash embedded in version metadata                 |
| `deps_prefix_cmake` | string  | (empty)    | Prefix path for cmake dependency lookup               |

Standard Meson built-in options used by Ant:

| Option          | Default   | Description                       |
| --------------- | --------- | --------------------------------- |
| `buildtype`     | `release` | Build type (release, debug, etc.) |
| `optimization`  | `3`       | Optimization level (0-3)          |
| `c_std`         | `gnu23`   | C language standard               |
| `b_lto`         | `true`    | Link-time optimization            |
| `b_lto_threads` | `8`       | LTO parallelism                   |
| `strip`         | `true`    | Strip debug symbols from binary   |
| `b_sanitize`    | `none`    | Sanitizer (e.g. `address`)        |

Example:

```bash
meson setup build -Dstatic_link=true --prefer-static
meson setup build -Dallocator=system
```
