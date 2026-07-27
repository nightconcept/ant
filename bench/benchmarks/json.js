// benchmarks/json.ts
function runJsonBench() {
  const items = [];
  for (let i = 0; i < 5e3; i++) {
    items.push({
      id: i,
      name: `item_${i}`,
      tags: ["alpha", "beta", "gamma", "delta"],
      active: i % 2 === 0,
      score: i * 1.5
    });
  }
  let totalLength = 0;
  for (let iter = 0; iter < 100; iter++) {
    const jsonStr = JSON.stringify(items);
    const parsed = JSON.parse(jsonStr);
    totalLength += parsed.length;
  }
  console.log(`JSON bench finished: ${totalLength} items processed`);
}
runJsonBench();
