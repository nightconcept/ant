// Regex DNA Sequence Processing Benchmark (from Computer Language Benchmarks Game & PyPerformance)
function runRegexDNABenchmark(): number {
    let dnaSequence = ">ONE Homo sapiens alu\n";
    const bases = ["agctntkbmrswyvhdAGCTNTKBMRSWYVHD", "GGCC", "AAAA", "TTTT", "CCCC"];
    for (let i = 0; i < 2500; i++) {
        dnaSequence += bases[i % bases.length] + "\n";
    }

    // Strip header and newlines
    let sequence = dnaSequence.replace(/^>.*$/mg, "").replace(/\n/g, "");
    const initialLen = sequence.length;

    // Pattern matching counts
    const variants = [
        /agcttcaa/gi,
        /ccg[ag]ta/gi,
        /gctg[at]ca/gi,
        /[ac]gttca/gi,
        /ag[act]tca/gi,
        /agct[act]ca/gi,
        /agctu[act]a/gi,
        /agctta[acg]/gi,
        /agctta[act]/gi
    ];

    let matchCount = 0;
    for (let i = 0; i < variants.length; i++) {
        const matches = sequence.match(variants[i]);
        if (matches) matchCount += matches.length;
    }

    // IUPAC code replacements
    const replacements: [RegExp, string][] = [
        [/B/g, "(c|g|t)"],
        [/D/g, "(a|g|t)"],
        [/H/g, "(a|c|t)"],
        [/K/g, "(g|t)"],
        [/M/g, "(a|c)"],
        [/N/g, "(a|c|g|t)"],
        [/R/g, "(a|g)"],
        [/S/g, "(c|g)"],
        [/V/g, "(a|c|g)"],
        [/W/g, "(a|t)"],
        [/Y/g, "(c|t)"]
    ];

    for (let i = 0; i < replacements.length; i++) {
        sequence = sequence.replace(replacements[i][0], replacements[i][1]);
    }

    return initialLen + sequence.length + matchCount;
}

const start = Date.now();
const res = runRegexDNABenchmark();
const elapsed = Date.now() - start;

console.log("RegexDNA: processed result " + res + " in " + elapsed + "ms");
