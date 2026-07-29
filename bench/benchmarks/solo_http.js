// HTTP Server Round-Trip Benchmark - Ant only.
//
// Covers src/http/, src/net/ and src/modules/server.c, none of which any other
// benchmark touches. There is no portable server API across the five runtimes
// (Ant uses Ant.serve, node uses node:http, deno/bun each differ), so this runs
// on Ant alone and is tracked against Ant's own history rather than a
// cross-runtime ratio. Everything happens in one process: the server binds an
// ephemeral port, the same process drives requests against it, then stops it.
const REQUESTS = 1800;
const CONCURRENCY = 24;

const server = Ant.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch(request) {
        const url = new URL(request.url);
        if (url.pathname === "/json") {
            return new Response(JSON.stringify({ path: url.pathname, q: url.searchParams.get("i") }), {
                headers: { "content-type": "application/json" }
            });
        }
        if (url.pathname === "/echo") {
            return new Response(url.searchParams.get("i") || "", {
                headers: { "content-type": "text/plain", "x-bench": "1" }
            });
        }
        return new Response("ok");
    }
});

const base = "http://127.0.0.1:" + server.port;

async function worker(id, count) {
    let bytes = 0;
    for (let i = 0; i < count; i++) {
        const n = id * count + i;
        // Rotate the three routes so header, body and JSON paths all get hit.
        switch (n % 3) {
            case 0: {
                const r = await fetch(base + "/");
                bytes += (await r.text()).length;
                break;
            }
            case 1: {
                const r = await fetch(base + "/echo?i=" + n);
                bytes += (await r.text()).length + (r.headers.get("x-bench") ? 1 : 0);
                break;
            }
            default: {
                const r = await fetch(base + "/json?i=" + n);
                const body = await r.json();
                bytes += body.path.length + String(body.q).length;
                break;
            }
        }
    }
    return bytes;
}

const start = Date.now();
const per = Math.floor(REQUESTS / CONCURRENCY);
const workers = [];
for (let i = 0; i < CONCURRENCY; i++) workers.push(worker(i, per));

Promise.all(workers).then((results) => {
    const total = results.reduce((a, b) => a + b, 0);
    const elapsed = Date.now() - start;
    server.stop();
    console.log("SoloHttp: " + (per * CONCURRENCY) + " requests, " + total +
        " bytes in " + elapsed + "ms");
});
