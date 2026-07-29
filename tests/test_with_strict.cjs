const assert = require('node:assert');
const { spawnSync } = require('node:child_process');

const source = '"use strict"; const obj = { x: 10 }; with (obj) { console.log(x); }';
const result = spawnSync(process.execPath, ['--no-color', '-e', source], { encoding: 'utf8' });

assert.notStrictEqual(result.status, 0, 'strict-mode with statement must fail to parse');
assert.match(result.stderr, /SyntaxError: with statement not allowed in strict mode/);

console.log('strict-mode with statement rejected');
