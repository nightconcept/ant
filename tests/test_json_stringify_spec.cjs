function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function eq(actual, expected, label) {
  assert(
    actual === expected,
    `${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
  );
}

// toJSON is looked up on the prototype chain, not just as an own property.
eq(JSON.stringify(new Date(0)), '"1970-01-01T00:00:00.000Z"', 'Date toJSON');
eq(JSON.stringify({ at: new Date(0) }), '{"at":"1970-01-01T00:00:00.000Z"}', 'nested Date toJSON');
eq(JSON.stringify(Object.create({ toJSON() { return 'inherited'; } })), '"inherited"', 'inherited toJSON');
eq(JSON.stringify({ toJSON() { return { x: 1 }; } }), '{"x":1}', 'own toJSON');

// Wrapper objects serialize as their primitive.
eq(JSON.stringify(new String('boxed')), '"boxed"', 'String wrapper');
eq(JSON.stringify(new Number(7)), '7', 'Number wrapper');
eq(JSON.stringify(new Boolean(true)), 'true', 'Boolean wrapper');
eq(JSON.stringify({ n: new Number(1.5) }), '{"n":1.5}', 'nested Number wrapper');

// BigInt is not serializable.
let threw = null;
try {
  JSON.stringify({ big: 1n });
} catch (error) {
  threw = error;
}
assert(threw instanceof TypeError, 'BigInt should throw a TypeError');

// Only own enumerable properties are serialized.
const proto = { inherited: 1 };
const child = Object.create(proto);
child.own = 2;
eq(JSON.stringify(child), '{"own":2}', 'own properties only');
eq(
  JSON.stringify(Object.defineProperty({ a: 1 }, 'hidden', { value: 2, enumerable: false })),
  '{"a":1}',
  'non-enumerable skipped'
);

// The `space` argument follows SerializeJSONProperty: numbers clamp to 10
// spaces, strings are truncated to their first 10 UTF-16 units.
eq(JSON.stringify({ a: 1 }, null, 2), '{\n  "a": 1\n}', 'two space indent');
eq(JSON.stringify({ a: 1 }, null, 3), '{\n   "a": 1\n}', 'three space indent');
eq(JSON.stringify({ a: 1 }, null, 0), '{"a":1}', 'zero indent');
eq(JSON.stringify({ a: 1 }, null, -1), '{"a":1}', 'negative indent');
eq(JSON.stringify({ a: 1 }, null, 100), `{\n${' '.repeat(10)}"a": 1\n}`, 'indent clamps to 10');
eq(JSON.stringify({ a: 1 }, null, '--'), '{\n--"a": 1\n}', 'string indent');
eq(JSON.stringify({ a: 1 }, null, '0123456789abc'), '{\n0123456789"a": 1\n}', 'string indent clamps to 10');
eq(JSON.stringify({ a: 1 }, null, new Number(3)), '{\n   "a": 1\n}', 'Number wrapper indent');
eq(JSON.stringify({ a: 1 }, null, new String('--')), '{\n--"a": 1\n}', 'String wrapper indent');
eq(JSON.stringify({ a: 1 }, null, 6.9), '{\n      "a": 1\n}', 'fractional indent truncates');
eq(JSON.stringify({ a: [] }, null, 2), '{\n  "a": []\n}', 'empty array keeps no indent');
eq(JSON.stringify({ a: {} }, null, 2), '{\n  "a": {}\n}', 'empty object keeps no indent');
eq(JSON.stringify([1, [2]], null, 1), '[\n 1,\n [\n  2\n ]\n]', 'nested array indent');

// Values with no representation vanish from objects but become null in arrays.
eq(JSON.stringify({ a: undefined, b: function () {}, c: Symbol('s'), d: 1 }), '{"d":1}', 'skipped keys');
eq(JSON.stringify([undefined, function () {}, Symbol('s')]), '[null,null,null]', 'skipped array slots');
eq(JSON.stringify([1, , 3]), '[1,null,3]', 'array hole');

// String escaping, including lone surrogates.
eq(JSON.stringify('a"b\\c\nd\te'), '"a\\"b\\\\c\\nd\\te"', 'escapes');
eq(JSON.stringify(''), '"\\u0001"', 'control escape');
eq(JSON.stringify('lone\uD800end'), '"lone\\ud800end"', 'lone surrogate escaped');
eq(JSON.stringify('pair\u{1F600}end'), '"pair\u{1F600}end"', 'surrogate pair preserved');

// Numbers use the same shortest representation as Number#toString.
eq(JSON.stringify([NaN, Infinity, -Infinity]), '[null,null,null]', 'non-finite numbers');
eq(JSON.stringify(-0), '0', 'negative zero');
eq(JSON.stringify(1e21), '1e+21', 'large exponent');
eq(JSON.stringify(1e-7), '1e-7', 'small exponent');
eq(JSON.stringify(0.1 + 0.2), '0.30000000000000004', 'shortest round-trip');

// A proxy is enumerated through its ownKeys trap, not its (empty) own shape.
const trapped = [];
const proxy = new Proxy({ a: 1, b: 2 }, {
  ownKeys(target) { trapped.push('ownKeys'); return Reflect.ownKeys(target); },
});
eq(JSON.stringify(proxy), '{"a":1,"b":2}', 'proxy stringify');
assert(trapped.length > 0, 'proxy ownKeys trap should have run');

// Duplicate keys in parsed input keep the last value.
eq(JSON.parse('{"a":1,"a":2}').a, 2, 'duplicate key wins');
const wide = {};
let widejson = '{';
for (let i = 0; i < 40; i++) widejson += `"k${i}":${i},`;
widejson += '"k0":999}';
eq(JSON.parse(widejson).k0, 999, 'duplicate key wins past the inline scan');
eq(Object.keys(JSON.parse(widejson)).length, 40, 'duplicate key does not add a slot');
void wide;

console.log('json stringify spec: ok');
