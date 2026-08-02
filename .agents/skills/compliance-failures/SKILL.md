---
name: compliance-failures
description: Analyze Ant WinterTC, Regression, or Test262 failures and rank actionable failure groups from large logs.
---

# Compliance Failure Analysis

Ant writes one log and one JSON manifest for each named suite:

```text
.deps/compliance/logs/<suite>_<timestamp>_<revision>.log
.deps/compliance/logs/<suite>_<timestamp>_<revision>.json
```

The suite IDs are `wintertc`, `regression`, and `test262`.

## Start With the Manifest

Read the stable manifest link before you read a log:

```bash
python3 -m json.tool .deps/compliance/logs/test262-latest.json
python3 scripts/compliance_baseline.py diff .deps/compliance/logs/test262-latest.json
```

The manifest contains totals, category totals, and sorted failing-test names.
Use the log only when you need captured output.

## Log Format

The runner writes one block for each failure:

```text
[FAIL] <test name> (<time>ms)
--- output ---
<captured output>
--------------
```

## Commands

Show an overview of the latest logs:

```bash
python3 .agents/skills/compliance-failures/parse_failures.py
```

Group Test262 failures by category or message:

```bash
python3 .agents/skills/compliance-failures/parse_failures.py --suite test262 --group category
python3 .agents/skills/compliance-failures/parse_failures.py --suite test262 --group message
```

List filtered failures:

```bash
python3 .agents/skills/compliance-failures/parse_failures.py --suite wintertc --filter streams
python3 .agents/skills/compliance-failures/parse_failures.py --suite regression --list
```

Produce JSON output:

```bash
python3 .agents/skills/compliance-failures/parse_failures.py --suite test262 --json
```

Use `--log <path>` for a historical numeric log. Use `--require-current` to
reject a dirty, unknown, or superseded revision.

## Triage Rules

Fix harness failures before runtime failures. A missing META dependency, an
absent completion marker, or an unsupported host global can inflate failures.

Group repeated error messages before you select runtime work. One root cause
can affect many tests.

Keep required WinterTC behavior visible. Do not classify an Ant behavior failure
as an exclusion.

Add an Ant Regression test for each corrected external conformance failure.

## Maintenance

If the log block format changes, update `FAIL_RE`, `ERR_RE`, and `DASHES_RE` in
`parse_failures.py`. Then make sure that the `Unknown` error count stays small.
