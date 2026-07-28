const assert = require('node:assert');

// GeneratorValidate throws a TypeError when a sync generator is resumed while
// it is already in the "executing" state. `return` and `throw` already did
// this; `next` did not.

function caught(fn) {
  try {
    fn();
  } catch (e) {
    return e;
  }
  return null;
}

let iter;

function* withoutVal() {
  iter.next();
}

function* withVal() {
  iter.next(42);
}

iter = withoutVal();
assert.ok(caught(() => iter.next()) instanceof TypeError);
// The TypeError propagates out of the generator body, completing it.
assert.deepStrictEqual(iter.next(), { value: undefined, done: true });

iter = withVal();
assert.ok(caught(() => iter.next()) instanceof TypeError);
assert.deepStrictEqual(iter.next(), { value: undefined, done: true });

// A generator that is merely suspended, not executing, still resumes normally.
function* ordinary() {
  yield 1;
  yield 2;
}
const ok = ordinary();
assert.deepStrictEqual(ok.next(), { value: 1, done: false });
assert.deepStrictEqual(ok.next(), { value: 2, done: false });
assert.deepStrictEqual(ok.next(), { value: undefined, done: true });

// Async generators queue re-entrant requests rather than throwing, so the
// executing-state guard must not apply to them.
(async () => {
  async function* agen() {
    yield 1;
    yield 2;
  }
  const a = agen();
  const [first, second] = await Promise.all([a.next(), a.next()]);
  assert.deepStrictEqual(first, { value: 1, done: false });
  assert.deepStrictEqual(second, { value: 2, done: false });
  console.log('ok');
})();
