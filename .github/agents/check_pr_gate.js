#!/usr/bin/env node

const env = process.env;
const failures = [];

function requireSuccess(label, result) {
  if (result !== "success") {
    failures.push(`${label} concluded '${result}', expected 'success'`);
  }
}

function requireSkippedOrSuccess(label, result) {
  if (result !== "skipped" && result !== "success") {
    failures.push(
      `${label} concluded '${result}', expected 'skipped' or 'success'`,
    );
  }
}

requireSuccess("classify", env.CLASSIFY_RESULT);
requireSuccess("repository", env.REPO_RESULT);

if (env.WORKFLOW_CHANGED === "true") {
  requireSuccess("workflow-lint", env.WORKFLOW_RESULT);
} else {
  requireSkippedOrSuccess("workflow-lint", env.WORKFLOW_RESULT);
}

if (env.BUILD_CHANGED === "true") {
  requireSuccess("build-and-test", env.BUILD_RESULT);
  requireSuccess("wintertc", env.WINTERTC_RESULT);
  requireSuccess("regression", env.REGRESSION_RESULT);
} else {
  requireSkippedOrSuccess("build-and-test", env.BUILD_RESULT);
  requireSkippedOrSuccess("wintertc", env.WINTERTC_RESULT);
  requireSkippedOrSuccess("regression", env.REGRESSION_RESULT);
}

if (env.RUNTIME_CHANGED === "true" || env.EVENT_NAME === "merge_group") {
  requireSuccess("test262", env.TEST262_RESULT);
} else {
  requireSkippedOrSuccess("test262", env.TEST262_RESULT);
}

if (failures.length > 0) {
  for (const failure of failures) {
    process.stderr.write(`PR gate: ${failure}\n`);
  }
  process.exit(1);
}

process.stdout.write("All classified PR requirements passed.\n");
