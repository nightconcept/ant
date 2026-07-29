// Map & Set Collection Benchmark - insert, lookup, delete and iterate.
// Covers src/modules/collections.c, which nothing else in the suite touches.
function runMapSetBenchmark(size, passes) {
    let checksum = 0;

    for (let pass = 0; pass < passes; pass++) {
        const byId = new Map();
        const seen = new Set();

        // Insert: string keys hit the hashing path, integer keys the fast path.
        for (let i = 0; i < size; i++) {
            byId.set("key_" + i, i * 3);
            byId.set(i, i);
            seen.add(i % 1024);
        }

        // Lookup, including misses.
        for (let i = 0; i < size; i++) {
            checksum += byId.get("key_" + i);
            checksum += byId.has(i) ? 1 : 0;
            checksum += byId.has(size + i) ? 100 : 0;
            checksum += seen.has(i % 2048) ? 1 : 0;
        }

        // Delete half, forcing tombstone handling and rehash.
        for (let i = 0; i < size; i += 2) {
            byId.delete("key_" + i);
            seen.delete(i % 1024);
        }

        // Iterate what survives.
        for (const value of byId.values()) {
            if (typeof value === "number") checksum += value & 7;
        }
        for (const key of seen) {
            checksum += key & 3;
        }

        checksum += byId.size + seen.size;
    }

    return checksum;
}

const start = Date.now();
const result = runMapSetBenchmark(20000, 9);
const elapsed = Date.now() - start;

console.log("MapSet: checksum " + result + " in " + elapsed + "ms");
