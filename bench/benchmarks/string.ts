function runStringBench() {
  let baseStr = "The quick brown fox jumps over the lazy dog. ";
  let largeStr = baseStr.repeat(5000);

  let processed = largeStr;
  for (let i = 0; i < 50; i++) {
    processed = processed.replace(/fox/g, "cat").replace(/dog/g, "wolf");
    processed = processed.toUpperCase();
    const parts = processed.split(" ");
    processed = parts.join("-");
  }

  console.log(`String bench finished: final length ${processed.length}`);
}

runStringBench();
