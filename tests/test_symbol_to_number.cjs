const assert = require('assert');

const symbol = Symbol('value');

assert.throws(() => Number(symbol), TypeError);
assert.throws(() => +symbol, TypeError);
assert.throws(() => -symbol, TypeError);
assert.throws(() => isNaN(symbol), TypeError);
assert.throws(() => isFinite(symbol), TypeError);

assert.throws(
  () => Array.prototype.includes.call({ length: symbol }, undefined),
  TypeError,
);
assert.throws(() => [1].includes(1, symbol), TypeError);
assert.throws(() => Array.prototype.find.call({ length: symbol }, () => true), TypeError);
assert.throws(() => [1, 2].fill(0, symbol), TypeError);
assert.throws(() => [1, 2].fill(0, 0, symbol), TypeError);
assert.throws(() => [1, 2].copyWithin(symbol, 0), TypeError);
assert.throws(() => [1, 2].copyWithin(0, symbol), TypeError);
assert.throws(() => [1, 2].copyWithin(0, 0, symbol), TypeError);

assert.deepStrictEqual([1, 2, 3].fill(0, '1', '2'), [1, 0, 3]);
assert.deepStrictEqual([1, 2, 3].copyWithin('1', '0', '1'), [1, 1, 3]);
assert.deepStrictEqual([1, 2, 3].fill(0, 1, undefined), [1, 0, 0]);
assert.deepStrictEqual([1, 2, 3].copyWithin(1, 0, undefined), [1, 1, 2]);

const boxed = {
  valueOf() {
    return symbol;
  },
};

assert.throws(() => Number(boxed), TypeError);
assert.throws(() => +boxed, TypeError);

console.log('symbol to number tests passed');
