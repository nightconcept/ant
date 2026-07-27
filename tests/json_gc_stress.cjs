// Hammers the JSON paths while forcing constant GC pressure, so any missing
// root in the new stringify/parse code shows up as corruption or a crash.
let churn = [];
function pressure() {
  for (let i = 0; i < 200; i++) churn.push({ pad: "x".repeat(64), n: i });
  if (churn.length > 20000) churn = [];
}

const wide = {};
for (let i = 0; i < 200; i++) wide["key_with_a_longish_name_" + i] = "value_" + i;

let ok = 0;
for (let round = 0; round < 400; round++) {
  pressure();

  const nested = { d: new Date(round), s: new String("boxed" + round), n: new Number(round) };
  const deep = { a: [{ b: [{ c: { d: [1, 2, { e: "leaf" + round }] } }] }] };
  const withToJSON = { toJSON() { pressure(); return { r: round, wide }; } };
  const withReplacer = { a: 1, b: { c: 2 }, d: [3, 4] };

  const s1 = JSON.stringify(nested);
  const s2 = JSON.stringify(deep, null, 2);
  const s3 = JSON.stringify(withToJSON);
  const s4 = JSON.stringify(withReplacer, (k, v) => { pressure(); return v; }, "\t");
  const s5 = JSON.stringify(wide);

  const p1 = JSON.parse(s2);
  const p2 = JSON.parse(s5);
  const p3 = JSON.parse(s3, (k, v) => { pressure(); return v; });

  if (p1.a[0].b[0].c.d[2].e !== "leaf" + round) throw new Error("deep roundtrip broke at " + round);
  if (p2.key_with_a_longish_name_199 !== "value_199") throw new Error("wide roundtrip broke at " + round);
  if (p3.r !== round) throw new Error("toJSON roundtrip broke at " + round);
  if (JSON.parse(s1).n !== round) throw new Error("wrapper roundtrip broke at " + round);
  if (!s4.includes('"c": 2')) throw new Error("replacer indent broke at " + round);

  ok++;
}

console.log("json gc stress: ok (" + ok + " rounds)");
