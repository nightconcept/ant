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
  assert.strictEqual(
    Object.prototype.hasOwnProperty.call(Ant.stats().alloc, 'propRefs'),
    false,
    'operation-local property locations require no retained handle storage',
  );
  console.log('microtask property-reference recycling tests passed');
}

queueMicrotask(step);
