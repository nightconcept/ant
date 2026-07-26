const { promisify } = require('node:util');
const { execFile } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

async function main() {
  const execFileAsync = promisify(execFile);
  const cwd = path.join(__dirname, '..');

  const revParse = await execFileAsync(
    'git',
    ['rev-parse', '--show-toplevel'],
    { cwd, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }
  );

  if (!revParse || typeof revParse.stdout !== 'string') {
    throw new Error('expected rev-parse stdout string');
  }
  // `cwd` is the checkout root regardless of what the containing directory is
  // named (a linked worktree, for instance, need not be named "ant"), so
  // compare against its real path rather than assuming a directory name.
  const expectedToplevel = fs.realpathSync(cwd);
  const actualToplevel = fs.realpathSync(revParse.stdout.trim());
  if (actualToplevel !== expectedToplevel) {
    throw new Error(
      `unexpected rev-parse output: ${JSON.stringify(revParse.stdout)} (expected ${expectedToplevel})`
    );
  }

  const status = await execFileAsync(
    'git',
    ['status', '--porcelain=v1', '-z', '--untracked-files=normal'],
    { cwd, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }
  );

  if (!status || typeof status.stdout !== 'string') {
    throw new Error('expected status stdout string');
  }

  console.log('util.promisify(execFile) handles git with options');
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
