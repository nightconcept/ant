// GC Pressure Benchmark - a large long-lived working set churned against heavy
// short-lived allocation, so objects must survive several collections and get
// promoted. object_graph allocates and dies young, which leaves the promotion
// and old-generation paths in src/gc/ largely untouched.
function makeRecord(i: number): any {
    return {
        id: i,
        key: "rec_" + (i & 1023),
        payload: [i, i + 1, i + 2, i + 3],
        meta: { tag: i & 7, live: true },
        next: null
    };
}

function runGcPressure(liveSize: number, churn: number, passes: number): number {
    // Retained across every pass: this is what forces promotion rather than
    // letting the nursery absorb everything.
    const live = new Array(liveSize);
    for (let i = 0; i < liveSize; i++) live[i] = makeRecord(i);

    // Link a fraction of them so the collector has real edges to trace.
    for (let i = 0; i < liveSize; i += 4) {
        live[i].next = live[(i * 7 + 1) % liveSize];
    }

    let checksum = 0;

    for (let pass = 0; pass < passes; pass++) {
        // Short-lived garbage: allocated, touched, dropped.
        for (let i = 0; i < churn; i++) {
            const tmp = makeRecord(i + pass);
            tmp.next = live[(i + pass) % liveSize];
            checksum += tmp.meta.tag + tmp.payload[1];
        }

        // Replace part of the live set, so old objects die and new ones are
        // promoted in their place instead of the set staying static.
        for (let i = pass % 8; i < liveSize; i += 8) {
            live[i] = makeRecord(i + pass);
        }

        // Traverse the retained graph - keeps it genuinely reachable.
        for (let i = 0; i < liveSize; i += 16) {
            const rec = live[i];
            checksum += rec.meta.tag;
            if (rec.next !== null) checksum += rec.next.id & 15;
        }
    }

    return checksum;
}

const start = Date.now();
const result = runGcPressure(40000, 20000, 12);
const elapsed = Date.now() - start;

console.log("GcPressure: checksum " + result + " in " + elapsed + "ms");
