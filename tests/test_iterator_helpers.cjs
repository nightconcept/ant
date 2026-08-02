function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function same(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${expected}, got ${actual}`);
  }
}

function throwsSame(fn, expected, message) {
  try {
    fn();
  } catch (error) {
    same(error, expected, message);
    return;
  }
  throw new Error(`${message}: expected an exception`);
}

function plain(values, options = {}) {
  let index = 0;
  const iterator = {
    next() {
      if (index >= values.length) return { done: true, value: undefined };
      return { done: false, value: values[index++] };
    },
  };
  if (options.close) iterator.return = options.close;
  return iterator;
}

// Iterator.from and lazy helpers must capture next exactly once.
{
  let gets = 0;
  let index = 0;
  const source = {};
  Object.defineProperty(source, "next", {
    get() {
      gets++;
      return function () {
        return index < 2
          ? { done: false, value: ++index }
          : { done: true, value: undefined };
      };
    },
  });

  const wrapped = Iterator.from(source);
  same(gets, 1, "Iterator.from captures next during construction");
  same(wrapped.next().value, 1, "Iterator.from yields the first value");
  same(wrapped.next().value, 2, "Iterator.from yields the second value");
  same(wrapped.next().done, true, "Iterator.from finishes");
  same(gets, 1, "Iterator.from does not read next again");
}

{
  let gets = 0;
  const source = plain([2, 3]);
  const next = source.next;
  Object.defineProperty(source, "next", {
    get() {
      gets++;
      return next;
    },
  });
  const helper = Iterator.prototype.map.call(source, value => value * 2);
  same(gets, 1, "map captures next during construction");
  same(helper.next().value, 4, "map yields a mapped value");
  same(helper.next().value, 6, "map yields another mapped value");
  same(gets, 1, "map does not read next again");
}

// Terminal helpers use GetIteratorDirect and therefore accept plain iterators.
same(Iterator.prototype.every.call(plain([1, 2, 3]), value => value > 0), true, "every accepts a plain iterator");
same(Iterator.prototype.some.call(plain([1, 2, 3]), value => value === 2), true, "some accepts a plain iterator");
same(Iterator.prototype.find.call(plain([1, 2, 3]), value => value > 1), 2, "find accepts a plain iterator");
same(Iterator.prototype.filter.call(plain([1, 2, 3]), value => value % 2).next().value, 1, "filter accepts a plain iterator");
let total = 0;
Iterator.prototype.forEach.call(plain([1, 2, 3]), value => { total += value; });
same(total, 6, "forEach accepts a plain iterator");
same(Iterator.prototype.reduce.call(plain([1, 2, 3]), (a, b) => a + b), 6, "reduce accepts a plain iterator");
same(Iterator.prototype.toArray.call(plain([1, 2, 3])).join(","), "1,2,3", "toArray accepts a plain iterator");

// Iterator result validation and accessor failures stay observable.
{
  const helper = Iterator.from({ next() { return 1; } });
  let typeError = false;
  try { helper.next(); } catch (error) { typeError = error instanceof TypeError; }
  assert(typeError, "a non-object iterator result throws TypeError");
}

{
  const doneError = new Error("done");
  const helper = Iterator.from({
    next() {
      return Object.defineProperty({}, "done", { get() { throw doneError; } });
    },
  });
  throwsSame(() => helper.next(), doneError, "done getter failure propagates");
}

{
  const valueError = new Error("value");
  const helper = Iterator.from({
    next() {
      return Object.defineProperties({}, {
        done: { value: false },
        value: { get() { throw valueError; } },
      });
    },
  });
  throwsSame(() => helper.next(), valueError, "value getter failure propagates");
}

{
  let valueGets = 0;
  const result = Object.defineProperties({}, {
    done: { value: true },
    value: { get() { valueGets++; return 1; } },
  });
  same(Iterator.from({ next() { return result; } }).next().done, true, "done result is preserved");
  same(valueGets, 0, "value is not read after done is true");
}

// Early terminal completion closes once. A callback throw remains primary.
for (const [name, callback] of [
  ["every", value => value < 1],
  ["some", value => value === 1],
  ["find", value => value === 1],
]) {
  let closes = 0;
  const source = plain([1, 2], { close() { closes++; return {}; } });
  Iterator.prototype[name].call(source, callback);
  same(closes, 1, `${name} closes after early completion`);
}

{
  const callbackError = new Error("callback");
  const source = plain([1], { close() { throw new Error("close"); } });
  throwsSame(
    () => Iterator.prototype.forEach.call(source, () => { throw callbackError; }),
    callbackError,
    "callback failure remains primary when close also fails",
  );
}

// Helper-produced results keep the specified observable key order.
same(Object.keys(Iterator.from(plain([1])).next()).join(","), "done,value", "result key order");

// Helpers close and stay completed without touching the source again.
{
  let nextCalls = 0;
  let closes = 0;
  const source = {
    next() { nextCalls++; return { done: false, value: 1 }; },
    return() { closes++; return {}; },
  };
  const helper = Iterator.prototype.take.call(source, 0);
  same(helper.next().done, true, "take(0) completes immediately");
  same(nextCalls, 0, "take(0) does not call source next");
  same(closes, 1, "take(0) closes the source");
  same(helper.next().done, true, "completed helper stays completed");
  same(nextCalls, 0, "completed helper does not call source next");
}

{
  let closes = 0;
  const helper = Iterator.prototype.map.call(
    plain([1, 2], { close() { closes++; return {}; } }),
    value => value,
  );
  same(Iterator.prototype.some.call(helper, value => value === 1), true, "wrapped some finds a value");
  same(closes, 1, "closing a helper forwards to its source");
  same(helper.next().done, true, "closed helper stays completed");
}

{
  let closes = 0;
  const helper = Iterator.from(plain([1], { close() { closes++; return {}; } }));
  const result = helper.return(9);
  same(result.done, true, "helper return result is done");
  same(result.value, 9, "helper return forwards its completion value");
  same(closes, 1, "helper return closes its source");
}

{
  let nextGets = 0;
  let closes = 0;
  const source = {
    get next() { nextGets++; throw new Error("next must not be read"); },
    return() { closes++; return {}; },
  };
  let typeError = false;
  try { Iterator.prototype.map.call(source); } catch (error) { typeError = error instanceof TypeError; }
  assert(typeError, "invalid callback throws TypeError");
  same(nextGets, 0, "invalid callback does not read next");
  same(closes, 1, "invalid callback closes the iterator without reading next");
}

for (const name of ["every", "some", "find", "forEach", "reduce"]) {
  let nextGets = 0;
  let closes = 0;
  const source = {
    get next() { nextGets++; throw new Error("next must not be read"); },
    return() { closes++; return {}; },
  };
  let typeError = false;
  try { Iterator.prototype[name].call(source); } catch (error) { typeError = error instanceof TypeError; }
  assert(typeError, `${name} invalid callback throws TypeError`);
  same(nextGets, 0, `${name} invalid callback does not read next`);
  same(closes, 1, `${name} invalid callback closes the iterator`);
}

{
  const effects = [];
  const source = {
    get next() {
      effects.push("next");
      return () => ({ done: true, value: undefined });
    },
  };
  Iterator.prototype.take.call(source, {
    valueOf() { effects.push("limit"); return 0; },
  });
  same(effects.join(","), "limit,next", "take converts its limit before reading next");
}

{
  let nextGets = 0;
  let closes = 0;
  const source = plain([1, 2], { close() { closes++; return {}; } });
  const next = source.next;
  Object.defineProperty(source, "next", { get() { nextGets++; return next; } });
  const helper = Iterator.prototype.drop.call(source, Infinity);
  same(nextGets, 1, "drop captures next once");
  same(helper.next().done, true, "drop(Infinity) exhausts a finite source");
  same(closes, 0, "drop exhaustion does not close the source");
}

{
  const helperPrototype = Object.getPrototypeOf([].values().map(value => value));
  function* values() { yield 1; }

  for (const name of ["next", "return", "throw"]) {
    let typeError = false;
    try { helperPrototype[name].call(values()); } catch (error) { typeError = error instanceof TypeError; }
    assert(typeError, `iterator helper ${name} rejects an unbranded generator`);
  }
}

console.log("iterator helper direct-record tests passed");
