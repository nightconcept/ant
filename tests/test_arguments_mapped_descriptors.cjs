let failures = 0;

function eq(actual, expected, label) {
  if (actual !== expected) {
    console.log(`FAIL ${label}: expected ${expected}, got ${actual}`);
    failures++;
  }
}

// Defining a mapped index must update the parameter and must not recurse when
// a later assignment reaches the descriptor-backed property.
function redefineAndAssign(parameter) {
  Object.defineProperty(arguments, '0', {
    value: 2,
    writable: true,
    enumerable: true,
    configurable: false,
  });
  eq(parameter, 2, 'defineProperty value updates mapped parameter');
  arguments[0] = 3;
  return [parameter, arguments[0]];
}

const reassigned = redefineAndAssign(1);
eq(reassigned[0], 3, 'descriptor-backed assignment updates parameter');
eq(reassigned[1], 3, 'descriptor-backed assignment updates property');

// Making the property non-writable disconnects the parameter map.
function makeReadOnly(parameter) {
  Object.defineProperty(arguments, '0', { writable: false });
  parameter = 4;
  arguments[0] = 5;
  return [parameter, arguments[0]];
}

const readOnly = makeReadOnly(1);
eq(readOnly[0], 4, 'non-writable descriptor disconnects parameter');
eq(readOnly[1], 1, 'non-writable mapped property keeps its value');

// Replacing a mapped data property with an accessor also disconnects it.
function replaceWithAccessor(parameter) {
  Object.defineProperty(arguments, '0', { get() { return 8; } });
  parameter = 6;
  return [parameter, arguments[0]];
}

const accessor = replaceWithAccessor(1);
eq(accessor[0], 6, 'accessor descriptor disconnects parameter');
eq(accessor[1], 8, 'accessor descriptor controls arguments value');

if (failures) process.exit(1);
console.log('mapped arguments descriptors: all assertions passed');
