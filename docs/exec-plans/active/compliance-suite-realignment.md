# Execution Plan: Compliance Suite Realignment

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

**Research:** `docs/repo/compliance.md` and the Ecma TC55 Minimum Common Web API specification
**Issue/Ref:** none

## Goal

Replace the misleading numeric compliance tiers with three named suites:
`wintertc`, `regression`, and `test262`. WinterTC will execute an intentional,
pinned Web Platform Tests subset plus a local API-surface contract. Ant
Regression will execute both internal test families with per-file results.
Test262 will retain the complete pinned ECMA-262 corpus. CI and baselines will
compare exact failing-test sets by suite name. The repository will not claim
WinterTC conformance until the complete required API surface and the applicable
WPT set pass.

## Worker Context Bootstrap

Every worker agent must execute these reads at session start, before any implementation:

1. Read `AGENTS.md` — entry point and repo map.
2. Read `docs/repo/index.md` — knowledge hub and system references.
3. Read `docs/exec-plans/tech-debt.md` — technical debt tracker.
4. Read `docs/repo/compliance.md` and `docs/repo/testing.md`.
5. Read this plan in full.

Do not proceed to implementation until these files are loaded.

## Naming Decision

| Stable ID | Display name | Purpose |
| --- | --- | --- |
| `wintertc` | WinterTC | Minimum Common Web API surface and applicable WPT behavior |
| `regression` | Ant Regression | Ant-owned language, engine, runtime, module, and regression tests |
| `test262` | Test262 | Complete pinned TC39 ECMAScript conformance corpus |

Use `Ant Regression`, not `Node Compatibility`. The current `tests/` directory
contains JIT, GC, parser, sandbox, Wasm, web API, and Node API coverage, so a
Node-specific name materially misdescribes it. Do not retain tier-number aliases
in commands, filenames, manifests, CI job names, documentation, dashboards, or
skill guidance; this is a deliberate vocabulary migration.

## Approach

Use a schema-level suite ID rather than deriving identity from a display name.
Version the manifest and checked-in baseline schema from 1 to 2, replace the
integer `tier` field and `tiers` map with a string `suite_id` field and `suites`
map, and make log/latest filenames use the suite ID.

Pin WPT in `.github/versions.json`, using commit
`4a5810a124fa0523dd2494996bf1542d4b67f394` for the first reproducible corpus.
The WinterTC runner must not copy Kawa's recursive `*.js` directory scan. It
will discover only `.any.js` tests from a checked-in allowlist of WinterTC API
families, resolve WPT `// META: script=` dependencies, prepend
`resources/testharness.js`, and report each source test independently. Tests
which require a browser Window, WPT HTTP server, special host names, TLS, or
unsupported harness globals must be classified explicitly instead of silently
passing, being selected accidentally, or being treated as engine failures.

The initial shell-compatible WPT manifest covers these normative families:

- DOM abort and events: `dom/abort/` and applicable `dom/events/` `.any.js` tests.
- Console: `console/` `.any.js` tests.
- Encoding: `encoding/` `.any.js` tests.
- File and Blob: applicable `FileAPI/` `.any.js` tests.
- Compression: `compression/` `.any.js` tests.
- Streams: `streams/` `.any.js` tests.
- URL and URLPattern: `url/` and `urlpattern/` `.any.js` tests.
- High-resolution time: `hr-time/` `.any.js` tests.
- Web Crypto: `WebCryptoAPI/` `.any.js` tests.
- WebAssembly JavaScript APIs: applicable `wasm/jsapi/` `.any.js` tests.
- Fetch value objects: shell-compatible Headers, Request, and Response tests
  under `fetch/api/`; network-backed fetch tests are added with the WPT server
  phase below.

Keep the exact include and exclude globs in
`tests/wintertc/wpt-manifest.json`. Each exclusion must include a machine-readable
reason (`window-only`, `server-required`, `unsupported-harness`, or
`outside-wintertc`) so that excluded coverage is visible and reviewable.

## Phases

### Phase 1: Named Suite Model and Schema

**Objective:** Remove numeric tier identity from the reusable compliance
infrastructure and give every artifact a stable suite ID.

**Depends on:** none

**Files to change:**

- `scripts/compliance_common.py` — accept `suite_id` explicitly in
  `SummaryTracker`; emit schema 2 manifests and `<suite>-latest.json` links.
- `scripts/compliance_baseline.py` — key baselines by suite ID and report named
  suites in validation and diffs.
- `scripts/run_compliance.py` — replace `--tier` with
  `--suite wintertc|regression|test262|all`.
- `scripts/dashboard.py` — render named suites.
- `docs/repo/compliance-baseline.json` — migrate to schema 2 and named keys.
- `tests/test_compliance_baseline.py` — exercise string suite IDs, schema
  validation, missing named baselines, filtered diffs, and exact revisions.

**Implementation notes:**

The new manifest identity is:

```json
{
  "schema_version": 2,
  "suite_id": "wintertc",
  "suite": "WinterTC"
}
```

Reject schema 1 current-run manifests with an actionable migration error. The
baseline reader may translate a trusted schema 1 base-branch baseline in memory
for one migration window: old Tier 2 maps to `regression`, old Tier 3 maps to
`test262`, and old Tier 1 has no mapping because its aggregate internal-spec
result is not WinterTC evidence. Never write schema 1 or persist the translated
form. Remove this read-only bridge after schema 2 has landed on `main`. Do not
infer an ID from `suite`. Preserve revision, filter, totals, categories, and
exact failing-test lists unchanged.

**Verification:**

```bash
python3 -m unittest tests.test_compliance_baseline
python3 -m py_compile scripts/compliance_common.py scripts/compliance_baseline.py scripts/run_compliance.py scripts/dashboard.py
```

**Status:** [x] complete

### Phase 2: Real WinterTC Runner

**Objective:** Replace the current mislabeled internal-spec invocation with a
pinned, per-test WinterTC/WPT runner.

**Depends on:** Phase 1

**Files to change:**

- `.github/versions.json` — add the WPT commit pin.
- `scripts/run_compliance_wintertc.py` — discover, prepare, execute, and record
  the WinterTC suite.
- `scripts/compliance_common.py` — add pinned WPT checkout, WPT metadata/script
  resolution, testharness completion handling, unique in-place scratch files,
  timeout handling, and stale scratch cleanup.
- `tests/wintertc/api-surface.js` — assert every global interface, method, and
  property required by the current TC55 Minimum Common Web API snapshot.
- `tests/wintertc/wpt-manifest.json` — checked-in WPT selection and explained
  exclusions.
- `tests/test_wintertc_runner.py` — unit tests for manifest selection,
  duplicate removal, META dependency resolution, classification, scratch
  cleanup, and an empty-selection failure.
- Remove `scripts/run_compliance_tier1.py` after its callers move.

**Implementation notes:**

Run the local API-surface contract as one named test and every WPT source file
as its own named test. A WPT test passes only after the testharness completion
callback reports all subtests complete and successful. Process exit zero
without harness completion is a harness failure, not a pass. Scratch files live
beside their source so relative imports and META scripts resolve, use a unique
sequence per test, and are removed in `finally` plus start/end sweeps.

Support `--filter`, `--limit`, `--list`, `--log`, and `--log-fail`. A full run
must fail closed if the pinned checkout cannot be obtained, the selection is
empty, a manifest path matches no files, a META dependency is missing, or a
selected test cannot be classified. Initial failures are allowed in the
checked-in baseline but regressions from a passing test are not; the final
WinterTC release bar becomes 100% only in Phase 6.

**Verification:**

```bash
python3 -m unittest tests.test_wintertc_runner
python3 scripts/run_compliance_wintertc.py --list
python3 scripts/run_compliance_wintertc.py --filter url --limit 10 --log-fail
```

**Status:** [x] complete

### Phase 3: Ant Regression Suite

**Objective:** Put all Ant-owned regression coverage behind one accurately
named suite with per-file baseline entries.

**Depends on:** Phase 1

**Files to change:**

- `scripts/run_compliance_regression.py` — run all top-level
  `tests/test_*.{cjs,js,mjs}` files and every selectable `examples/spec/*.js`
  spec file independently.
- `examples/spec/run.js` — only if needed, expose a machine-readable listing or
  focused-file entrypoint without changing test semantics.
- `tests/test_compliance_suites.py` — verify discovery, exclusions, category
  naming, filters, and that both internal roots participate.
- Remove `scripts/run_compliance_tier2.py` after its callers move.

**Implementation notes:**

Do not record `examples/spec/run.js --all` as one aggregate test. Preserve its
in-process full-suite command for developer use, but the compliance runner must
record each of the 98 spec files independently. Retain the existing top-level
`test_` convention and explicitly document that nested fixtures/support files
are excluded.

**Verification:**

```bash
python3 -m unittest tests.test_compliance_suites
python3 scripts/run_compliance_regression.py --filter url --log-fail
./build/ant examples/spec/run.js --all
```

**Status:** [x] complete

### Phase 4: Test262 Rename

**Objective:** Preserve the current pinned Test262 behavior under its actual
name and remove unsupported claims about WPT/framework coverage.

**Depends on:** Phase 1

**Files to change:**

- Rename `scripts/run_compliance_tier3.py` to
  `scripts/run_compliance_test262.py` and rename suite/log/category text.
- `scripts/compliance_common.py` — remove tier-number smoke manifests and keep
  Test262 helpers under Test262 terminology.
- `tests/test_compliance_suites.py` — verify Test262 selection and suite ID.

**Implementation notes:**

Keep the existing `.github/versions.json` Test262 pin and in-place unique
scratch-file invariant. The three advanced local spec files currently injected
into Tier 3 move to Ant Regression; Test262 contains only Test262. Remove the
unused `--all-test262` orchestration flag if the runner already treats a normal
unfiltered run as complete.

**Verification:**

```bash
python3 -m unittest tests.test_compliance_suites
python3 scripts/run_compliance_test262.py --filter built-ins/Array/prototype/map --limit 20 --log-fail
```

**Status:** [x] complete

### Phase 5: Commands, CI, Baselines, and Documentation

**Objective:** Make named suites the only vocabulary exposed to developers,
agents, dashboards, baselines, releases, and CI.

**Depends on:** Phases 2, 3, and 4

**Files to change:**

- `justfile` — provide `compliance-wintertc`, `compliance-regression`,
  `compliance-test262`, and matching `update`/`diff` recipes; remove all `t1`,
  `t2`, and `t3` recipes.
- `.github/workflows/*.yml` and `.github/agents/check_pr_gate.js` — rename jobs,
  outputs, environment variables, artifact names, and required-result logic.
- `tests/test_pr_gate.py` — assert named-suite gate behavior.
- `bench/compliance*.py` and `bench/compliance_common.py` — use named suite
  modules, IDs, output, and snapshot keys. Remove their divergent hand-picked
  tier corpora and call the same discovery/selection functions as the ant-only
  runners so dashboard comparisons measure the same suites.
- `.agents/skills/compliance-failures/` — select named logs/manifests and update
  user-facing guidance; keep explicit `--log` parsing of historical numeric
  filenames while changing automatic discovery to suite IDs.
- `scripts/sync_upstream.py` — replace Tier 3 instructions with Test262 names
  while preserving the shared pinned checkout behavior.
- `docs/repo/compliance.md`, `docs/repo/testing.md`, `AGENTS.md`, and relevant
  completed plans — update current operational statements; preserve historical
  text only where clearly marked as historical.
- `ARCHITECTURE.md` — replace the nonexistent `tools/wpt/` reference with the
  actual named WinterTC harness and manifest paths.
- `docs/repo/compliance-runtimes-baseline.json` — migrate snapshot labels.
- `docs/repo/compliance-baseline.json` — seed named Regression from a clean full
  run; seed WinterTC and Test262 only from clean, pinned, full-corpus runs.

**Implementation notes:**

The public commands are:

```text
just compliance --suite wintertc|regression|test262|all
just compliance-wintertc
just compliance-regression
just compliance-test262
just compliance-update-<suite>
just compliance-diff-<suite>
```

CI build jobs run WinterTC and Ant Regression. Until WinterTC reaches 100%, CI
must preserve the runner's manifest even when individual tests fail and then
apply an exact failing-set comparison; it must not ignore the runner without a
successful baseline diff. Once the checked-in WinterTC baseline has zero
failures, the same exact-set gate also enforces the 100% bar. Runtime pull
requests and merge groups additionally run Test262 exact-set comparison. The
weekly workflow and artifact become `test262-weekly` and
`test262-compliance-main`. Release gating uses WinterTC plus Ant Regression.

**Verification:**

```bash
python3 -m unittest tests.test_compliance_baseline tests.test_compliance_suites tests.test_wintertc_runner tests.test_pr_gate
just knowledge
just structure
just validate_changes
rg -n 'tier[ _-]?[123]|Tier [123]|compliance-t[123]|TIER[123]' --glob '!docs/exec-plans/completed/**' --glob '!build/**' --glob '!vendor/**'
```

The final `rg` command must return no live operational references. Historical
completed plans may retain old names only when changing them would falsify the
record.

**Status:** [x] complete

### Phase 6: Close WinterTC Compliance Gaps

**Objective:** Reach and maintain 100% of the selected applicable WPT set and
the full TC55-required API-surface contract, without hiding failures through
exclusions.

**Depends on:** Phase 5

**Files to change:**

- `src/`, `include/`, and `tests/` — focused engine/runtime fixes, one root cause
  per change, each with an Ant regression test.
- `tests/wintertc/wpt-manifest.json` — remove temporary
  `unsupported-harness` exclusions only when harness support lands.
- `docs/repo/compliance.md` — maintain a coverage matrix mapping every TC55
  interface/property to WPT paths, local contract checks, and documented
  deviations.
- `docs/repo/compliance-baseline.json` — promote clean full runs after review.

**Implementation notes:**

Start from a clean full WinterTC manifest. Classify every failure as
`harness`, `missing-api`, `behavior`, `server-required`, or `not-applicable`.
Fix harness failures before runtime failures. Then work normative families in
this order: API surface and globals; URL/encoding/console/time; events and
abort; streams/compression; Blob/File/FormData and fetch value objects;
WebCrypto; WebAssembly; network-backed fetch. For each root cause, add a focused
`tests/test_*.cjs` regression and diff the affected WinterTC slice before a full
run.

An exclusion is acceptable only when the test exercises browser-only behavior
outside TC55, or while a separately tracked harness/server capability is
missing. Unsupported Ant behavior required by TC55 must remain a visible
failure. A green selected subset alone must never be described as full
WinterTC conformance.

Add WPT server-backed execution for fetch after shell-compatible tests are
stable: start the pinned WPT server on allocated local ports, wait for its
health endpoint, run the explicit fetch manifest with required host mapping,
and terminate the server in `finally`. CI must cache only the pinned checkout,
not generated results.

**Verification:**

```bash
just compliance-diff-wintertc
python3 scripts/compliance_baseline.py diff .deps/compliance/logs/wintertc-latest.json --require-baseline --require-full
just compliance-regression
```

Done means the full clean WinterTC run is 100%, every TC55-required API has a
coverage-matrix entry, all exclusions are justified as outside the standard or
harness-only, and Ant Regression has no failing-set regression.

**Status:** [ ] in progress; the exact failure set is baselined

## Testing Strategy

Unit-test discovery, metadata parsing, schema validation, and gate routing
without network access. Use focused pinned-WPT slices to validate the WPT
harness. Use full clean suite runs to create baselines and exact-set diffs.
Every runtime behavior fixed from WPT must also get an Ant Regression test so
external corpus changes cannot remove the regression net.

Do not treat a raw process exit code as sufficient WPT evidence. Require
testharness completion and capture subtest names/messages. Do not update a
baseline from a dirty tree, partial filter, wrong commit, or different WPT pin.

## Rollout / Integration Notes

This intentionally breaks old tier-number commands and manifest consumers.
Land the schema, runners, CI callers, tests, and docs together so no protected
workflow refers to removed commands. Preserve old generated `.deps/` logs as
local artifacts, but ignore them for named-suite baseline comparisons.

Seed the Ant Regression baseline first because it describes existing local
coverage. Seed WinterTC after reviewing the initial failure classification.
Seed Test262 from a clean complete run using the existing Test262 pin. Do not
fabricate named baselines by merely changing keys on old aggregate Tier 1 data.

## Known Risks

- Many WPT tests assume browser globals or the WPT HTTP server. Explicit
  classification and allowlisted `.any.js` discovery prevents harness noise
  from being mistaken for Ant non-conformance.
- The initial WPT run can be large and slow. Pinning, filtering, per-test
  timeouts, and exact manifests keep it reproducible and debuggable.
- Renaming CI jobs can change required status-check names. Update the GitHub
  ruleset in the same rollout if it names jobs below the aggregate `PR Gate`.
- Existing baseline history is keyed by integers. Schema 2 intentionally starts
  new named histories rather than presenting incomparable data as continuous.
- WinterTC conformance also requires ECMA-262. The WinterTC bar therefore
  cannot support an unconditional conformance claim while required Test262
  failures remain; document the distinction between Web API coverage and full
  standard conformance.

## Out of Scope

- Making all Test262 tests pass.
- Running browser-only WPT rendering, DOM tree, CSS, or navigation tests.
- General Node.js upstream compatibility testing; Ant-owned Node API regression
  tests remain part of Ant Regression.
- Framework and npm ecosystem test suites. Add a separately named ecosystem
  suite later if those are introduced.
- Preserving deprecated numeric tier commands or schema-1 baseline compatibility.

## Progress Log

- 2026-08-01: Plan created after comparing Ant's runners with Kawa's WPT-based
  WinterTC runner. Chose the names WinterTC, Ant Regression, and Test262; chose
  a pinned allowlist rather than Kawa's unpinned recursive JavaScript scan.
- 2026-08-01: Implemented schema 2, the three named runners, shared
  multi-runtime discovery, named CI gates, commands, dashboards, failure
  analysis, and documentation through red-green tests.
- 2026-08-01: Generated clean full-suite baselines at commit `2916d9fc`.
  Ant Regression passed 569/569. Test262 passed 34,527/53,428. WinterTC passed
  78/436. The 358 WinterTC failures remain visible for Phase 6; the largest
  groups are WebCrypto, WebAssembly, Streams, and Encoding.
