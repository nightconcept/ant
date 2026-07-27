const assert = require('assert');

// float16 conversion rounds the full double in one step, ties to even. Rounding
// through float first would double-round and pick the wrong neighbour.

assert.equal(typeof Math.f16round, 'function');

assert.equal(Math.f16round(2049), 2048);        // tie, 2048 has the even significand
assert.equal(Math.f16round(2051), 2052);        // tie, 2052 has the even significand
assert.equal(Math.f16round(2050), 2050);
assert.equal(Math.f16round(1.337), 1.3369140625);
assert.equal(Math.f16round(1 / 3), 0.333251953125);
assert.equal(Math.f16round(-1.5), -1.5);

assert.ok(Object.is(Math.f16round(0), 0));
assert.ok(Object.is(Math.f16round(-0), -0));
assert.ok(Object.is(Math.f16round(NaN), NaN));
assert.equal(Math.f16round(Infinity), Infinity);
assert.equal(Math.f16round(-Infinity), -Infinity);

// Overflow: 65504 is the largest half, 65520 is the tie that rounds to Infinity.
assert.equal(Math.f16round(65504), 65504);
assert.equal(Math.f16round(65519), 65504);
assert.equal(Math.f16round(65520), Infinity);
assert.equal(Math.f16round(-65520), -Infinity);

// Subnormals and underflow.
assert.equal(Math.f16round(6.103515625e-5), 6.103515625e-5);
assert.equal(Math.f16round(5.960464477539063e-8), 5.960464477539063e-8);
assert.ok(Object.is(Math.f16round(2.9802322387695312e-8), 0));   // 2**-25, ties to even
assert.equal(Math.f16round(4.470348358154297e-8), 5.960464477539063e-8);  // 1.5 * 2**-25, rounds up
assert.ok(Object.is(Math.f16round(-1e-100), -0));
assert.equal(Math.f16round(1e100), Infinity);

// Float16Array and DataView share the conversion.
const ta = new Float16Array(1);
ta[0] = 2049;
assert.equal(ta[0], 2048);

const dv = new DataView(new ArrayBuffer(2));
dv.setFloat16(0, 2049);
assert.equal(dv.getFloat16(0), 2048);

console.log('float16 rounding regression checks passed');
