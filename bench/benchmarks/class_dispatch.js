// Class Hierarchy & Megamorphic Dispatch Benchmark.
// Replaces the old ic_polymorphic micro-benchmark: same inline-cache pressure,
// but through class syntax, super chains and accessors rather than object
// literals, so it exercises the paths real code takes.
class Shape {
    constructor(id) {
        this.id = id;
        this._area = 0;
    }
    get area() { return this._area; }
    set area(v) { this._area = v; }
    describe() { return this.id; }
    weight() { return this.area * 2; }
}

class Circle extends Shape {
    constructor(id, r) { super(id); this.r = r; this.area = r * r * 3; }
    describe() { return super.describe() + this.r; }
    weight() { return super.weight() + this.r; }
}

class Square extends Shape {
    constructor(id, s) { super(id); this.s = s; this.area = s * s; }
    describe() { return super.describe() + this.s; }
    weight() { return super.weight() - this.s; }
}

class Triangle extends Shape {
    constructor(id, b, h) { super(id); this.b = b; this.h = h; this.area = b * h / 2; }
    describe() { return super.describe() + this.b + this.h; }
    weight() { return super.weight() + this.b - this.h; }
}

class Rect extends Shape {
    constructor(id, w, h) { super(id); this.w = w; this.h = h; this.area = w * h; }
    describe() { return super.describe() + this.w; }
    weight() { return super.weight() * 2 - this.h; }
}

function buildShapes(count) {
    const shapes = [];
    for (let i = 0; i < count; i++) {
        switch (i & 3) {
            case 0: shapes.push(new Circle(i, (i % 7) + 1)); break;
            case 1: shapes.push(new Square(i, (i % 5) + 1)); break;
            case 2: shapes.push(new Triangle(i, (i % 4) + 1, (i % 6) + 1)); break;
            default: shapes.push(new Rect(i, (i % 3) + 1, (i % 8) + 1)); break;
        }
    }
    return shapes;
}

function runClassDispatch(count, passes) {
    const shapes = buildShapes(count);
    let checksum = 0;

    for (let pass = 0; pass < passes; pass++) {
        // Megamorphic: the call site sees four receiver shapes in rotation.
        for (let i = 0; i < shapes.length; i++) {
            const s = shapes[i];
            checksum += s.weight();
            checksum += s.area;
            s.area = s.area + 1;
        }
        // instanceof and accessor reads on the same rotating receivers.
        for (let i = 0; i < shapes.length; i++) {
            const s = shapes[i];
            if (s instanceof Circle) checksum += 1;
            else if (s instanceof Square) checksum += 2;
            else if (s instanceof Triangle) checksum += 3;
            else checksum += 4;
        }
    }

    return checksum;
}

const start = Date.now();
const result = runClassDispatch(20000, 14);
const elapsed = Date.now() - start;

console.log("ClassDispatch: checksum " + result + " in " + elapsed + "ms");
