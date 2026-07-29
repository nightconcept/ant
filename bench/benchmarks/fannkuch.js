// Fannkuch-Redux Permutation Benchmark (from Computer Language Benchmarks Game & PyPerformance)
function fannkuch(n) {
    const p = new Int32Array(n);
    const q = new Int32Array(n);
    const count = new Int32Array(n);
    let permCount = 0;
    let maxFlips = 0;
    let checksum = 0;

    for (let i = 0; i < n; i++) p[i] = i;
    let r = n;

    while (true) {
        while (r !== 1) {
            count[r - 1] = r;
            r--;
        }

        for (let i = 0; i < n; i++) q[i] = p[i];
        let flips = 0;
        let k = q[0];
        while (k !== 0) {
            const half = (k + 1) >> 1;
            for (let i = 0; i < half; i++) {
                const tmp = q[i];
                q[i] = q[k - i];
                q[k - i] = tmp;
            }
            flips++;
            k = q[0];
        }
        if (flips > maxFlips) maxFlips = flips;
        checksum += (permCount & 1) === 0 ? flips : -flips;

        // Next permutation, rotating the first r entries left by one.
        while (true) {
            if (r === n) return [checksum, maxFlips];
            const p0 = p[0];
            for (let i = 0; i < r; i++) p[i] = p[i + 1];
            p[r] = p0;
            count[r]--;
            if (count[r] > 0) break;
            r++;
        }
        permCount++;
    }
}

const start = Date.now();
const res = fannkuch(9);
const elapsed = Date.now() - start;

console.log("Fannkuch: checksum " + res[0] + " maxFlips " + res[1] + " in " + elapsed + "ms");
