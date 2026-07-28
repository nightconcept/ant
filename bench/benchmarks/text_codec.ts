// TextEncoder & TextDecoder UTF-8 Transcoding Benchmark
function runTextCodecBenchmark(): number {
    let sourceText = "";
    for (let i = 0; i < 5000; i++) {
        sourceText += "Hello World, Unicode UTF-8 test string: 🚀 € £ ¥ 𐍈 " + i + " ";
    }

    const encoder = new TextEncoder();
    const decoder = new TextDecoder("utf-8");
    let totalBytes = 0;

    for (let iter = 0; iter < 300; iter++) {
        const encoded = encoder.encode(sourceText);
        totalBytes += encoded.byteLength;
        const decoded = decoder.decode(encoded);
        totalBytes += decoded.length;
    }

    return totalBytes;
}

const start = Date.now();
const bytesProcessed = runTextCodecBenchmark();
const elapsed = Date.now() - start;

console.log("TextCodec: processed " + bytesProcessed + " bytes in " + elapsed + "ms");
