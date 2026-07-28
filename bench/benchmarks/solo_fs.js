// Filesystem Churn Benchmark - Ant only.
//
// Covers src/modules/fs.c. Kept Ant-only alongside solo_http: node and bun
// would run this unchanged, but the point is tracking Ant's own I/O over time,
// and mixing in runtimes whose fs layer is a different design makes the ratio
// meaningless rather than informative.
//
// Everything is written under a scratch directory that is removed on exit, so
// the benchmark leaves nothing behind even if run from the repo root.
//
// Static ESM imports: Ant runs bare .js as a module, where `require` is not
// defined. Being Ant-only, this does not have to satisfy node's CJS default.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const FILES = 600;
const PASSES = 8;

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ant-bench-fs-"));

function runFsBenchmark() {
    let checksum = 0;
    const payload = "x".repeat(2048);

    try {
        for (let pass = 0; pass < PASSES; pass++) {
            // Write.
            for (let i = 0; i < FILES; i++) {
                fs.writeFileSync(path.join(dir, "f" + i + ".txt"), payload + i);
            }

            // Stat and read back.
            for (let i = 0; i < FILES; i++) {
                const p = path.join(dir, "f" + i + ".txt");
                checksum += fs.statSync(p).size;
                checksum += fs.readFileSync(p, "utf8").length;
            }

            // Append, then re-read to force a second size.
            for (let i = 0; i < FILES; i += 2) {
                const p = path.join(dir, "f" + i + ".txt");
                fs.appendFileSync(p, "tail");
                checksum += fs.readFileSync(p, "utf8").length;
            }

            // Directory listing.
            checksum += fs.readdirSync(dir).length;

            // Rename half, then delete everything for the next pass.
            for (let i = 0; i < FILES; i += 2) {
                fs.renameSync(path.join(dir, "f" + i + ".txt"), path.join(dir, "r" + i + ".txt"));
            }
            for (const name of fs.readdirSync(dir)) {
                fs.unlinkSync(path.join(dir, name));
            }
        }
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }

    return checksum;
}

const start = Date.now();
const result = runFsBenchmark();
const elapsed = Date.now() - start;

console.log("SoloFs: checksum " + result + " in " + elapsed + "ms");
