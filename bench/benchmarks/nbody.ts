// N-Body Physics Simulation Benchmark (from Computer Language Benchmarks Game & PyPerformance)
const PI = 3.141592653589793;
const SOLAR_MASS = 4 * PI * PI;
const DAYS_PER_YEAR = 365.24;

class Body {
    x: number; y: number; z: number;
    vx: number; vy: number; vz: number;
    mass: number;

    constructor(x: number, y: number, z: number, vx: number, vy: number, vz: number, mass: number) {
        this.x = x; this.y = y; this.z = z;
        this.vx = vx; this.vy = vy; this.vz = vz;
        this.mass = mass;
    }
}

function initBodies(): Body[] {
    return [
        new Body(0, 0, 0, 0, 0, 0, SOLAR_MASS), // Sun
        new Body( // Jupiter
            4.8414314424647209e+00, -1.1603201304427534e+00, -1.0362204447112310e-01,
            1.6600766427440369e-03 * DAYS_PER_YEAR, 7.6990111841974042e-03 * DAYS_PER_YEAR, -6.9046001697206302e-05 * DAYS_PER_YEAR,
            9.5479193842432660e-04 * SOLAR_MASS
        ),
        new Body( // Saturn
            8.3433667182445795e+00, 4.1247985641243047e+00, -4.0352341711432138e-01,
            -2.7674251072686241e-03 * DAYS_PER_YEAR, 4.9985280123491723e-03 * DAYS_PER_YEAR, 2.3041729757376393e-05 * DAYS_PER_YEAR,
            2.8588598066613081e-04 * SOLAR_MASS
        )
    ];
}

function advance(bodies: Body[], dt: number): void {
    const len = bodies.length;
    for (let i = 0; i < len; i++) {
        const bi = bodies[i];
        for (let j = i + 1; j < len; j++) {
            const bj = bodies[j];
            const dx = bi.x - bj.x;
            const dy = bi.y - bj.y;
            const dz = bi.z - bj.z;
            const dist2 = dx * dx + dy * dy + dz * dz;
            const mag = dt / (dist2 * Math.sqrt(dist2));
            bi.vx -= dx * bj.mass * mag;
            bi.vy -= dy * bj.mass * mag;
            bi.vz -= dz * bj.mass * mag;
            bj.vx += dx * bi.mass * mag;
            bj.vy += dy * bi.mass * mag;
            bj.vz += dz * bi.mass * mag;
        }
    }
    for (let i = 0; i < len; i++) {
        const b = bodies[i];
        b.x += dt * b.vx;
        b.y += dt * b.vy;
        b.z += dt * b.vz;
    }
}

function energy(bodies: Body[]): number {
    let e = 0;
    const len = bodies.length;
    for (let i = 0; i < len; i++) {
        const bi = bodies[i];
        e += 0.5 * bi.mass * (bi.vx * bi.vx + bi.vy * bi.vy + bi.vz * bi.vz);
        for (let j = i + 1; j < len; j++) {
            const bj = bodies[j];
            const dx = bi.x - bj.x;
            const dy = bi.y - bj.y;
            const dz = bi.z - bj.z;
            const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            e -= (bi.mass * bj.mass) / dist;
        }
    }
    return e;
}

const bodies = initBodies();
const start = Date.now();
const e1 = energy(bodies);
for (let n = 0; n < 75000; n++) {
    advance(bodies, 0.01);
}
const e2 = energy(bodies);
const elapsed = Date.now() - start;

console.log("NBody: energy diff " + (e2 - e1).toFixed(9) + " in " + elapsed + "ms");
