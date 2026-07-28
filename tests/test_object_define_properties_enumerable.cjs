const assert = require('node:assert');

// ObjectDefineProperties walks the props object's own *enumerable* keys and
// reads each descriptor with [[Get]], so non-enumerable entries are skipped
// and accessors are invoked.

const nonEnumerableValue = {};
Object.defineProperty(nonEnumerableValue, 'prop', { value: {}, enumerable: false });
assert.strictEqual(Object.create({}, nonEnumerableValue).hasOwnProperty('prop'), false);

let getterCalls = 0;
const nonEnumerableGetter = {};
Object.defineProperty(nonEnumerableGetter, 'prop', {
  get() { getterCalls++; return {}; },
  enumerable: false,
});
assert.strictEqual(Object.create({}, nonEnumerableGetter).hasOwnProperty('prop'), false);
assert.strictEqual(getterCalls, 0);

// An enumerable accessor is invoked exactly once, and its result is the
// descriptor.
getterCalls = 0;
const enumerableGetter = {};
Object.defineProperty(enumerableGetter, 'prop', {
  get() { getterCalls++; return { value: 42, enumerable: true }; },
  enumerable: true,
});
const fromGetter = Object.create({}, enumerableGetter);
assert.strictEqual(getterCalls, 1);
assert.strictEqual(fromGetter.prop, 42);

// Own properties of exotic objects (wrappers, arrays) are picked up.
const stringWrapper = new String('');
stringWrapper.prop = { value: 12, enumerable: true };
assert.strictEqual(Object.create({}, stringWrapper).prop, 12);

const arrayProps = [];
arrayProps.prop = { value: 'from array', enumerable: true };
assert.strictEqual(Object.create({}, arrayProps).prop, 'from array');

// Inherited properties of the props object are ignored.
const base = { inherited: { value: 1, enumerable: true } };
const derived = Object.create(base);
derived.own = { value: 2, enumerable: true };
const fromDerived = Object.create({}, derived);
assert.strictEqual(fromDerived.hasOwnProperty('inherited'), false);
assert.strictEqual(fromDerived.own, 2);

// Object.defineProperties shares the path.
const target = {};
const props = { a: { value: 1, enumerable: true } };
Object.defineProperty(props, 'b', { value: { value: 2 }, enumerable: false });
Object.defineProperties(target, props);
assert.strictEqual(target.a, 1);
assert.strictEqual(target.hasOwnProperty('b'), false);

console.log('ok');
