// benchmarks/fib.ts
function fib(n) {
  if (n <= 1) return n;
  return fib(n - 1) + fib(n - 2);
}
var start = Date.now();
var result = fib(34);
var elapsed = Date.now() - start;
console.log(`Fibonacci(34) = ${result} (took ${elapsed}ms)`);
