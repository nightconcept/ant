const assert = require('assert');

// assert.throws ignores its expected-error argument, so check the type here.
function throwsWith(fn, Ctor, label) {
  let caught = null;
  let threw = false;
  try { fn(); } catch (err) { threw = true; caught = err; }
  assert.ok(threw, label + ': expected a throw');
  assert.ok(caught instanceof Ctor, label + ': expected ' + Ctor.name + ', got ' + caught);
}

const TypedArray = Object.getPrototypeOf(Int8Array);

assert.equal(typeof TypedArray.prototype.findLast, 'function');
assert.equal(typeof TypedArray.prototype.findLastIndex, 'function');

const a = new Int16Array([1, 2, 3, 4, 5]);

assert.equal(a.findLast(x => x < 4), 3);
assert.equal(a.findLastIndex(x => x < 4), 2);
assert.equal(a.findLast(x => x > 9), undefined);
assert.equal(a.findLastIndex(x => x > 9), -1);

// Iterates from the end, and the predicate sees (value, index, array).
const seen = [];
a.findLast(function (value, index, array) {
  assert.equal(array, a);
  seen.push([value, index]);
  return false;
});
assert.deepEqual(seen, [[5, 4], [4, 3], [3, 2], [2, 1], [1, 0]]);

// thisArg.
const receiver = {};
a.findLastIndex(function () { assert.equal(this, receiver); return true; }, receiver);

// Empty arrays never call the predicate.
new Uint8Array(0).findLast(() => { throw new Error('called'); });
new Uint8Array(0).findLastIndex(() => { throw new Error('called'); });

// BigInt element types.
assert.equal(new BigInt64Array([1n, 2n]).findLast(x => x < 2n), 1n);
assert.equal(new BigUint64Array([1n, 2n]).findLastIndex(x => x < 2n), 0);

// A non-callable predicate is a TypeError, and an abrupt one propagates.
throwsWith(() => a.findLast(), TypeError, 'findLast without a predicate');
throwsWith(() => a.findLastIndex(null), TypeError, 'findLastIndex with null');
throwsWith(() => a.findLast(() => { throw new RangeError('boom'); }), RangeError, 'abrupt predicate');

console.log('%TypedArray%.prototype.findLast/findLastIndex regression checks passed');
