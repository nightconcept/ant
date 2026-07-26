function assert(condition, message) {
  if (!condition) {
    console.log("FAIL: " + message);
    throw new Error(message);
  }
}

function assertThrows(fn, message) {
  try {
    fn();
  } catch (e) {
    assert(e instanceof TypeError, message + " (expected TypeError, got " + e + ")");
    return;
  }
  assert(false, message + " (no exception thrown)");
}

// A String wrapper is a String exotic object: its indices and `length` are own
// properties, reachable through the ordinary property-get path.
const wrapper = Object("abc");
assert(wrapper.length === 3, "String wrapper exposes length");
assert(wrapper[0] === "a", "String wrapper exposes index 0");
assert(wrapper[2] === "c", "String wrapper exposes index 2");
assert(wrapper[3] === undefined, "String wrapper has no index past length");

// The generic Array.prototype methods apply ToObject to `this`, so a primitive
// string is boxed rather than rejected.
assert(
  JSON.stringify(Array.prototype.map.call("abc", (c) => c)) === '["a","b","c"]',
  "map over a primitive string"
);
assert(
  JSON.stringify(Array.prototype.filter.call("abc", () => true)) === '["a","b","c"]',
  "filter over a primitive string"
);
assert(
  JSON.stringify(Array.prototype.slice.call("abc")) === '["a","b","c"]',
  "slice over a primitive string"
);
assert(Array.prototype.join.call("abc", "-") === "a-b-c", "join over a primitive string");
assert(Array.prototype.indexOf.call("abc", "b") === 1, "indexOf over a primitive string");
assert(Array.prototype.lastIndexOf.call("abc", "c") === 2, "lastIndexOf over a primitive string");
assert(Array.prototype.includes.call("abc", "b") === true, "includes over a primitive string");
assert(Array.prototype.at.call("abc", 1) === "b", "at over a primitive string");
assert(Array.prototype.at.call("abc", -1) === "c", "at with a negative index");
assert(
  Array.prototype.every.call("abc", (c) => typeof c === "string"),
  "every over a primitive string"
);
assert(Array.prototype.some.call("abc", (c) => c === "b"), "some over a primitive string");
assert(
  Array.prototype.reduce.call("abc", (a, b) => a + b, "") === "abc",
  "reduce over a primitive string"
);
assert(
  Array.prototype.reduceRight.call("abc", (a, b) => a + b, "") === "cba",
  "reduceRight over a primitive string"
);
assert(Array.prototype.find.call("abc", (c) => c === "b") === "b", "find over a primitive string");
assert(Array.prototype.findIndex.call("abc", (c) => c === "b") === 1, "findIndex over a string");
assert(Array.prototype.findLast.call("abc", () => true) === "c", "findLast over a string");
assert(Array.prototype.findLastIndex.call("abc", () => true) === 2, "findLastIndex over a string");

const forEachSeen = [];
Array.prototype.forEach.call("abc", (c) => forEachSeen.push(c));
assert(JSON.stringify(forEachSeen) === '["a","b","c"]', "forEach over a primitive string");

// The same methods work on a boxed wrapper directly.
assert(
  JSON.stringify(Array.prototype.map.call(wrapper, (c) => c)) === '["a","b","c"]',
  "map over a String wrapper"
);

// Functions are objects, so they are valid array-like receivers too.
const fn = function (a) {}; // one declared parameter, so fn.length === 1
fn[0] = "x";
assert(
  JSON.stringify(Array.prototype.map.call(fn, (v) => v)) === '["x"]',
  "map over a function receiver"
);

// Plain array-likes keep working.
const arrayLike = { 0: 11, 1: 9, length: 2 };
assert(
  JSON.stringify(Array.prototype.map.call(arrayLike, (v) => v)) === "[11,9]",
  "map over a plain array-like"
);

// concat does not spread a non-array receiver; it wraps it.
assert(Array.prototype.concat.call("abc").length === 1, "concat wraps a string receiver");

// Only null and undefined are rejected.
assertThrows(() => Array.prototype.forEach.call(null, () => {}), "forEach on null throws");
assertThrows(() => Array.prototype.map.call(undefined, () => {}), "map on undefined throws");
assertThrows(() => Array.prototype.indexOf.call(null, 1), "indexOf on null throws");

// The copying methods build a fresh array and never write to the receiver, so
// they accept any array-like, including one whose elements are not own
// properties of a real array.
const unsorted = { 0: "b", 1: "a", length: 2 };
assert(
  JSON.stringify(Array.prototype.toSorted.call(unsorted)) === '["a","b"]',
  "toSorted over an array-like"
);
assert(
  JSON.stringify(Array.prototype.toReversed.call(unsorted)) === '["a","b"]',
  "toReversed over an array-like"
);
assert(
  JSON.stringify(Array.prototype.toSpliced.call(unsorted, 0, 1)) === '["a"]',
  "toSpliced over an array-like"
);
assert(
  JSON.stringify(Array.prototype.toSorted.call("cab")) === '["a","b","c"]',
  "toSorted over a primitive string"
);
assert(
  JSON.stringify(Array.prototype.toReversed.call("abc")) === '["c","b","a"]',
  "toReversed over a primitive string"
);
assert(
  JSON.stringify(Array.prototype.with.call("abc", 0, "z")) === '["z","b","c"]',
  "with over a primitive string"
);
assert(
  JSON.stringify([...Array.prototype.values.call("abc")]) === '["a","b","c"]',
  "values over a primitive string"
);
assert(
  JSON.stringify([...Array.prototype.keys.call("abc")]) === "[0,1,2]",
  "keys over a primitive string"
);

// A String exotic object's indices and length are non-writable, and the
// mutating methods write with Set(..., throw = true), so a rejected write is a
// TypeError rather than being silently ignored.
assertThrows(() => Array.prototype.push.call("abc", "x"), "push on a string throws");
assertThrows(() => Array.prototype.pop.call("abc"), "pop on a string throws");
assertThrows(() => Array.prototype.shift.call("abc"), "shift on a string throws");
assertThrows(() => Array.prototype.unshift.call("abc", "x"), "unshift on a string throws");
assertThrows(() => Array.prototype.splice.call("abc", 0, 1), "splice on a string throws");
assertThrows(() => Array.prototype.reverse.call("abc"), "reverse on a string throws");
assertThrows(() => Array.prototype.sort.call("ba"), "sort on a string throws");
assertThrows(() => Array.prototype.fill.call("abc", "x"), "fill on a string throws");
assertThrows(() => Array.prototype.copyWithin.call("abc", 0, 1), "copyWithin on a string throws");

// Setting `length` always fails on a String exotic, so these throw even when
// there is no element to move.
assertThrows(() => Array.prototype.push.call(Object(""), "x"), "push on an empty string throws");
assertThrows(() => Array.prototype.push.call(Object("abc")), "push with no args still throws");
assertThrows(() => Array.prototype.pop.call(Object("")), "pop on an empty string throws");
assertThrows(() => Array.prototype.splice.call(Object(""), 0, 0), "splice on empty string throws");

// ...but a method that ends up writing nothing does not throw.
assert(
  Array.prototype.reverse.call(Object("")) instanceof String,
  "reverse on an empty string is a no-op"
);
assert(
  Array.prototype.reverse.call(Object("a")) instanceof String,
  "reverse on a one-character string is a no-op"
);
assert(
  Array.prototype.sort.call(Object("a")) instanceof String,
  "sort on a one-character string is a no-op"
);
assert(
  Array.prototype.fill.call(Object(""), "x") instanceof String,
  "fill on an empty string is a no-op"
);
assert(
  Array.prototype.fill.call(Object("abc"), "x", 1, 1) instanceof String,
  "fill over an empty range is a no-op"
);
assert(
  Array.prototype.copyWithin.call(Object(""), 0, 1) instanceof String,
  "copyWithin with nothing to copy is a no-op"
);

// A Number or Boolean wrapper has no exotic own properties, so the mutating
// methods operate on the throwaway wrapper without throwing.
assert(Array.prototype.push.call(5, "x") === 1, "push on a number returns the new length");
assert(Array.prototype.pop.call(5) === undefined, "pop on a number yields undefined");
assert(Array.prototype.reverse.call(5) instanceof Number, "reverse on a number is a no-op");
assert(Array.prototype.sort.call(5) instanceof Number, "sort on a number is a no-op");
assert(Array.prototype.fill.call(5, "x") instanceof Number, "fill on a number is a no-op");

// The mutating methods still reject null and undefined.
assertThrows(() => Array.prototype.push.call(null, "x"), "push on null throws");
assertThrows(() => Array.prototype.sort.call(undefined), "sort on undefined throws");

console.log("PASS");
