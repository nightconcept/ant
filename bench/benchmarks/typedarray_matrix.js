// TypedArray Numerical Computation Benchmark
function runTypedArrayBenchmark(size) {
    const arrA = new Float64Array(size);
    const arrB = new Float64Array(size);
    const result = new Float64Array(size);

    for (let i = 0; i < size; i++) {
        arrA[i] = i * 0.5;
        arrB[i] = (size - i) * 0.25;
    }

    for (let pass = 0; pass < 20; pass++) {
        for (let i = 0; i < size; i++) {
            result[i] = (arrA[i] * 1.5) + (arrB[i] * 0.8) - (i % 7);
        }
    }

    let checksum = 0;
    for (let i = 0; i < size; i += 100) {
        checksum += result[i];
    }
    return checksum;
}

const start = Date.now();
const cs = runTypedArrayBenchmark(100000);
const elapsed = Date.now() - start;

console.log("TypedArrayMatrix: checksum " + cs + " in " + elapsed + "ms");
