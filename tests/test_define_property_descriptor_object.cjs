// ToPropertyDescriptor used to read the descriptor's fields as own shape
// properties of a plain object. Any Object is a valid descriptor, and each
// field is read with HasProperty followed by Get, so inherited fields count and
// accessor fields are invoked.

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

// A function is an Object, so it works as a descriptor.
const fromFunction = {};
const descFn = function (a, b) { return a + b; };
descFn.value = 'from-function';
Object.defineProperty(fromFunction, 'p', descFn);
assert(fromFunction.p === 'from-function', `function descriptor: got ${fromFunction.p}`);

// So does an array, and a boxed primitive.
const fromArray = {};
const descArr = [];
descArr.value = 'from-array';
Object.defineProperty(fromArray, 'p', descArr);
assert(fromArray.p === 'from-array', `array descriptor: got ${fromArray.p}`);

const fromBoxed = {};
const descBoxed = new String('ignored');
descBoxed.value = 'from-boxed';
Object.defineProperty(fromBoxed, 'p', descBoxed);
assert(fromBoxed.p === 'from-boxed', `boxed descriptor: got ${fromBoxed.p}`);

// Fields inherited from the descriptor's prototype chain are read.
const proto = { value: 'inherited-data', enumerable: true, configurable: true };
const Ctor = function () {};
Ctor.prototype = proto;

const fromInherited = {};
Object.defineProperty(fromInherited, 'p', new Ctor());
assert(fromInherited.p === 'inherited-data', `inherited value: got ${fromInherited.p}`);

const inheritedDesc = Object.getOwnPropertyDescriptor(fromInherited, 'p');
assert(inheritedDesc.enumerable === true, 'inherited enumerable');
assert(inheritedDesc.configurable === true, 'inherited configurable');
assert(inheritedDesc.writable === false, 'writable absent from the chain stays false');

// Accessor fields on the descriptor are invoked, own or inherited.
const ownAccessor = {};
Object.defineProperty(ownAccessor, 'value', { get: () => 'own-accessor' });
const fromOwnAccessor = {};
Object.defineProperty(fromOwnAccessor, 'p', ownAccessor);
assert(fromOwnAccessor.p === 'own-accessor', `own accessor: got ${fromOwnAccessor.p}`);

const accessorProto = {};
Object.defineProperty(accessorProto, 'value', { get: () => 'inherited-accessor' });
const InheritedAccessorCtor = function () {};
InheritedAccessorCtor.prototype = accessorProto;
const fromInheritedAccessor = {};
Object.defineProperty(fromInheritedAccessor, 'p', new InheritedAccessorCtor());
assert(
  fromInheritedAccessor.p === 'inherited-accessor',
  `inherited accessor: got ${fromInheritedAccessor.p}`
);

// A throwing field getter propagates out of defineProperty.
const throwing = {};
Object.defineProperty(throwing, 'value', {
  get() { throw new RangeError('descriptor getter'); },
});
let caught = null;
try {
  Object.defineProperty({}, 'p', throwing);
} catch (e) {
  caught = e;
}
assert(caught instanceof RangeError, 'throwing descriptor getter propagates');
assert(caught.message === 'descriptor getter', `propagated message: got ${caught && caught.message}`);

// Non-objects are still rejected.
for (const bad of [undefined, null, 42, 'value', true, Symbol('s')]) {
  let threw = false;
  try {
    Object.defineProperty({}, 'p', bad);
  } catch (e) {
    threw = e instanceof TypeError;
  }
  assert(threw, `non-object descriptor ${String(bad)} must throw a TypeError`);
}

// Plain descriptors keep their existing behavior, including absent fields
// defaulting to false rather than being inherited from Object.prototype.
const plain = {};
Object.defineProperty(plain, 'p', { value: 1 });
const plainDesc = Object.getOwnPropertyDescriptor(plain, 'p');
assert(plainDesc.value === 1, 'plain value');
assert(plainDesc.writable === false, 'plain writable defaults to false');
assert(plainDesc.enumerable === false, 'plain enumerable defaults to false');
assert(plainDesc.configurable === false, 'plain configurable defaults to false');

// A descriptor may not mix accessor and data fields, wherever they come from.
const mixed = Object.create({ value: 1 });
mixed.get = () => 2;
let mixedThrew = false;
try {
  Object.defineProperty({}, 'p', mixed);
} catch (e) {
  mixedThrew = e instanceof TypeError;
}
assert(mixedThrew, 'inherited value plus own get is an invalid descriptor');

// The property key goes through ToPropertyKey — ToPrimitive with a string hint,
// then ToString — rather than being formatted for display or truncated.
const keyed = {};
Object.defineProperty(keyed, { valueOf: () => 'abc', toString: undefined }, { value: 1 });
assert(Object.prototype.hasOwnProperty.call(keyed, 'abc'), `valueOf key: got ${Object.getOwnPropertyNames(keyed)}`);

const longKey = 'k'.repeat(100);
const longKeyed = {};
Object.defineProperty(longKeyed, { toString: () => longKey }, { value: 2 });
assert(longKeyed[longKey] === 2, 'a key longer than the old buffer is not truncated');

const primitiveKeys = {};
for (const key of [false, 1.5, null, undefined, ['a', 'b']]) {
  Object.defineProperty(primitiveKeys, key, { value: String(key) });
  assert(primitiveKeys[String(key)] === String(key), `key ${String(key)} coerces with String()`);
}

const symKey = Symbol('sym');
const symKeyed = {};
Object.defineProperty(symKeyed, symKey, { value: 'symbol-keyed' });
assert(symKeyed[symKey] === 'symbol-keyed', 'symbol keys stay symbols');

const toPrimitiveKeyed = {};
Object.defineProperty(toPrimitiveKeyed, { [Symbol.toPrimitive]: (hint) => hint }, { value: 3 });
assert(toPrimitiveKeyed.string === 3, 'ToPropertyKey uses the string hint');

let keyThrew = false;
try {
  Object.defineProperty({}, { toString() { throw new RangeError('key'); }, valueOf: undefined }, { value: 1 });
} catch (e) {
  keyThrew = e instanceof RangeError;
}
assert(keyThrew, 'a throwing key coercion propagates');

console.log('PASS');
