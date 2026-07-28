const assert = require('node:assert');

// Outside a generator's [Yield] context, `yield` is an ordinary
// IdentifierReference in sloppy mode -- including inside a non-generator
// function nested in a generator body.

var yield = 1;
assert.strictEqual(yield, 1);
yield = yield + 1;
assert.strictEqual(yield, 2);

function plain() {
  var yield = 'plain';
  return yield;
}
assert.strictEqual(plain(), 'plain');

function* nested() {
  const received = yield;
  return (function (arg) {
    var yield = arg + 1;
    return yield;
  })(received);
}

const it = nested();
assert.strictEqual(it.next().done, false);
assert.deepStrictEqual(it.next(41), { value: 42, done: true });

const obj = {
  *gen() {
    const received = yield;
    return (function (arg) {
      var yield = arg;
      return yield;
    })(received);
  },
  method() {
    var yield = 'method';
    return yield;
  },
};
assert.strictEqual(obj.method(), 'method');
const objIt = obj.gen();
objIt.next();
assert.deepStrictEqual(objIt.next('x'), { value: 'x', done: true });

// Arrow functions inherit [Yield] from the enclosing context, so `yield` in an
// arrow outside any generator is still an identifier.
const arrow = (yield) => yield;
assert.strictEqual(arrow(7), 7);

// Async generators behave like sync ones: the generator body keeps `yield` as
// an operator, nested non-generator functions do not.
async function* asyncGen() {
  const received = yield;
  return (function (arg) {
    var yield = arg + 1;
    return yield;
  })(received);
}

// `yield` stays a reserved word in strict mode, and stays an operator inside a
// generator body (so it cannot be used as a bare identifier reference there).
function syntaxErrorFrom(src) {
  try {
    eval(src);
  } catch (e) {
    return e instanceof SyntaxError;
  }
  return false;
}

assert.ok(syntaxErrorFrom('"use strict"; var yield = 1;'));
assert.ok(syntaxErrorFrom('"use strict"; (function () { return yield; });'));
assert.ok(syntaxErrorFrom('function* g() { return (function () { return yield; }); }') === false);
assert.ok(syntaxErrorFrom('function f() { return yield; }') === false);

(async () => {
  const ai = asyncGen();
  assert.strictEqual((await ai.next()).done, false);
  assert.deepStrictEqual(await ai.next(41), { value: 42, done: true });
  console.log('ok');
})();
