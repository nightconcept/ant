// benchmarks/fib.ts
function fib(n) {
  if (n <= 1) return n;
  return fib(n - 1) + fib(n - 2);
}
var start = Date.now();
var N = 36;
var result = fib(N);
var elapsed = Date.now() - start;
console.log(`Fibonacci(${N}) = ${result} (took ${elapsed}ms)`);
