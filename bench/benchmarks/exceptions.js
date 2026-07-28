// Exception Throw/Catch Benchmark - stack unwinding, Error construction and
// stack capture across call depth. Previously unmeasured entirely.
class AppError extends Error {
    constructor(code, message) {
        super(message);
        this.name = "AppError";
        this.code = code;
    }
}

function deep(depth, failAt) {
    if (depth === failAt) {
        throw new AppError(depth, "failed at depth " + depth);
    }
    return deep(depth + 1, failAt) + 1;
}

// Stack strings are engine-specific, so their contents can never reach the
// checksum. They still have to be read, or stack capture goes unmeasured -
// this sink keeps the read alive without making the result engine-dependent.
let stackSink = 0;

function runExceptions(iterations) {
    let checksum = 0;

    for (let i = 0; i < iterations; i++) {
        // Unwind a deep stack. Depth rotates so no single path stays hot.
        const failAt = 4 + (i % 12);
        try {
            checksum += deep(0, failAt);
        } catch (e) {
            checksum += e.code;
            // Capture is the expensive half on most engines; skipping the read
            // would leave that path unmeasured.
            if (typeof e.stack === "string") stackSink += e.stack.length;
        }

        // Shallow throw/catch of a plain value - no Error allocation, no stack.
        try {
            if (i & 1) throw i;
            checksum += 1;
        } catch (v) {
            checksum += v & 3;
        }

        // finally on the unwind path.
        try {
            try {
                throw new TypeError("inner " + i);
            } finally {
                checksum += 1;
            }
        } catch (e) {
            checksum += e.message.length;
        }
    }

    return checksum;
}

const start = Date.now();
const result = runExceptions(15000);
const elapsed = Date.now() - start;

// `stacks` is reported as a boolean so the sink cannot be optimised away while
// staying identical across engines.
console.log("Exceptions: checksum " + result + " stacks " + (stackSink > 0) +
    " in " + elapsed + "ms");
