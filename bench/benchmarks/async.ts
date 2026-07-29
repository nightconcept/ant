async function runAsyncBench() {
  let count = 0;
  async function step(n: number): Promise<number> {
    if (n <= 0) return 1;
    await Promise.resolve();
    return (await step(n - 1)) + 1;
  }

  const tasks: Promise<number>[] = [];
  for (let i = 0; i < 2000; i++) {
    tasks.push(step(100));
  }

  const results = await Promise.all(tasks);
  const total = results.reduce((a, b) => a + b, 0);
  console.log(`Async bench finished: total ${total}`);
}

runAsyncBench();
