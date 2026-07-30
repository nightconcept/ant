// Math and RegExp instances exposed every own property as enumerable, so
// anything that walks own enumerable keys saw the whole builtin surface.
// Object.create's Properties argument is the sharpest version: it treats each
// enumerable own key as a property descriptor, so `Object.create({}, Math)`
// threw "Property descriptor must be an object" on Math.PI.

const assert = require("node:assert");

// ES2025 21.3.1: Math constants are non-writable, non-enumerable,
// non-configurable. 21.3.2: Math methods are writable and configurable, but
// never enumerable.
assert.deepStrictEqual(Object.keys(Math), [], "Math exposes no enumerable keys");

const pi = Object.getOwnPropertyDescriptor(Math, "PI");
assert.deepStrictEqual(
  { writable: pi.writable, enumerable: pi.enumerable, configurable: pi.configurable },
  { writable: false, enumerable: false, configurable: false },
  "Math.PI attributes"
);
assert.strictEqual(Math.PI, 3.141592653589793, "Math.PI still reads");

const floor = Object.getOwnPropertyDescriptor(Math, "floor");
assert.deepStrictEqual(
  { writable: floor.writable, enumerable: floor.enumerable, configurable: floor.configurable },
  { writable: true, enumerable: false, configurable: true },
  "Math.floor attributes"
);
assert.strictEqual(floor.value, Math.floor, "Math.floor descriptor preserves function identity");
assert.strictEqual(Math.floor(1.7), 1, "Math.floor still works");

const objectToString = Object.getOwnPropertyDescriptor(Object.prototype, "toString");
assert.strictEqual(
  objectToString.value,
  Object.prototype.toString,
  "Object.prototype.toString descriptor preserves function identity"
);

const dateUTC = Object.getOwnPropertyDescriptor(Date, "UTC");
assert.strictEqual(dateUTC.value, Date.UTC, "Date.UTC descriptor preserves function identity");

// A RegExp instance carries nothing enumerable either.
const re = /ab+c/gi;
assert.deepStrictEqual(Object.keys(re), [], "RegExp instance exposes no enumerable keys");
assert.strictEqual(re.source, "ab+c", "source still reads");
assert.strictEqual(re.flags, "gi", "flags still read");
assert.strictEqual(re.global, true, "global still reads");
assert.strictEqual(re.lastIndex, 0, "lastIndex still reads");

// lastIndex stays writable - the matching machinery advances it.
re.lastIndex = 2;
assert.strictEqual(re.lastIndex, 2, "lastIndex is writable");
assert.strictEqual("xxabc".replace(/b/g, "B"), "xxaBc", "regex matching unaffected");

// The Object.create shapes that regressed in test262.
Math.prop = { value: 12, enumerable: true };
assert.ok(Object.create({}, Math).hasOwnProperty("prop"), "Object.create with Math");
delete Math.prop;

const props = new RegExp();
props.prop = { value: 12, enumerable: true };
assert.ok(Object.create({}, props).hasOwnProperty("prop"), "Object.create with a RegExp");

// Ant models the Arguments and RegExp built-in classifications with
// compatibility @@toStringTag properties. They must remain non-enumerable
// without blocking an instance's ordinary tag override.
const args = (function () { return arguments; })();
args[Symbol.toStringTag] = "custom";
assert.strictEqual(Object.prototype.toString.call(args), "[object custom]");

const taggedRegExp = /x/;
taggedRegExp[Symbol.toStringTag] = "custom";
assert.strictEqual(Object.prototype.toString.call(taggedRegExp), "[object custom]");

console.log("test_builtin_prop_attrs: OK");
