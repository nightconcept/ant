// Accessor inline-cache behaviour. The interesting cases only appear once a
// property site has run enough times to warm (and then invalidate) its IC, so
// every case loops rather than reading once.
const assert = require("assert");

const WARM = 200;

// --- prototype getter/setter, the shape the IC is built for -----------------
{
  class Base {
    constructor(v) { this._v = v; }
    get v() { return this._v; }
    set v(x) { this._v = x * 2; }
  }
  const o = new Base(1);
  for (let i = 0; i < WARM; i++) {
    o.v = i;
    assert.strictEqual(o.v, i * 2);
    assert.strictEqual(o._v, i * 2);
  }
}

// --- `this` inside an accessor is the receiver, not the holder --------------
{
  class Base { get who() { return this.tag; } }
  const a = new Base(); a.tag = "a";
  const b = new Base(); b.tag = "b";
  for (let i = 0; i < WARM; i++) {
    assert.strictEqual(a.who, "a");
    assert.strictEqual(b.who, "b");
  }
}

// --- a getter that throws must propagate, warm or cold ----------------------
{
  class Boom { get bad() { throw new Error("getter boom"); } }
  const o = new Boom();
  for (let i = 0; i < WARM; i++) {
    assert.throws(() => o.bad, /getter boom/);
  }
}

{
  class Boom { set bad(x) { throw new Error("setter boom"); } }
  const o = new Boom();
  for (let i = 0; i < WARM; i++) {
    assert.throws(() => { o.bad = i; }, /setter boom/);
  }
}

// --- setter-only reads as undefined; getter-only ignores writes (sloppy) ----
{
  const proto = {};
  Object.defineProperty(proto, "wo", { set(x) { this.seen = x; }, configurable: true });
  Object.defineProperty(proto, "ro", { get() { return 7; }, configurable: true });
  const o = Object.create(proto);
  for (let i = 0; i < WARM; i++) {
    assert.strictEqual(o.wo, undefined);
    o.wo = i;
    assert.strictEqual(o.seen, i);
    assert.strictEqual(o.ro, 7);
    o.ro = 99;
    assert.strictEqual(o.ro, 7);
  }
}

// --- own accessor defined directly on the instance --------------------------
{
  const o = {};
  let n = 0;
  Object.defineProperty(o, "counter", { get() { return ++n; }, configurable: true });
  for (let i = 1; i <= WARM; i++) assert.strictEqual(o.counter, i);
}

// --- redefining an accessor as a data property must invalidate the IC -------
{
  const proto = {};
  Object.defineProperty(proto, "p", { get() { return "accessor"; }, configurable: true });
  const o = Object.create(proto);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.p, "accessor");
  Object.defineProperty(proto, "p", { value: "data", writable: true, configurable: true });
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.p, "data");
}

// --- and the reverse: data property replaced by an accessor -----------------
{
  const proto = { q: "data" };
  const o = Object.create(proto);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.q, "data");
  Object.defineProperty(proto, "q", { get() { return "accessor"; }, configurable: true });
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.q, "accessor");
}

// --- shadowing a prototype accessor with an own data property ---------------
{
  const proto = {};
  Object.defineProperty(proto, "s", { get() { return "proto"; }, configurable: true });
  const o = Object.create(proto);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.s, "proto");
  Object.defineProperty(o, "s", { value: "own", writable: true, configurable: true });
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.s, "own");
}

// --- swapping the prototype out from under a warm site ----------------------
{
  const p1 = {}; Object.defineProperty(p1, "t", { get() { return 1; } });
  const p2 = {}; Object.defineProperty(p2, "t", { get() { return 2; } });
  const o = Object.create(p1);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.t, 1);
  Object.setPrototypeOf(o, p2);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.t, 2);
}

// --- deleting a warm accessor ----------------------------------------------
{
  const proto = {};
  Object.defineProperty(proto, "d", { get() { return "here"; }, configurable: true });
  const o = Object.create(proto);
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.d, "here");
  delete proto.d;
  for (let i = 0; i < WARM; i++) assert.strictEqual(o.d, undefined);
}

// --- one site alternating between accessor and data receivers ---------------
{
  const withAcc = Object.create(Object.defineProperty({}, "m", { get() { return "acc"; } }));
  const withData = { m: "data" };
  for (let i = 0; i < WARM; i++) {
    const o = (i & 1) ? withAcc : withData;
    assert.strictEqual(o.m, (i & 1) ? "acc" : "data");
  }
}

// --- assigning to a getter-only property throws in strict mode --------------
// (written with try/catch rather than assert.throws: an arrow passed to
// assert.throws can be inlined here, and the throw then escapes it)
(function strictAssign() {
  "use strict";
  class RO { get x() { return 1; } }
  const o = new RO();
  for (let i = 0; i < WARM; i++) {
    assert.strictEqual(o.x, 1);
    let caught = null;
    try { o.x = 2; } catch (e) { caught = e; }
    assert.ok(caught instanceof TypeError, "strict assign to getter-only must throw TypeError");
    assert.strictEqual(o.x, 1);
  }
})();

// ...and is silently ignored in sloppy mode
{
  class RO2 { get y() { return 1; } }
  const o = new RO2();
  for (let i = 0; i < WARM; i++) {
    o.y = 2;
    assert.strictEqual(o.y, 1);
  }
}

// --- setter that triggers GC / allocation inside the call -------------------
{
  class Alloc {
    set big(x) { this._last = new Array(64).fill(x); }
    get big() { return this._last[0]; }
  }
  const o = new Alloc();
  for (let i = 0; i < WARM; i++) {
    o.big = i;
    assert.strictEqual(o.big, i);
  }
}

console.log("accessor IC tests passed");
