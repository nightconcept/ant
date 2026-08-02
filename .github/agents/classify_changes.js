#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { repoRoot } from './util_repo_root.js';

function parseArgs(argv) {
  const options = { filesFrom: null, json: false, files: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--files-from') {
      options.filesFrom = argv[index + 1] || null;
      index += 1;
    } else if (arg === '--json') options.json = true;
    else options.files.push(arg);
  }
  return options;
}

function loadFiles(options) {
  if (!options.filesFrom) return options.files;
  return fs.readFileSync(path.resolve(repoRoot, options.filesFrom), 'utf8')
    .split(/\r?\n/u)
    .map(value => value.trim().replaceAll('\\', '/'))
    .filter(Boolean);
}

function isDocumentation(file) {
  return file === 'AGENTS.md' ||
    file === 'ARCHITECTURE.md' ||
    file === 'BUILDING.md' ||
    file === 'CONTRIBUTING.md' ||
    file === 'README.md' ||
    file.startsWith('docs/') ||
    file.endsWith('.md');
}

function isWorkflow(file) {
  return file.startsWith('.github/workflows/') ||
    file.startsWith('.github/actions/') ||
    file.startsWith('.github/agents/');
}

function isRuntime(file) {
  return file.startsWith('src/') ||
    file.startsWith('include/') ||
    file.startsWith('tests/') ||
    file.startsWith('examples/spec/') ||
    file.startsWith('tests/wintertc/');
}

function isPerformanceSensitive(file) {
  return file === 'src/ant.c' ||
    file === 'src/runtime.c' ||
    file === 'src/shapes.c' ||
    file.startsWith('src/silver/') ||
    file.startsWith('src/gc/') ||
    file.startsWith('src/modules/') ||
    file.startsWith('src/streams/') ||
    file.startsWith('src/http/') ||
    file.startsWith('src/net/') ||
    file.startsWith('include/');
}

function isKnownNonRuntime(file) {
  return isDocumentation(file) ||
    isWorkflow(file) ||
    file.startsWith('scripts/') ||
    file.startsWith('meson/') ||
    file.startsWith('packages/') ||
    file.startsWith('bench/') ||
    file.startsWith('vendor/') ||
    file === 'meson.build' ||
    file === 'justfile' ||
    file === '.gitignore';
}

function classify(files) {
  const unknown = files.filter(file => !isRuntime(file) && !isKnownNonRuntime(file));
  const conservativeFallback = files.length === 0 || unknown.length > 0;
  const docsOnly = files.length > 0 && files.every(isDocumentation);
  return {
    docs_only: docsOnly,
    workflow_changed: files.some(isWorkflow),
    build_changed: !docsOnly,
    runtime_changed: conservativeFallback || files.some(isRuntime),
    performance_sensitive: conservativeFallback || files.some(isPerformanceSensitive),
  };
}

const options = parseArgs(process.argv.slice(2));
const result = classify(loadFiles(options));
if (options.json) process.stdout.write(`${JSON.stringify(result)}\n`);
else for (const [key, value] of Object.entries(result)) {
  process.stdout.write(`${key}=${value}\n`);
}
