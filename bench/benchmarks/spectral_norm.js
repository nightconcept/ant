// Spectral Norm Matrix Eigenvalue Benchmark (from Computer Language Benchmarks Game & PyPerformance)
function evalA(i, j) {
    return 1.0 / (((i + j) * (i + j + 1)) / 2 + i + 1);
}

function evalAtimesFortran(v, Atv, n) {
    for (let i = 0; i < n; i++) {
        let sum = 0.0;
        for (let j = 0; j < n; j++) {
            sum += evalA(i, j) * v[j];
        }
        Atv[i] = sum;
    }
}

function evalAtAtimesFortran(v, AtAv, u, n) {
    evalAtimesFortran(v, u, n);
    evalAtimesFortran(u, AtAv, n);
}

function spectralNorm(n) {
    const u = new Float64Array(n);
    const v = new Float64Array(n);
    const w = new Float64Array(n);
    for (let i = 0; i < n; i++) u[i] = 1.0;

    for (let i = 0; i < 10; i++) {
        evalAtAtimesFortran(u, v, w, n);
        evalAtAtimesFortran(v, u, w, n);
    }

    let vBv = 0.0;
    let vv = 0.0;
    for (let i = 0; i < n; i++) {
        vBv += u[i] * v[i];
        vv += v[i] * v[i];
    }
    return Math.sqrt(vBv / vv);
}

const start = Date.now();
const result = spectralNorm(500);
const elapsed = Date.now() - start;

console.log("SpectralNorm: result " + result.toFixed(9) + " in " + elapsed + "ms");
