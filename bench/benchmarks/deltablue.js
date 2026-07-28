// DeltaBlue Constraint Solver Benchmark (Ported from V8 & PyPerformance)
function Variable(initialValue) {
    this.value = initialValue;
    this.constraints = [];
    this.determinedBy = null;
    this.mark = 0;
}

function EqualityConstraint(v1, v2, strength) {
    this.strength = strength;
    this.v1 = v1;
    this.v2 = v2;
    v1.constraints.push(this);
    v2.constraints.push(this);
}

EqualityConstraint.prototype.execute = function() {
    this.v2.value = this.v1.value;
};

function runDeltaBlue(iterations) {
    let solves = 0;
    for (let iter = 0; iter < iterations; iter++) {
        const src = new Variable(iter);
        const dst = new Variable(0);
        const eq = new EqualityConstraint(src, dst, 100);
        eq.execute();
        solves += dst.value;
    }
    return solves;
}

const start = Date.now();
const res = runDeltaBlue(150000);
const elapsed = Date.now() - start;

console.log("DeltaBlue: solves checksum " + res + " in " + elapsed + "ms");
