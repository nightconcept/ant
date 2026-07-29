const assert = require('node:assert');
const { spawnSync } = require('node:child_process');

const source = `
function level3() {
  throw new Error("error from level3");
}
function level2() {
  level3();
}
function level1() {
  level2();
}
level1();
`;

const result = spawnSync(process.execPath, ['--no-color', '-e', source], { encoding: 'utf8' });
assert.notStrictEqual(result.status, 0, 'uncaught throw must fail the child process');
assert.match(result.stderr, /Error: error from level3/);
assert.match(result.stderr, /at level3/);
assert.match(result.stderr, /at level2/);
assert.match(result.stderr, /at level1/);

const primitive = spawnSync(
  process.execPath,
  ['--no-color', '-e', 'throw "primitive failure";'],
  { encoding: 'utf8' }
);
assert.notStrictEqual(primitive.status, 0, 'uncaught primitive throw must fail the child process');
assert.match(primitive.stderr, /primitive failure/);

console.log('uncaught throw includes stack frames');
