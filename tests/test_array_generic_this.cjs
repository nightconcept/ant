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

console.log("PASS");
