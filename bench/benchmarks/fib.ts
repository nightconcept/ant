function fib(n: number): number {
  if (n <= 1) return n;
  return fib(n - 1) + fib(n - 2);
}

const start = Date.now();
const N = 36;
const result = fib(N);
const elapsed = Date.now() - start;
console.log(`Fibonacci(${N}) = ${result} (took ${elapsed}ms)`);
