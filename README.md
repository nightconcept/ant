# 🐜 Ant

_An ant carries 50× its weight. So does this one._

Ant is a lightweight, high-performance JavaScript runtime built from scratch. <br>
Built to carry more than it weighs without compromising performance.

```bash
$ ls -lh ant
-rwxr-xr-x⠀8.9M⠀ant*

# built with -Os
-rwxr-xr-x⠀4.4M⠀ant*
```

## Table of contents

- [Why Ant?](#why-ant)
- [Installation](#installation)
- [Benchmarks](#benchmarks)
- [Spec conformance](#spec-conformance)
- [Building Ant](#building-ant)
- [Security](#security)
- [Community](#community)
- [Contributing to Ant](#contributing-to-ant)

## Why Ant?

|                     | Ant (Fork) | Ant (Upstream) | Node    | Bun    | Deno   |
| ------------------- | ---------- | -------------- | ------- | ------ | ------ |
| Binary size         | **~12 MB** | ~11 MB         | ~115 MB | ~94 MB | ~122 MB |
| Cold start          | **~8.7 ms**| **~8.6 ms**    | ~38 ms  | ~20 ms | ~30 ms |
| Engine              | Ant Silver | Ant Silver     | V8      | JSC    | V8     |
| JIT                 | ✓          | ✓              | ✓       | ✓      | ✓      |
| Regression suite     | ✓          | ✓              | —       | —      | —      |

Ant is designed for environments where size and startup time matter: serverless functions, edge computing, embedded systems, CLI tools, and anywhere you'd want JavaScript but can't afford a 50MB+ runtime.

The engine, Ant Silver is hand-built, not a wrapper around V8, JSC, or SpiderMonkey. The JIT compiler uses a fork of [MIR](https://github.com/themackabu/mir), a lightweight backend that enables near compiled performance.

## Installation

```bash
curl -fsSL https://antjs.org/install | bash
```

## Spec conformance

Ant validates runtime changes with the complete Ant Regression suite and a
pinned Test262 corpus. Regression runs must pass completely; Test262 runs must
not gain failures or lose tests.

| Suite        | Pass rate | Notes                                      |
| ------------ | --------- | ------------------------------------------ |
| Ant Regression | **100%** | 569/569 (runtime tests and spec examples) |
| Test262        | ~64%     | Changes must not reduce the existing result |

## Benchmarks

### Cold start

Measures the time to import [Hono](https://hono.dev), register routes, and exit. Each runtime loads the same `bench-coldstart.js` script from `examples/npm/hono/` that creates a Hono app with two routes, prints "ready", and calls `process.exit(0)`. No HTTP server is actually started, this isolates module resolution and initialization overhead.

Measured with `just bench` (hyperfine 10 warmup runs, 100 timed runs):

```bash
just bench
```

| Runtime | Mean | Min | Max | Relative |
| ------- | ---- | --- | --- | -------- |
| **Ant (Upstream)** | **8.6 ms** | 6.5 ms | 11.4 ms | **1.00** |
| **Ant (Fork)** | **8.7 ms** | 6.2 ms | 11.2 ms | 1.01× slower |
| Bun | 20.1 ms | 15.6 ms | 27.2 ms | 2.33× slower |
| Deno | 29.7 ms | 25.0 ms | 36.6 ms | 3.44× slower |
| Node | 37.7 ms | 31.8 ms | 43.1 ms | 4.36× slower |

<details>
<summary>Environment</summary>

| Detail | Value |
| ------ | ----- |
| Hardware | AMD Ryzen 9 5900X, 64 GB RAM, 12 cores / 24 threads |
| OS | Ubuntu 24.04.4 LTS (x86_64, Linux 7.0.3) |
| Ant (Fork) | 12.2.1d8040ee (Local build) |
| Ant (Upstream) | 12.2.1d8040ee.1 |
| Node | 22.14.0 |
| Bun | 1.2.2 |
| Deno | 2.2.3 |

</details>

## Building Ant

See [BUILDING.md](BUILDING.md) for instructions on how to build Ant from source and a list of supported platforms.

## Security

For information on reporting security vulnerabilities in Ant, see [SECURITY.md](SECURITY.md).

## Community

- [Discord](http://discord.gg/CH7YSjWGzY)
- [Blog: Working was the beginning](https://themackabu.dev/blog/ant-part-two)
- [DeepWiki: Ant internals](https://deepwiki.com/theMackabu/ant)
