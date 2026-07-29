// ES6 Generators & Iterator Protocol Benchmark
function* rangeGenerator(start: number, end: number): Generator<number, void, unknown> {
    for (let i = start; i < end; i++) {
        yield i * 2;
    }
}

function* delegateGenerator(count: number): Generator<number, void, unknown> {
    for (let i = 0; i < count; i++) {
        yield* rangeGenerator(i * 10, i * 10 + 5);
    }
}

function runGeneratorsBenchmark(iterations: number): number {
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
const result = runGeneratorsBenchmark(7000);
const elapsed = Date.now() - start;

console.log("Generators: sum " + result + " in " + elapsed + "ms");
