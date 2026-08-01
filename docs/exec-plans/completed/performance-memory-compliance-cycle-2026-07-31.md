# Performance, Memory, and Compliance Cycle (2026-07-31)

Status: completed
Last reviewed: 2026-07-31
Owner: theMackabu

## Goal

Improve Ant's closest-peer performance and memory position without regressing
the exact Tier 3 failing-test set. Spend the main effort on shared engine paths
that can improve both runtime cost and allocation pressure, while keeping a
smaller compliance lane for high-leverage semantic fixes outside the
unimplemented Temporal/Intl feature family.

## Baseline Findings

- Tier 1 and Tier 2 were at 100% in the checked-in compliance baseline.
- Tier 3 was 34,139/53,431 (63.9%) at `d75d49a4`.
- Temporal accounted for 6,632 of 19,292 Tier 3 failures. Excluding that absent
  subsystem, coverage was approximately 76.3%.
- Fresh diagnostics found Array Operations and Object Graph approximately 24%
  and 22% slower than the recorded benchmark, respectively. Both traced to
  repeated indexed-descriptor/prototype checks on dense array writes.

## Constraints

- Preserve the user's existing `bench/versions.json` edit.
- Do not promote dirty-tree or filtered measurements to checked-in baselines.
- Tier 1 must remain at 100%; Tier 2 and Tier 3 may have no newly failing test.
- Do not accept memory reductions that cross the benchmark speed gate.
- Prefer fixes to shared engine behavior over benchmark- or suite-specific
  shortcuts.
- Do not implement Temporal solely to increase the aggregate Tier 3 score.

## Completed Work

- Added a conservative per-shape indexed-property marker without increasing
  the shape structure size.
- Added a narrow indexed-property epoch so unrelated shape mutations no longer
  invalidate the Array prototype safety cache.
- Avoided generic property lookup for ordinary dense writes when the receiver
  shape cannot contain an indexed descriptor.
- Corrected inherited indexed reads and `HasProperty` beyond an array's own
  length.
- Corrected sparse indexed-property deletion when array length shrinks,
  including descending deletion and non-configurable-element handling.
- Added focused regression coverage for cache invalidation, inherited indexed
  properties, and the maximum valid array index.

## Decision Log

- 2026-07-31: Allocated the cycle approximately 70% to performance/memory and
  30% to targeted compliance work.
- 2026-07-31: Treated txiki.js as the closest-peer size/memory comparison and
  Node as the throughput ceiling, while preserving Ant's startup advantage.
- 2026-07-31: Rejected the existing 1 MiB GC pool floor as-is because it slowed
  Object Graph by 9.6%.
- 2026-07-31: Kept RSS neutral in this cycle and recovered the identified speed
  regression before pursuing riskier GC tuning.

## Validation Results

- Direct paired diagnostics recovered approximately 16% on Array Operations
  and 17% on Object Graph versus the pre-change dirty-tree measurements.
- Full `just bench-diff`: no regression past the 6% time, 10% RSS, or 25%
  binary-size gates. Array Operations improved 2.0% and Object Graph improved
  2.6% against the recorded benchmark; peak RSS was effectively unchanged.
- Tier 1: 1/1, 100%.
- Tier 2: 468/468, 100%, with zero exact-set regressions.
- Tier 3: 34,196/53,431, 64.0%, with zero newly failing and 57 newly passing
  tests against `d75d49a4`.
- Spec suite: 3,672 tests across 98 files, zero failures.
- Focused runtime tests, `just preflight`, `just knowledge`, build, and
  whitespace validation passed.

All compliance and benchmark manifests were generated from a dirty tree and
were therefore used for validation only, not promoted as checked-in baselines.

## Follow-Ups

- Refresh the checked-in benchmark and compliance baselines from a clean,
  reproducible commit after review.
- Continue memory work by profiling the high-RSS Async, Object Graph, and Web
  Streams workloads; require speed-neutral changes.
- Keep the weekly exact-set Tier 3 gate in place and prefer shared semantic
  fixes over aggregate-score work on the absent Temporal subsystem.
