// NamedEvaluation (spec 8.5.5) used to be applied only to variable declarations
// and object literal properties, so anonymous functions and classes reached
// through a destructuring default, a parameter default, or a plain assignment
// were left with an empty `name`.

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function check(actual, expected, label) {
  assert(actual === expected, `${label}: expected name '${expected}', got '${actual}'`);
}

// Plain assignment to an identifier reference.
let assignFn, assignGen, assignArrow, assignCls;
assignFn = function () {};
assignGen = function* () {};
assignArrow = () => {};
assignCls = class {};
check(assignFn.name, 'assignFn', 'assign fn');
check(assignGen.name, 'assignGen', 'assign gen');
check(assignArrow.name, 'assignArrow', 'assign arrow');
check(assignCls.name, 'assignCls', 'assign class');

// A parenthesized target is not an IdentifierReference, so it names nothing.
let parened;
(parened) = function () {};
check(parened.name, '', 'parenthesized assign');

// Member assignment never names.
const holder = {};
holder.prop = function () {};
check(holder.prop.name, '', 'member assign');

// Parameter defaults, both in a simple parameter list and alongside a pattern.
function simpleParams(fn = function () {}, cls = class {}) {
  return [fn.name, cls.name];
}
check(simpleParams()[0], 'fn', 'simple param default fn');
check(simpleParams()[1], 'cls', 'simple param default class');

function mixedParams({ a } = { a: 1 }, arrow = () => {}) {
  return [a, arrow.name];
}
check(mixedParams()[1], 'arrow', 'non-simple param default arrow');

// Object and array destructuring defaults, in both binding and assignment form.
const { objFn = function () {} } = {};
check(objFn.name, 'objFn', 'object pattern default');

const { renamed: objGen = function* () {} } = {};
check(objGen.name, 'objGen', 'renamed object pattern default');

const [aryArrow = () => {}] = [];
check(aryArrow.name, 'aryArrow', 'array pattern default');

let assignedTarget;
({ assignedTarget = class {} } = {});
check(assignedTarget.name, 'assignedTarget', 'destructuring assignment default');

// Nested patterns still name their leaf identifiers.
const { outer: { inner = function () {} } = {} } = {};
check(inner.name, 'inner', 'nested pattern default');

// A named function expression keeps its own name.
const { keep = function named() {} } = {};
check(keep.name, 'named', 'named function expression default');

// A non-identifier target (member expression) in a pattern names nothing.
const sink = {};
[sink.slot = function () {}] = [];
check(sink.slot.name, '', 'member target in array pattern');

// Defaults that are not taken are unaffected.
const original = function () {};
const { untaken = function () {} } = { untaken: original };
assert(untaken === original, 'untaken default should not replace the value');

// The `name` property stays a normal function name property.
const desc = Object.getOwnPropertyDescriptor(objFn, 'name');
assert(desc.writable === false, 'name should be non-writable');
assert(desc.enumerable === false, 'name should be non-enumerable');
assert(desc.configurable === true, 'name should be configurable');

console.log('named evaluation ok');
