// Polymorphic Inline Cache (IC) Property Lookup Benchmark
interface ShapeA { kind: "A"; val: number; a: number }
interface ShapeB { kind: "B"; val: number; b: string }
interface ShapeC { kind: "C"; val: number; c: boolean }
interface ShapeD { kind: "D"; val: number; d: number[] }
type Shape = ShapeA | ShapeB | ShapeC | ShapeD;

function createShapes(count: number): Shape[] {
    const shapes: Shape[] = [];
    for (let i = 0; i < count; i++) {
        const mod = i % 4;
        if (mod === 0) shapes.push({ kind: "A", val: i, a: i * 2 });
        else if (mod === 1) shapes.push({ kind: "B", val: i, b: "str_" + i });
        else if (mod === 2) shapes.push({ kind: "C", val: i, c: i % 2 === 0 });
        else shapes.push({ kind: "D", val: i, d: [i, i + 1] });
    }
    return shapes;
}

function processPolymorphic(shapes: Shape[], iterations: number): number {
    let sum = 0;
    const len = shapes.length;
    for (let iter = 0; iter < iterations; iter++) {
        for (let i = 0; i < len; i++) {
            const s = shapes[i];
            sum += s.val;
            if (s.kind === "A") {
                sum += (s as ShapeA).a;
            } else if (s.kind === "C") {
                sum += (s as ShapeC).c ? 1 : 0;
            }
        }
    }
    return sum;
}

const start = Date.now();
const shapes = createShapes(1000);
const checksum = processPolymorphic(shapes, 500);
const elapsed = Date.now() - start;

console.log("ICPolymorphic: checksum " + checksum + " in " + elapsed + "ms");
