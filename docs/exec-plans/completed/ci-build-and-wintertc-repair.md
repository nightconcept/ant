# CI Build and WinterTC Repair

Status: completed
Completed: 2026-07-26

## Problem

All six build jobs in CI failed while configuring MIR. The wrap pointed at the
intended `nightconcept/mir` repository but contained a nonexistent commit SHA:
`c932c4784e2aed0d1fa7eab3c2d4fb21a6869766`. Existing local vendor caches hid
the broken fresh-checkout path. The standalone Tier 1 job also configured Ant
without installing Zig, so it failed before running compliance tests.

## Decision

- Pin MIR to the actual `nightconcept/mir` `dev` commit
  `c932c478136948f9e5f5e8a23fa1f9609fad6a54`.
- Rename the platform matrix to `Build and Test` and run the Tier 1 WinterTC
  suite as the `WinterTC Tests` step of the Linux glibc x64 matrix entry.
- Remove macOS x64 from the automatic branch matrices while retaining the
  target configuration for explicit manual builds.
- Install Zig in the main/upstream compliance-benchmarking jobs, which still
  configure their own independent build trees.

## Validation

- Confirmed the corrected MIR commit exists and is the current `dev` ref.
- Ran the repository knowledge, structure, and validation-router checks.
- Ran `git diff --check`.
- A local compile was unavailable because Meson is not installed in this
  Windows environment. CI remains the authoritative clean multi-platform
  validation of the corrected dependency fetch.
