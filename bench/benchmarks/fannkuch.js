// Fannkuch-Redux Permutation Benchmark (from Computer Language Benchmarks Game & PyPerformance)
function fannkuch(n) {
    const p = new Int32Array(n);
    const q = new Int32Array(n);
    const count = new Int32Array(n);
    let sign = 1;
    let maxFlips = 0;
    let checksum = 0;

    for (let i = 0; i < n; i++) p[i] = i;
    let r = n;

    while (true) {
        while (r !== 1) {
            count[r - 1] = r;
            r--;
        }

        if (p[0] !== 0) {
            for (let i = 0; i < n; i++) q[i] = p[i];
            let flips = 0;
            let k = q[0];
            while (k !== 0) {
                for (let i = 0, j = k; i < j; i++, j--) {
                    const tmp = q[i];
                    q[i] = q[j];
                    q[j] = tmp;
                }
                flips++;
                k = q[0];
            }
            if (flips > maxFlips) maxFlips = flips;
            checksum += sign * flips;
        }

        // Permute
        if (sign === 1) {
            const tmp = p[0];
            p[0] = p[1];
            p[1] = tmp;
            sign = -1;
        } else {
            const tmp = p[1];
            p[1] = p[2];
            p[2] = tmp;
            sign = 1;

            for (let i = 2; i < n; i++) {
                if (count[i] !== 0) {
                    count[i]--;
                    if (count[i] !== 0) break;
                }
                count[i] = i + 1;
                const p0 = p[0];
                for (let j = 0; j <= i; j++) p[j] = p[j + 1];
                p[i + 1] = p0;
            }
        }
        if (count[n - 1] === 0) break;
    }

    return [checksum, maxFlips];
}

const start = Date.now();
const res = fannkuch(9);
const elapsed = Date.now() - start;

console.log("Fannkuch: checksum " + res[0] + " maxFlips " + res[1] + " in " + elapsed + "ms");
