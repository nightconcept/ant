const assert = require('assert');

// GetViewValue / SetViewValue (ES2025 25.3.1.1-2): ToIndex on the byte offset,
// then value conversion, then the detach and bounds checks. A bad index is a
// RangeError; a bad receiver is a TypeError.

// assert.throws ignores its expected-error argument, so check the type here.
function throwsWith(fn, Ctor, label) {
  let caught = null;
  let threw = false;
  try { fn(); } catch (err) { threw = true; caught = err; }
  assert.ok(threw, label + ': expected a throw');
  assert.ok(caught instanceof Ctor, label + ': expected ' + Ctor.name + ', got ' + caught);
}

const POISON = { poison: true };
const poisoned = { valueOf() { throw POISON; } };

function throwsPoison(fn, label) {
  let caught = null;
  try { fn(); } catch (err) { caught = err; }
  assert.equal(caught, POISON, label + ': expected the poisoned valueOf to win');
}

const dv = new DataView(new ArrayBuffer(8));

throwsWith(() => dv.getInt8(-1), RangeError, 'negative index');
throwsWith(() => dv.getInt8(Infinity), RangeError, 'infinite index');
throwsWith(() => dv.getInt8(Number.MAX_SAFE_INTEGER + 1), RangeError, 'index past 2**53-1');
throwsWith(() => dv.getInt32(6), RangeError, 'read past the end');
throwsWith(() => dv.setInt32(6, 0), RangeError, 'write past the end');
throwsWith(() => dv.getInt8(0n), TypeError, 'bigint index');
throwsWith(() => DataView.prototype.getInt8.call({}, 0), TypeError, 'foreign receiver');

// An undefined or NaN index is 0, not a throw.
assert.equal(dv.getInt8(), dv.getInt8(0));
assert.equal(dv.getInt8(NaN), dv.getInt8(0));

// The offset is converted before the bounds check, so a poisoned valueOf wins.
throwsPoison(() => dv.getInt8(poisoned), 'getInt8');
throwsPoison(() => dv.setInt8(poisoned, 0), 'setInt8');
throwsPoison(() => dv.getInt32(poisoned), 'getInt32');

// A non-number offset still goes through ToIndex rather than being ignored.
dv.setInt8('3', 42);
assert.equal(dv.getInt8(3), 42);
dv.setInt8({ valueOf: () => 3 }, 0);
assert.equal(dv.getInt8(3), 0);

// Endianness.
dv.setInt32(0, 0x12345678);
assert.equal(dv.getInt32(0), 0x12345678);
assert.equal(dv.getUint8(0), 0x12);
dv.setInt32(0, 0x12345678, true);
assert.equal(dv.getInt32(0, true), 0x12345678);
assert.equal(dv.getUint8(0), 0x78);

dv.setFloat64(0, 1.5);
assert.equal(dv.getFloat64(0), 1.5);
dv.setFloat32(0, 1.5, true);
assert.equal(dv.getFloat32(0, true), 1.5);
dv.setFloat16(0, 1.5);
assert.equal(dv.getFloat16(0), 1.5);
dv.setFloat16(0, 1.5, true);
assert.equal(dv.getFloat16(0, true), 1.5);

dv.setBigInt64(0, -2n);
assert.equal(dv.getBigInt64(0), -2n);
assert.equal(dv.getBigUint64(0), 18446744073709551614n);
throwsWith(() => dv.setBigInt64(0, 1), TypeError, 'number into setBigInt64');

// Detached buffers are a TypeError, but the index is still converted first.
if (typeof ArrayBuffer.prototype.transfer === 'function') {
  const detachable = new ArrayBuffer(8);
  const detachedView = new DataView(detachable);
  detachable.transfer();
  throwsWith(() => detachedView.getInt8(0), TypeError, 'detached read');
  throwsWith(() => detachedView.getInt8(-1), RangeError, 'detached read, bad index');
}

// The constructor takes both of its offsets through ToIndex too.
const buffer = new ArrayBuffer(8);
throwsWith(() => new DataView(buffer, -1), RangeError, 'ctor negative offset');
throwsWith(() => new DataView(buffer, 9), RangeError, 'ctor offset past the end');
throwsWith(() => new DataView(buffer, 0, -1), RangeError, 'ctor negative length');
throwsWith(() => new DataView(buffer, 4, 5), RangeError, 'ctor length past the end');
throwsWith(() => new DataView(buffer, Infinity), RangeError, 'ctor infinite offset');
throwsPoison(() => new DataView(buffer, poisoned), 'ctor offset');
assert.equal(new DataView(buffer, '4').byteLength, 4);
assert.equal(new DataView(buffer, 4, undefined).byteLength, 4);

console.log('DataView GetViewValue/SetViewValue regression checks passed');
