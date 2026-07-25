#!/usr/bin/env node

// TinyCC (../mc) mishandles _Thread_local variables with non-zero initializers
// (the initializer silently reads back as 0). Forbid the pattern so the engine
// stays compilable under ../mc. See TRANSITION_PLAN.md Phase 2 Item 4.

import fs from 'node:fs';
import path from 'node:path';
import { repoRoot } from './util_repo_root.js';

const SCAN_DIRS = ['src', 'include'];
const ZERO_INITIALIZERS = new Set(['0', 'false', 'null', 'nullptr', '{0}', '{ 0 }']);

function walk(dir, files) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
    } else if (/\.(c|h|cc|hh|hpp)$/u.test(entry.name)) {
      files.push(fullPath);
    }
  }
}

function main() {
  const files = [];
  for (const dir of SCAN_DIRS) {
    const fullDir = path.join(repoRoot, dir);
    if (fs.existsSync(fullDir)) walk(fullDir, files);
  }

  const errors = [];

  for (const filePath of files) {
    const text = fs.readFileSync(filePath, 'utf8');
    const lines = text.split(/\r?\n/);

    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (!line.includes('_Thread_local')) continue;

      const match = line.match(/_Thread_local[^;]*?=\s*([^;]+);/u);
      if (!match) continue;

      const initializer = match[1].trim();
      if (!ZERO_INITIALIZERS.has(initializer)) {
        const relPath = path.relative(repoRoot, filePath);
        errors.push(`${relPath}:${index + 1}: _Thread_local variable has a non-zero initializer (\`${initializer}\`); ../mc (TinyCC) reads this back as 0`);
      }
    }
  }

  if (errors.length > 0) {
    console.error('thread-local check failed:');
    for (const error of errors) {
      console.error(`  - ${error}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log('thread-local check passed');
}

main();
