// Integer-indexed element access on typed arrays: canonical numeric indices are
// served from the backing store, and non-canonical or out-of-range indices are
// absorbed instead of reaching the ordinary property machinery.

let failures = 0;

function eq(actual, expected, label) {
  const a = String(actual), e = String(expected);
  if (a !== e) {
    console.log(`FAIL ${label}: expected ${e}, got ${a}`);
    failures++;
  }
}

// Reads and writes round-trip through the element storage.
{
  const ta = new Float64Array(4);
  ta[0] = 1.5;
  ta[3] = -2.25;
  eq(ta[0], 1.5, "float64 store/load");
  eq(ta[3], -2.25, "float64 store/load at last index");
  eq(ta[1], 0, "float64 default element");
}

// Every element type keeps its own conversion rules on the fast path.
{
  const i8 = new Int8Array(1);
  i8[0] = 200;
  eq(i8[0], -56, "int8 wraps");

  const u8c = new Uint8ClampedArray(2);
  u8c[0] = 300;
  u8c[1] = -5;
  eq(u8c[0], 255, "uint8clamped saturates high");
  eq(u8c[1], 0, "uint8clamped saturates low");

  const f32 = new Float32Array(1);
  f32[0] = 0.1;
  eq(f32[0], 0.10000000149011612, "float32 rounds to single precision");

  const big = new BigInt64Array(1);
  big[0] = -5n;
  eq(big[0], -5n, "bigint64 store/load");
}

// An out-of-range index reads as undefined and must not consult the prototype
// chain (ES2026 10.4.5.5).
{
  const ta = new Float64Array(2);
  Object.prototype[99] = "from proto";
  try {
    eq(ta[99], undefined, "out-of-range read ignores prototype");
  } finally {
    delete Object.prototype[99];
  }
}

// An out-of-range write is discarded rather than defining an own property
// (ES2026 10.4.5.3).
{
  const ta = new Float64Array(2);
  ta[99] = 7;
  eq(ta[99], undefined, "out-of-range write does not store");
  eq(Object.getOwnPropertyDescriptor(ta, "99"), undefined, "out-of-range write defines nothing");
}

// Numeric keys that are not canonical indices behave the same way.
{
  const ta = new Float64Array(2);
  ta[1.5] = 7;
  ta[-1] = 7;
  eq(ta[1.5], undefined, "fractional index reads undefined");
  eq(ta[-1], undefined, "negative index reads undefined");
  eq(Object.getOwnPropertyDescriptor(ta, "1.5"), undefined, "fractional index defines nothing");
  eq(Object.getOwnPropertyDescriptor(ta, "-1"), undefined, "negative index defines nothing");
}

// -0 is the canonical index 0.
{
  const ta = new Float64Array(1);
  ta[-0] = 3;
  eq(ta[0], 3, "-0 writes index 0");
  eq(ta[-0], 3, "-0 reads index 0");
}

// NaN and Infinity are not indices.
{
  const ta = new Float64Array(1);
  eq(ta[NaN], undefined, "NaN index reads undefined");
  eq(ta[Infinity], undefined, "Infinity index reads undefined");
}

// A value written to an in-range index is coerced with ToNumber, so a valueOf
// side effect is observable exactly once.
{
  const ta = new Float64Array(1);
  let calls = 0;
  ta[0] = { valueOf() { calls++; return 7; } };
  eq(ta[0], 7, "valueOf result is stored");
  eq(calls, 1, "valueOf called once");
}

// A detached buffer reads as undefined and absorbs writes.
{
  const buf = new ArrayBuffer(8);
  const ta = new Float64Array(buf);
  ta[0] = 1;
  structuredClone(buf, { transfer: [buf] });
  eq(ta[0], undefined, "detached read is undefined");
  ta[0] = 2;
  eq(ta[0], undefined, "detached write is absorbed");
}

// Views over a shared buffer see each other's writes through the fast path.
{
  const buf = new ArrayBuffer(16);
  const a = new Float64Array(buf);
  const b = new Uint8Array(buf);
  a[0] = 0;
  b[0] = 1;
  eq(a[0], 5e-324, "overlapping views share storage");
}

// A view with a non-zero byte offset indexes from its own base.
{
  const buf = new ArrayBuffer(32);
  const whole = new Float64Array(buf);
  const tail = new Float64Array(buf, 16);
  tail[0] = 9;
  eq(whole[2], 9, "byteOffset view writes at the right element");
  eq(tail.length, 2, "byteOffset view length");
  eq(tail[2], undefined, "byteOffset view bounds are its own");
}

// Every write path reaches the element store, not an ordinary own property.
{
  function bytes(ta) {
    return Array.from(new Uint8Array(ta.buffer).slice(0, 8)).join(",");
  }
  const expected = "0,0,0,0,0,0,240,63"; // float64 1.0, little-endian

  const viaElement = new Float64Array(1);
  viaElement["0"] = 1;
  eq(bytes(viaElement), expected, "string-key write reaches the element store");

  const viaReflect = new Float64Array(1);
  eq(Reflect.set(viaReflect, "0", 1), true, "Reflect.set returns true");
  eq(bytes(viaReflect), expected, "Reflect.set reaches the element store");

  const viaDefine = new Float64Array(1);
  Object.defineProperty(viaDefine, "0", { value: 1, writable: true, enumerable: true, configurable: true });
  eq(bytes(viaDefine), expected, "defineProperty reaches the element store");
}

// Element descriptors are reported from the backing store.
{
  const ta = new Float64Array(2);
  ta[0] = 7;
  const desc = Object.getOwnPropertyDescriptor(ta, "0");
  eq(desc.value, 7, "descriptor value");
  eq(desc.writable, true, "descriptor writable");
  eq(desc.enumerable, true, "descriptor enumerable");
  eq(desc.configurable, true, "descriptor configurable");
  eq(Object.getOwnPropertyDescriptor(ta, "9"), undefined, "no descriptor out of range");
}

// A descriptor that cannot describe an element is rejected.
{
  const ta = new Float64Array(1);
  let threw = false;
  try {
    Object.defineProperty(ta, "0", { get() { return 1; } });
  } catch (e) {
    threw = e instanceof TypeError;
  }
  eq(threw, true, "accessor descriptor on an element is rejected");
  eq(Reflect.defineProperty(ta, "0", { value: 1, writable: false }), false, "non-writable element descriptor is rejected");
  eq(Reflect.defineProperty(ta, "9", { value: 1 }), false, "out-of-range define is rejected");
}

// Ordinary arrays keep working alongside the typed-array path.
{
  const a = [1, 2, 3];
  a[1] = 9;
  eq(a[1], 9, "array element write");
  a[3] = 4;
  eq(a.length, 4, "array append extends length");
  eq(a[3], 4, "array append stores");
  const args = (function () { arguments[0] = 42; return arguments[0]; })(1);
  eq(args, 42, "arguments object still writable");
}

if (failures > 0) {
  console.log(`${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("typedarray index access: all assertions passed");
