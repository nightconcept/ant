// Web Streams Pipeline Benchmark - ReadableStream -> TransformStream -> sink.
// Covers src/streams/ (readable, transform, writable, pipes, queuing), which
// nothing else in the suite exercises. Uses only the WHATWG API, so it stays
// portable across all five runtimes.
function makeSource(chunks: number, chunkSize: number): ReadableStream<Uint8Array> {
    let i = 0;
    return new ReadableStream({
        pull(controller: ReadableStreamDefaultController<Uint8Array>) {
            if (i >= chunks) {
                controller.close();
                return;
            }
            const buf = new Uint8Array(chunkSize);
            for (let j = 0; j < chunkSize; j++) buf[j] = (i + j) & 0xff;
            i++;
            controller.enqueue(buf);
        }
    });
}

function makeXorTransform(mask: number): TransformStream<Uint8Array, Uint8Array> {
    return new TransformStream({
        transform(chunk: Uint8Array, controller: TransformStreamDefaultController<Uint8Array>) {
            const out = new Uint8Array(chunk.length);
            for (let j = 0; j < chunk.length; j++) out[j] = chunk[j] ^ mask;
            controller.enqueue(out);
        }
    });
}

function makeSumTransform(): TransformStream<Uint8Array, number> {
    return new TransformStream({
        transform(chunk: Uint8Array, controller: TransformStreamDefaultController<number>) {
            let sum = 0;
            for (let j = 0; j < chunk.length; j++) sum += chunk[j];
            controller.enqueue(sum);
        }
    });
}

async function runStreamPipe(rounds: number, chunks: number, chunkSize: number): Promise<number> {
    let checksum = 0;

    for (let r = 0; r < rounds; r++) {
        const stream = makeSource(chunks, chunkSize)
            .pipeThrough(makeXorTransform(r & 0xff))
            .pipeThrough(makeSumTransform());

        const reader = stream.getReader();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            checksum += value;
        }
    }

    return checksum;
}

const start = Date.now();
runStreamPipe(16, 200, 512).then((result: number) => {
    const elapsed = Date.now() - start;
    console.log("StreamPipe: checksum " + result + " in " + elapsed + "ms");
});
