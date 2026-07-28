// ES6 Generators & Iterator Protocol Benchmark
function* rangeGenerator(start, end) {
    for (let i = start; i < end; i++) {
        yield i * 2;
    }
}

function* delegateGenerator(count) {
    for (let i = 0; i < count; i++) {
        yield* rangeGenerator(i * 10, i * 10 + 5);
    }
}

function runGeneratorsBenchmark(iterations) {
    let total = 0;
    for (let i = 0; i < iterations; i++) {
        const gen = delegateGenerator(10);
        let res = gen.next();
        while (!res.done) {
            total += res.value;
            res = gen.next();
        }
    }
    return total;
}

const start = Date.now();
const result = runGeneratorsBenchmark(5000);
const elapsed = Date.now() - start;

console.log("Generators: sum " + result + " in " + elapsed + "ms");
