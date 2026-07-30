# Execution Plan: Ant Compliance Test Suite Runner Scripts

Status: completed
Last reviewed: 2026-07-25  
Owner: Core Engineering  

This execution plan outlines the design and implementation of automated test runner scripts under `scripts/` to measure Ant's runtime compliance across 3 tiers (WinterTC/WPT, Node.js compatibility, and full Test262/Ecosystem conformance).

## 1. Overview & Objectives

To bring **Ant** to runtime compliance parity with Node.js, Bun, Deno, and Cloudflare Workers, we require automated test runner scripts in `scripts/`. These scripts orchestrate external standards suites (Test262, WPT, Node.js Core Tests) and Ant's internal spec suite, categorized into 3 distinct tiers.

## 2. Architecture & Script Map

- `scripts/run-compliance.sh`: Master CLI orchestrator
- `scripts/run-compliance-tier1.sh`: Tier 1 (WinterTC / Edge Baseline & Core JS)
- `scripts/run-compliance-tier2.sh`: Tier 2 (Node.js Compatibility Suite)
- `scripts/run-compliance-tier3.sh`: Tier 3 (Full Test262, Broad WPT & Frameworks)
- `scripts/lib/compliance-common.sh`: Shared helper functions (fetchers, logger, binary check)
- `scripts/lib/node-runner-shim.js`: JS harness shim for executing Node.js unit tests in Ant

## 3. Tier Breakdown

### Tier 1: WinterTC & Edge Baseline (`scripts/run-compliance-tier1.sh`)
- **Focus:** Fast, high-signal validation of edge APIs and standard JS language features (~1-3 mins).
- **Suites:**
  1. Ant Spec Suite (`./build/ant examples/spec/run.js --all`).
  2. WinterTC WPT subset (`fetch`, `streams`, `url`, `encoding`, `crypto`, `console`, `timers`, `blob`, `formdata`).
  3. Test262 core built-ins (`Array`, `Object`, `Promise`, `RegExp`, `Map`, `Set`, `Async/Await`).

### Tier 2: Node.js Compatibility Suite (`scripts/run-compliance-tier2.sh`)
- **Focus:** `node:*` core module compatibility for npm ecosystem readiness (~5-15 mins).
- **Suites:**
  - Node.js `test/parallel/` suites for `buffer`, `events`, `fs`, `stream`, `http`, `net`, `child_process`, `crypto`, `path`, `os`, `zlib`.

### Tier 3: Full Conformance & Framework Integration (`scripts/run-compliance-tier3.sh`)
- **Focus:** Complete engine-level conformance against V8/JSC and end-to-end real-world app validation (~30-60 mins).
- **Suites:**
  1. Full Test262 suite (50,000+ TC39 tests).
  2. Broad Web Platform Tests (WebSockets, Web Workers, WASM Web API).
  3. Real-World Framework integration tests (Hono, Express, Fastify, Zod, Vitest).

## 4. Implementation Steps

1. Create `scripts/lib/compliance-common.sh` and `scripts/run-compliance-tier1.sh`.
2. Build `scripts/lib/node-runner-shim.js` and `scripts/run-compliance-tier2.sh`.
3. Build `scripts/run-compliance-tier3.sh` and master `scripts/run-compliance.sh`.
4. Add `just compliance` target to `justfile` and wire into repo harness scripts.
