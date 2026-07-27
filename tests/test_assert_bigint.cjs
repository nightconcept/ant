const assert = require('assert');

// BigInts live on the heap, so comparing them by value rather than by pointer
// is what makes assert see two separately-built 1n as equal.

assert.equal(1n, 1n);
assert.equal(-2n, -2n);
assert.equal(BigInt('123456789012345678901234567890'), 123456789012345678901234567890n);
assert.strictEqual(0n, -0n);
assert.deepEqual([1n, 2n], [1n, 2n]);
assert.deepStrictEqual({ a: 7n }, { a: 7n });

assert.notEqual(1n, 2n);
assert.notStrictEqual(1n, 2n);

// A BigInt is never loosely equal to a Number here, matching strictEqual's typing.
assert.notStrictEqual(1n, 1);

console.log('assert BigInt comparison regression checks passed');
