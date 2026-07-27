// Proxy & Reflect Interception Benchmark
interface Target {
    [key: string]: number;
}

function runProxyBenchmark(iterations: number): number {
    const target: Target = { count: 0, multiplier: 2 };
    let trapAccesses = 0;

    const handler: ProxyHandler<Target> = {
        get(t, prop: string) {
            trapAccesses++;
            return prop in t ? t[prop] : 0;
        },
        set(t, prop: string, value: number) {
            trapAccesses++;
            t[prop] = value;
            return true;
        }
    };

    const proxy = new Proxy(target, handler);

    for (let i = 0; i < iterations; i++) {
        proxy.count = (proxy.count as number) + 1;
        proxy.total = (proxy.count as number) * (proxy.multiplier as number);
    }

    return trapAccesses + target.total;
}

const start = Date.now();
const res = runProxyBenchmark(100000);
const elapsed = Date.now() - start;

console.log("ProxyTrap: result " + res + " in " + elapsed + "ms");
