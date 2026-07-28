// String Manipulation Benchmark - non-regex string ops only.
// Regex lives in regex_dna; keeping it out of here stops the two from
// measuring the same engine path.
function runStringBench(iterations) {
    const base = "The quick brown fox jumps over the lazy dog. ";
    const large = base.repeat(5e3);
    let checksum = 0;

    for (let i = 0; i < iterations; i++) {
        // Each pass restarts from `large`; deriving from the previous result
        // leaves nothing to split on after the first iteration.
        let s = large.split(" ").join("-");
        s = s.toUpperCase();
        s = s.toLowerCase();

        checksum += s.length;
        checksum += s.indexOf("lazy");
        checksum += s.lastIndexOf("brown");
        checksum += s.slice(s.length >> 2, s.length >> 1).length;
        checksum += s.startsWith("the") ? 1 : 0;
        checksum += s.endsWith("dog.") ? 1 : 0;
    }

    return checksum;
}

const start = Date.now();
const checksum = runStringBench(50);
const elapsed = Date.now() - start;

console.log("String: checksum " + checksum + " in " + elapsed + "ms");
