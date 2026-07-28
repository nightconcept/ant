// DeltaBlue Constraint Solver Benchmark (Ported from V8 & PyPerformance)
class Variable {
    value: number;
    constraints: Constraint[] = [];
    determinedBy: Constraint | null = null;
    mark: number = 0;

    constructor(initialValue: number) {
        this.value = initialValue;
    }
}

abstract class Constraint {
    strength: number;

    constructor(strength: number) {
        this.strength = strength;
    }

    abstract execute(): void;
}

class EqualityConstraint extends Constraint {
    v1: Variable;
    v2: Variable;

    constructor(v1: Variable, v2: Variable, strength: number) {
        super(strength);
        this.v1 = v1;
        this.v2 = v2;
        v1.constraints.push(this);
        v2.constraints.push(this);
    }

    execute(): void {
        this.v2.value = this.v1.value;
    }
}

function runDeltaBlue(iterations: number): number {
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
