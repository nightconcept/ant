const assert = require("node:assert");

function write(array, index, value) {
  array[index] = value;
}

const sloppy = [1];
Object.defineProperty(sloppy, "0", { value: 1, writable: false });
write(sloppy, 0, 2);
assert.strictEqual(sloppy[0], 1, "sloppy assignment preserves a non-writable element");

assert.throws(
  () => {
    "use strict";
    const strict = [1];
    Object.defineProperty(strict, "0", { value: 1, writable: false });
    strict[0] = 2;
  },
  TypeError,
  "strict assignment to a non-writable element throws"
);

let ownSetterValue;
const ownAccessor = [1];
Object.defineProperty(ownAccessor, "0", {
  set(value) { ownSetterValue = value; },
  configurable: true,
});
write(ownAccessor, 0, 3);
assert.strictEqual(ownSetterValue, 3, "own indexed setter receives the write");

let inheritedSetterValue;
const setterProto = [];
Object.defineProperty(setterProto, "0", {
  set(value) { inheritedSetterValue = value; },
  configurable: true,
});
const inheritedSetter = [];
Object.setPrototypeOf(inheritedSetter, setterProto);
inheritedSetter.length = 1;
write(inheritedSetter, 0, 4);
assert.strictEqual(inheritedSetterValue, 4, "inherited indexed setter receives a hole write");

const readonlyProto = [];
Object.defineProperty(readonlyProto, "0", {
  value: 5,
  writable: false,
  configurable: true,
});
const inheritedReadonly = [];
Object.setPrototypeOf(inheritedReadonly, readonlyProto);
inheritedReadonly.length = 1;
write(inheritedReadonly, 0, 6);
assert.strictEqual(inheritedReadonly[0], 5, "sloppy write respects inherited non-writable data");

const ordinary = [0, 1];
write(ordinary, 1, 7);
assert.strictEqual(ordinary[1], 7, "ordinary in-bounds dense write remains direct");

const appended = [];
write(appended, 0, 8);
assert.deepStrictEqual(appended, [8], "ordinary append fallback remains dense");

const redefined = [];
redefined[0] = 100;
Object.defineProperty(redefined, "0", {
  value: 100,
  writable: true,
  enumerable: true,
  configurable: true,
});
write(redefined, 0, 101);
assert.strictEqual(redefined[0], 101, "descriptor-backed dense element remains writable");
assert.deepStrictEqual(Object.getOwnPropertyDescriptor(redefined, "0"), {
  value: 101,
  writable: true,
  enumerable: true,
  configurable: true,
});

const redefinedMany = [];
redefinedMany[0] = 100;
Object.defineProperties(redefinedMany, {
  "0": {
    value: 100,
    writable: true,
    enumerable: true,
    configurable: true,
  },
});
write(redefinedMany, 0, 102);
assert.strictEqual(redefinedMany[0], 102, "defineProperties materializes a dense element");

console.log("OK: test_array_numeric_fast_set_descriptors");
