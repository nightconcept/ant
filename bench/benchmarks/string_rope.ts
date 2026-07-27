// Rope & String Concatenation Benchmark
function runStringRope(): number {
    let str = "initial_base_string_chunk_0123456789_abcdefghijklmnopqrstuvwxyz";
    let totalLen = 0;
    const pieces: string[] = [];

    for (let i = 0; i < 50000; i++) {
        const token = "token_" + (i % 100) + "_" + (i * 17 % 9999);
        str += token;
        if (i % 500 === 0) {
            pieces.push(str.substring(str.length - 100));
            str = str.slice(str.length / 2);
        }
    }

    const joined = pieces.join("|");
    totalLen = str.length + joined.length;
    const matchIdx = joined.indexOf("token_42");
    return totalLen + matchIdx;
}

const start = Date.now();
const res = runStringRope();
const elapsed = Date.now() - start;

console.log("StringRope: result " + res + " in " + elapsed + "ms");
