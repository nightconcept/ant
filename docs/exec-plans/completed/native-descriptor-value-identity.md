# Native Descriptor Value Identity

Status: completed
Last reviewed: 2026-07-29
Owner: Core Engineering

## Goal

Make property descriptors preserve the identity of native function values,
correcting the shared cause of 141 Test262 assertions without adding memory or
runtime overhead.

## Scope

- Correct `Object.getOwnPropertyDescriptor` for data properties whose stored
  value uses Ant's lightweight `T_CFUNC` representation.
- Add a focused runtime regression test for descriptor value identity.
- Measure the exact Test262 slice before and after the change.

## Constraints

- Do not change equality semantics or ordinary property lookup hot paths.
- Do not allocate a heap function object merely to construct a descriptor.
- Preserve native function names, lengths, property attributes, and promotion
  behavior.
- Keep tier 1 at 100% and introduce no tier 2 or tier 3 regression.

## Task List

1. Record a current clean baseline for the affected Test262 slice.
2. Return the stored data-property value unchanged in the descriptor object.
3. Add runtime coverage across native methods from multiple builtins.
4. Rebuild and rerun focused runtime and Test262 tests.
5. Run preflight, tier 1, the full spec suite, and performance comparison.

## Decision Log

- 2026-07-29: The current `dev` baseline for
  `built-ins/Object/getOwnPropertyDescriptor/15.2.3.3-4` is 45/239 passing.
  Exactly 141 of its 194 failures compare a descriptor value with the native
  function stored on the described object.
- 2026-07-29: Preserve the stored value through `js_set_exact`. The prior
  promotion creates a distinct heap representation and allocates on a
  reflective read. Changing equality would add work to a hot engine operation
  and would mask the descriptor's failure to return the actual stored value.
- 2026-07-29: The focused result is 139/239 passing, a gain of 94 tests with
  zero newly failing tests. All 141 identity assertions now pass; 47 of those
  tests continue to an unrelated pre-existing enumerable-attribute failure.

## Validation Status

- Baseline focused Test262 slice: 45/239 passed, 194 failed.
  Manifest:
  `.deps/compliance/logs/tier3_20260729_231559_50606b43.json`.
- Final runtime reproduction:
  `Object.getOwnPropertyDescriptor(Math, "floor").value === Math.floor` is
  true after the fix.
- Final focused Test262 slice: 139/239 passed, 100 failed.
  Manifest:
  `.deps/compliance/logs/tier3_20260729_231923_50606b43-dirty.json`.
- Broader `built-ins/Object` Test262 slice: 2,751/3,414 passed, 663
  failed; 95 newly passing and zero newly failing tests against the checked-in
  baseline. Manifest:
  `.deps/compliance/logs/tier3_20260729_232417_50606b43-dirty.json`.
- Tier 1: 1/1 passed (100%), including 3,672/3,672 spec assertions across
  98 files. Manifest:
  `.deps/compliance/logs/tier1_20260729_232146_50606b43-dirty.json`.
- Tier 2: 466/466 passed (100%). Manifest:
  `.deps/compliance/logs/tier2_20260729_232319_50606b43-dirty.json`.
- Focused runtime tests and `just preflight`: passed.
- `just bench-fast-diff`: no regression past the time, RSS, or binary-size
  thresholds. The implementation removes a promotion/allocation from the
  affected reflection path and changes no object layout or hot lookup path.

## Follow-ups

- The 47 tests that now advance to native-property enumerability failures are
  a separate registration-attribute issue and should be triaged independently.
