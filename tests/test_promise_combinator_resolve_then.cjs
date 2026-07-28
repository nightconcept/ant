const assert = require('node:assert');

// PerformPromiseAll/AllSettled/Any normalise every element through the
// receiver constructor's own `resolve`, then subscribe with that result's own
// `then` -- neither is necessarily the intrinsic one.

function makeNotPromise() {
  function NotPromise(executor) {
    executor(function () {}, function () {});
  }
  NotPromise.resolve = function (v) {
    NotPromise.resolveCalls.push(v);
    return v;
  };
  NotPromise.resolveCalls = [];
  return NotPromise;
}

function elementFunctionsFor(combinator, thenIndex) {
  const seen = [];
  const NotPromise = makeNotPromise();
  const thenable = {
    then(onFulfilled, onRejected) {
      seen.push(thenIndex === 0 ? onFulfilled : onRejected);
    },
  };
  combinator.call(NotPromise, [thenable, thenable]);
  assert.strictEqual(NotPromise.resolveCalls.length, 2);
  assert.strictEqual(seen.length, 2);
  return seen;
}

function checkElementFunctions(label, fns) {
  for (const fn of fns) {
    assert.strictEqual(typeof fn, 'function', label + ': callable');
    assert.strictEqual(
      Object.getPrototypeOf(fn), Function.prototype, label + ': %Function.prototype%');
    assert.ok(Object.isExtensible(fn), label + ': extensible');
  }
  // Each element gets its own function.
  assert.notStrictEqual(fns[0], fns[1], label + ': distinct per element');
}

checkElementFunctions('all resolve', elementFunctionsFor(Promise.all, 0));
checkElementFunctions('allSettled resolve', elementFunctionsFor(Promise.allSettled, 0));
checkElementFunctions('allSettled reject', elementFunctionsFor(Promise.allSettled, 1));
checkElementFunctions('any reject', elementFunctionsFor(Promise.any, 1));

// An abrupt completion from `resolve` (or from getting it) rejects the
// combinator's promise rather than throwing out of the call.
const thrown = new Error('resolve blew up');

function rejectsWith(combinator, patch) {
  const saved = Object.getOwnPropertyDescriptor(Promise, 'resolve');
  Object.defineProperty(Promise, 'resolve', patch);
  let p;
  try {
    p = combinator.call(Promise, [1]);
  } finally {
    Object.defineProperty(Promise, 'resolve', saved);
  }
  return p;
}

const pending = [
  rejectsWith(Promise.all, { value: function () { throw thrown; }, configurable: true, writable: true }),
  rejectsWith(Promise.allSettled, { value: function () { throw thrown; }, configurable: true, writable: true }),
  rejectsWith(Promise.any, { value: function () { throw thrown; }, configurable: true, writable: true }),
  rejectsWith(Promise.all, { get() { throw thrown; }, configurable: true }),
  rejectsWith(Promise.all, { value: 1, configurable: true, writable: true }),
];

(async () => {
  for (let i = 0; i < pending.length; i++) {
    let rejected = false;
    await pending[i].then(
      () => { throw new Error('combinator ' + i + ' should not fulfil'); },
      (reason) => {
        rejected = true;
        // The last case is "resolve is not callable" -> a TypeError we raise.
        if (i < 4) assert.strictEqual(reason, thrown);
        else assert.ok(reason instanceof TypeError);
      }
    );
    assert.ok(rejected);
  }

  // The ordinary paths still work.
  assert.deepStrictEqual(await Promise.all([1, Promise.resolve(2)]), [1, 2]);
  assert.deepStrictEqual(await Promise.allSettled([Promise.reject('x')]), [
    { status: 'rejected', reason: 'x' },
  ]);
  assert.strictEqual(await Promise.any([Promise.reject('a'), 'b']), 'b');

  const agg = await Promise.any([Promise.reject('a'), Promise.reject('b')]).then(
    () => null, (e) => e);
  assert.ok(agg instanceof AggregateError);
  assert.deepStrictEqual(agg.errors, ['a', 'b']);

  console.log('ok');
})();
