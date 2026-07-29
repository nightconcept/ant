const assert = require('node:assert');

assert.throws(() => btoa('✓'));
assert.doesNotThrow(() => btoa('plain'));

async function expectSyncThrowToReject(method) {
  const marker = new Error(`${method}-sync`);
  let caught;
  try {
    await assert[method](() => {
      throw marker;
    });
  } catch (error) {
    caught = error;
  }
  assert.strictEqual(caught, marker, `assert.${method} must reject with the synchronous exception`);
}

(async () => {
  await expectSyncThrowToReject('rejects');
  await expectSyncThrowToReject('doesNotReject');
  console.log('assert exception propagation ok');
})().catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
