# Architecture Decision Log

Durable record of architectural choices, the trade-offs weighed, and the
options deliberately left on the table. Each entry is self-contained: an agent
picking up a deferred option should be able to implement it from the entry
alone, without re-deriving the analysis.

## Format

Files are `####-kebab-name.md`, numbered in the order decided. Each entry
carries a `Name` and the `Hash` of the commit the work was based on, so a
later reader can diff against the exact tree the measurements were taken on.

Required sections:

- **Status** — `accepted`, `rejected`, `deferred`, or `superseded`
- **Context** — what forced the decision
- **Decision** — what was chosen
- **Measurement** — real numbers, on named hardware/benchmark. Estimates are
  labelled as estimates and never presented as results.
- **Options considered** — including rejected ones, with enough implementation
  detail to revisit
- **Consequences** — what this costs or constrains later

## Rules

- Measure, don't estimate. An entry claiming a win states how it was measured
  and what the baseline was. If a change measured flat, that is the result and
  the change gets reverted — see `0005`.
- Record rejected options in as much detail as accepted ones. The value of this
  log is mostly in the paths not taken.
- Compliance is a gate, not a trade: tier 1 at 100%, no tier 2/3 regression.
  Entries state the compliance run that backs them.

## Index

| # | Name | Status |
|---|------|--------|
| [0001](0001-promise-combinator-native-slots.md) | Promise combinator bookkeeping in native slots | accepted |
| [0002](0002-iterator-result-interned-keys.md) | Iterator result objects use interned keys | accepted |
| [0005](0005-promise-state-free-list.md) | Promise state free list | rejected |
