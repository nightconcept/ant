// Builtins registered through js_setprop with a string key (Math, Date.prototype,
// Symbol) used to be installed from an anonymous cfunc meta, leaving them without
// the own `name` property every function is required to have.

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const cases = [
  [Math.pow, 'pow'],
  [Math.max, 'max'],
  [Date.prototype.getHours, 'getHours'],
  [Date.prototype.setUTCMinutes, 'setUTCMinutes'],
  [Symbol.for, 'for'],
  // Builtins registered through the other paths must keep working.
  [Object.keys, 'keys'],
  [Array.isArray, 'isArray'],
  [String.prototype.slice, 'slice'],
];

for (const [fn, expected] of cases) {
  assert(fn.name === expected, `expected name '${expected}', got '${fn.name}'`);

  assert(
    Object.prototype.hasOwnProperty.call(fn, 'name'),
    `expected '${expected}' to have an own name property`
  );

  const desc = Object.getOwnPropertyDescriptor(fn, 'name');
  assert(desc.writable === false, `expected '${expected}' name to be non-writable`);
  assert(desc.enumerable === false, `expected '${expected}' name to be non-enumerable`);
  assert(desc.configurable === true, `expected '${expected}' name to be configurable`);
}

// Aliasing a named builtin must not rename it: the key is only adopted while the
// underlying cfunc is still anonymous.
const holder = {};
holder.renamed = Math.pow;
assert(holder.renamed.name === 'pow', `aliasing renamed the builtin to '${holder.renamed.name}'`);

// User functions keep the ordinary SetFunctionName semantics.
const obj = {};
obj.assigned = function () {};
assert(obj.assigned.name === '', `expected assignment to leave name empty, got '${obj.assigned.name}'`);

console.log('builtin function name test passed');
