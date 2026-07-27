interface User {
  id: number;
  age: number;
  val: number;
}

function runArrayBench() {
  const users: User[] = [];
  for (let i = 0; i < 100000; i++) {
    users.push({ id: i, age: (i * 37) % 80, val: (i * 17) % 10000 });
  }

  let sum = 0;
  for (let iter = 0; iter < 10; iter++) {
    const filtered = users.filter(u => u.age > 18 && u.age < 65);
    const mapped = filtered.map(u => u.val * 2);
    mapped.sort((a, b) => a - b);
    sum += mapped.reduce((acc, curr) => acc + (curr % 100), 0);
  }

  console.log(`Array bench finished: sum ${sum}`);
}

runArrayBench();
