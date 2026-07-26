# CI Build Cache Optimization

Status: completed
Completed: 2026-07-26

## Problem

Fresh platform jobs repeatedly compile unchanged C, C++, and Zig sources and
download the same npm package data. The existing vendor cache also included
`build/vendor`, creating roughly 285–300 MB entries containing brittle Meson
build output. Three branch-scoped MSYS2 caches alone consumed about 5.32 GB of
the repository's default 10 GB Actions cache allowance.

The build timestamp and Git-derived version values were global compiler
arguments. Because those values change between builds, they invalidated every
C compiler cache entry even when a translation unit did not use version data.

## Decision

- Add platform- and toolchain-scoped caches for ccache, Zig's global build
  cache, and npm's download cache.
- Rotate ccache and Zig entries weekly. Restore the previous entry when a new
  week begins, then save the refreshed entry after a successful job.
- Limit ccache to 200 MB per platform.
- Cache only downloaded `vendor/*/` sources, not `build/vendor`.
- Skip native-dependency cache entries for platforms with no separately built
  native dependencies, and key zlib directly by its version and build recipe.
- Generate `ant_version_config.h` and include it only in translation units
  that consume version metadata. This keeps timestamp and Git version changes
  from invalidating unrelated compiler-cache entries.
- Report ccache statistics in every cached build so hit rates remain visible.

## Cache Maintenance

`dev` is the default branch, so its compatible caches can be restored by the
other long-lived branches. List and remove redundant branch entries by ID:

```sh
gh cache list -R nightconcept/ant
gh cache delete <cache-id> -R nightconcept/ant
```

Do not delete all caches indiscriminately. Keep the current `dev` MSYS2 entry
and remove stale duplicate entries scoped to `main` and `upstream`.

## Validation

- Workflow and composite-action YAML lint passed.
- Repository knowledge, structure, and validation-router checks passed.
- `git diff --check` passed.
- A fresh MinGW Meson configuration generated `ant_version_config.h` and
  compilation passed all version-consuming translation units. The local GCC
  build later stopped in the existing `src/silver/limits.c` Windows SDK path
  because `GetCurrentThreadStackLimits` was unavailable; CI uses the supported
  CLANG64 toolchain instead.
- The installed LLVM, Zig, and ccache flow still requires clean CI validation
  across the platform matrix.
