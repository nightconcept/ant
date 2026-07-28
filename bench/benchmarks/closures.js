// Closure Allocation & Capture Benchmark - exercises upvalue handling in
// src/silver/: closures that escape their defining frame, shared captured
// state between siblings, and loop-scoped `let` bindings.
function makeCounter(start, step) {
    let value = start;
    // Two closures over the same binding: the capture cannot be unboxed away.
    return {
        next() { value += step; return value; },
        peek() { return value; }
    };
}

function makeAdders(n) {
    const adders = [];
    for (let i = 0; i < n; i++) {
        // Fresh binding per iteration - one upvalue cell per closure.
        adders.push((x) => x + i);
    }
    return adders;
}

function compose(fns) {
    return fns.reduce((f, g) => (x) => g(f(x)), (x) => x);
}

function runClosures(passes) {
    let checksum = 0;

    for (let pass = 0; pass < passes; pass++) {
        // Escaping closures over shared mutable state.
        const counter = makeCounter(pass, 3);
        for (let i = 0; i < 200; i++) checksum += counter.next();
        checksum += counter.peek();

        // Many short-lived closures, each with its own captured cell.
        const adders = makeAdders(200);
        for (let i = 0; i < adders.length; i++) checksum += adders[i](pass);

        // Deep composition: a chain of closures each capturing the previous.
        const pipeline = compose(adders.slice(0, 40));
        checksum += pipeline(pass);

        // Closure captured by an inner function two levels down.
        const outer = pass;
        const nested = () => () => outer * 2;
        checksum += nested()();
    }

    return checksum;
}

const start = Date.now();
const result = runClosures(3000);
const elapsed = Date.now() - start;

console.log("Closures: checksum " + result + " in " + elapsed + "ms");
