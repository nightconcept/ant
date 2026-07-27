// Proxy & Reflect Interception Benchmark
function runProxyBenchmark(iterations) {
    const target = { count: 0, multiplier: 2 };
    let trapAccesses = 0;

    const handler = {
        get(t, prop) {
            trapAccesses++;
            return prop in t ? t[prop] : 0;
        },
        set(t, prop, value) {
            trapAccesses++;
            t[prop] = value;
            return true;
        }
    };

    const proxy = new Proxy(target, handler);

    for (let i = 0; i < iterations; i++) {
        proxy.count = proxy.count + 1;
        proxy.total = proxy.count * proxy.multiplier;
    }

    return trapAccesses + target.total;
}

const start = Date.now();
const res = runProxyBenchmark(100000);
const elapsed = Date.now() - start;

console.log("ProxyTrap: result " + res + " in " + elapsed + "ms");
