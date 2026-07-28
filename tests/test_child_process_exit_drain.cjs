// A child that writes and exits immediately races the exit callback against
// libuv's read callbacks. The 'close' event must not fire until both the
// process has exited *and* its stdio has drained, or output written just
// before exit is silently dropped.
const assert = require('node:assert');
const { spawn } = require('node:child_process');

// Big enough to need several reads, small enough to stay under the pipe buffer
// so the child never blocks and can exit while data is still in flight.
const LINES = 400;
const script = `for i in $(seq ${LINES}); do echo "out $i"; echo "err $i" >&2; done`;

let pending = 0;
let failures = 0;

// Fails the run at the point of detection: a truncated read can also leave a
// child without its 'close', so the tally at the end is not guaranteed to be
// reached on a regression.
function check(label, actual, expected) {
  if (actual !== expected) {
    failures++;
    console.error(`FAIL ${label}: expected ${expected}, got ${actual}`);
    process.exit(1);
  }
}

// Repeat: a single run lands on the safe side of the race most of the time.
const RUNS = 20;

for (let run = 0; run < RUNS; run++) {
  pending++;
  const child = spawn('sh', ['-c', script]);

  let out = '';
  let err = '';
  child.stdout.on('data', (d) => { out += d; });
  child.stderr.on('data', (d) => { err += d; });

  child.on('close', (code) => {
    check(`run ${run} exit code`, code, 0);
    check(`run ${run} stdout lines`, out.trim().split('\n').length, LINES);
    check(`run ${run} stderr lines`, err.trim().split('\n').length, LINES);
    check(`run ${run} last stdout line`, out.trim().split('\n').pop(), `out ${LINES}`);
    check(`run ${run} last stderr line`, err.trim().split('\n').pop(), `err ${LINES}`);

    if (--pending === 0) {
      assert.strictEqual(failures, 0, `${failures} drain checks failed`);
      console.log(`child_process exit drain: ${RUNS} runs clean`);
    }
  });
}
