const assert = require('assert');

const object = { value: 1 };
let remaining = 20000;
let checksum = 0;

function step() {
  checksum += object.value;
  if (--remaining > 0) {
    queueMicrotask(step);
    return;
  }

  queueMicrotask(verify);
}

function verify() {
  assert.strictEqual(checksum, 20000);
  assert(
    Ant.stats().alloc.propRefs < 1024 * 1024,
    'microtask property-reference storage should remain bounded',
  );
  console.log('microtask property-reference recycling tests passed');
}

queueMicrotask(step);
