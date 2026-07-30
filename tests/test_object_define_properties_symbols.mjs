function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function same(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`);
  }
}

const symbol = Symbol("descriptor");
const descriptorMap = {
  [symbol]: { value: 11, enumerable: true, configurable: true },
};

const defined = Object.defineProperties({}, descriptorMap);
same(defined[symbol], 11, "Object.defineProperties includes enumerable symbols");

const created = Object.create(null, descriptorMap);
same(created[symbol], 11, "Object.create includes enumerable symbols");

const hidden = Symbol("hidden");
const hiddenMap = {};
Object.defineProperty(hiddenMap, hidden, {
  value: { value: 12 },
  enumerable: false,
});
const withoutHidden = Object.defineProperties({}, hiddenMap);
assert(!Object.prototype.hasOwnProperty.call(withoutHidden, hidden),
  "non-enumerable symbol descriptor entries are ignored");

let symbolGetterCalls = 0;
const accessorSymbol = Symbol("accessor");
const accessorMap = {};
Object.defineProperty(accessorMap, accessorSymbol, {
  get() {
    symbolGetterCalls++;
    return { value: 13, enumerable: true };
  },
  enumerable: true,
});
same(Object.create(null, accessorMap)[accessorSymbol], 13,
  "symbol descriptor accessor supplies the descriptor");
same(symbolGetterCalls, 1, "symbol descriptor accessor is read once");

const order = [];
const firstSymbol = Symbol("first");
const secondSymbol = Symbol("second");
const orderedMap = {};
for (const key of ["first", firstSymbol, "second", secondSymbol]) {
  Object.defineProperty(orderedMap, key, {
    get() {
      order.push(key);
      return { value: String(key), enumerable: true };
    },
    enumerable: true,
  });
}
Object.defineProperties({}, orderedMap);
same(order.length, 4, "all mixed descriptor entries are read");
same(order[0], "first", "string keys retain insertion order");
same(order[1], "second", "all strings precede symbols");
same(order[2], firstSymbol, "symbols follow strings in insertion order");
same(order[3], secondSymbol, "second symbol retains insertion order");

const proxySymbol = Symbol("proxy");
const proxyLog = [];
const proxyTarget = {};
Object.defineProperty(proxyTarget, "string", {
  value: { value: 21, enumerable: true },
  enumerable: true,
  configurable: true,
});
Object.defineProperty(proxyTarget, proxySymbol, {
  value: { value: 22, enumerable: true },
  enumerable: true,
  configurable: true,
});
const proxyMap = new Proxy(proxyTarget, {
  ownKeys() {
    proxyLog.push("ownKeys");
    return [proxySymbol, "string"];
  },
  getOwnPropertyDescriptor(target, key) {
    proxyLog.push(`desc:${String(key)}`);
    return Reflect.getOwnPropertyDescriptor(target, key);
  },
  get(target, key, receiver) {
    proxyLog.push(`get:${String(key)}`);
    return Reflect.get(target, key, receiver);
  },
});
const fromProxy = Object.defineProperties({}, proxyMap);
same(fromProxy[proxySymbol], 22, "proxy symbol descriptor is defined");
same(fromProxy.string, 21, "proxy string descriptor is defined");
same(
  proxyLog.join("|"),
  "ownKeys|desc:Symbol(proxy)|get:Symbol(proxy)|desc:string|get:string",
  "proxy descriptor keys preserve trap order and each value is read once"
);

for (const [name, value, expectedTag] of [
  ["JSON", JSON, "JSON"],
  ["Math", Math, "Math"],
  ["array iterator prototype", Object.getPrototypeOf([][Symbol.iterator]()), "Array Iterator"],
]) {
  const tag = Object.getOwnPropertyDescriptor(value, Symbol.toStringTag);
  assert(tag, `${name} has an own @@toStringTag`);
  same(tag.value, expectedTag, `${name} @@toStringTag value`);
  same(tag.enumerable, false, `${name} @@toStringTag is non-enumerable`);
}

const namespace = await import("./fixtures/import_binding_length_dep.mjs");
const namespaceTag = Object.getOwnPropertyDescriptor(namespace, Symbol.toStringTag);
assert(namespaceTag, "module namespace has @@toStringTag");
same(namespaceTag.value, "Module", "module namespace @@toStringTag value");
same(namespaceTag.enumerable, false, "module namespace @@toStringTag is non-enumerable");
same(namespaceTag.writable, false, "module namespace @@toStringTag is non-writable");
same(namespaceTag.configurable, false, "module namespace @@toStringTag is non-configurable");

assert(Object.create({}, JSON), "Object.create ignores JSON's non-enumerable tag");
assert(Object.create({}, Math), "Object.create ignores Math's non-enumerable tag");

console.log("OK: test_object_define_properties_symbols");
