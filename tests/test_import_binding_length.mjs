// `imported.length` used to compile to a raw frame-slot read (OP_GET_SLOT_RAW),
// which skipped the indirection an imported binding carries and yielded
// undefined. Only `.length` took that fast path, so every other property on the
// same binding kept working - which is what made it easy to miss.

import assert from "node:assert";

import arr, { obj, str } from "./fixtures/import_binding_length_dep.mjs";

assert.strictEqual(arr.length, 3, "default-imported array length");
assert.strictEqual(obj.length, 99, "named-imported object own length");
assert.strictEqual(obj.foo, 1, "unrelated property on the same binding");
assert.strictEqual(str.length, 5, "named-imported string length");

// The bug only reproduced through the binding identifier itself; an alias or a
// function parameter resolved normally. Keep both shapes covered so a future
// fast path cannot regress one without the other.
const alias = arr;
assert.strictEqual(alias.length, 3, "aliased binding length");
assert.strictEqual(((o) => o.length)(arr), 3, "binding length through a call");

console.log("test_import_binding_length: OK");
