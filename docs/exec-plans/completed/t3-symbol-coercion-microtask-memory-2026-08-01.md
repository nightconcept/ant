# Tier 3 Symbol Coercion and Microtask Memory (2026-08-01)

Status: completed
Last reviewed: 2026-08-01
Owner: Core Engineering

## Goal

Use the follow-up allocation from the performance, memory, and compliance
cycle on two bounded root causes: a non-Temporal Tier 3 coercion cluster and
the Web Streams memory outlier. Preserve Tier 1 and Tier 2 at 100%, and do not
regress the exact Tier 3 failing-test set.

## Completed Work

- Made numeric coercion of Symbols throw `TypeError`, including Symbols
  produced by object-to-primitive conversion.
- Applied `ToIntegerOrInfinity`-style coercion and relative-index clamping to
  `Array.prototype.fill` and `Array.prototype.copyWithin`.
- Applied numeric length coercion to generic and proxy-backed array method
  receivers, with exception propagation and length clamping.
- Recycled operation-local property-reference handles at each microtask job
  boundary. Promise-heavy workloads can otherwise grow the table continuously
  because they may not encounter a bytecode backedge for a long time.
- Added focused runtime tests for Symbol coercion, array argument coercion,
  explicit `undefined` end arguments, and bounded property-reference storage
  across 20,000 microtasks.

## Decision Log

- 2026-08-01: Selected the Symbol-to-number cluster because a 29-test focused
  Test262 slice exposed one shared coercion failure across several Array
  builtins; it improved from 2/29 to 13/29 with no newly failing tests.
- 2026-08-01: Reset only the property-reference handle count, not its backing
  allocation. These handles are operation-local and already recycle at VM
  backedges, so the microtask boundary extends the existing lifetime rule to
  promise-driven execution without changing object lifetime or GC roots.
- 2026-08-01: Kept dirty-tree compliance manifests as validation evidence only;
  they are not suitable for baseline promotion.

## Validation Results

- Web Streams Pipeline peak RSS, three runs before: 72,220 KiB each. After:
  28,172 KiB median (28,084-28,300 KiB), approximately 61% lower. Elapsed time
  remained neutral-to-better (0.31-0.32 seconds before, 0.28-0.30 after).
- Full Tier 3: 34,361/53,431 passed (64.3%), with zero newly failing and 222
  newly passing tests against the checked-in `d75d49a4` baseline. The preceding
  full dirty-tree run passed 34,196 tests.
- Tier 1: 1/1 passed (100%), including 3,672/3,672 spec assertions across 98
  files.
- Tier 2: 470/470 passed (100%). The count increased from 468 because the two
  new repository regression files are part of this local compatibility suite.
- Focused Symbol, microtask recycling, and timer tests passed.
- Build, `just preflight`, and whitespace validation passed.

## Follow-Ups

- Refresh the compliance baseline from a clean commit after review.
- Continue non-Temporal Tier 3 work by grouping the remaining coercion failures
  rather than selecting isolated tests.
- Apply the same allocation-lifetime audit to other promise-heavy benchmarks
  before changing GC pool sizing.
