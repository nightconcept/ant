interface DataItem {
  id: number;
  name: string;
  tags: string[];
  active: boolean;
  score: number;
}

function runJsonBench() {
  const items: DataItem[] = [];
  for (let i = 0; i < 5000; i++) {
    items.push({
      id: i,
      name: `item_${i}`,
      tags: ["alpha", "beta", "gamma", "delta"],
      active: i % 2 === 0,
      score: i * 1.5,
    });
  }

  let totalLength = 0;
  for (let iter = 0; iter < 100; iter++) {
    const jsonStr = JSON.stringify(items);
    const parsed = JSON.parse(jsonStr) as DataItem[];
    totalLength += parsed.length;
  }
  console.log(`JSON bench finished: ${totalLength} items processed`);
}

runJsonBench();
