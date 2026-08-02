const requiredGlobals = [
  'AbortController',
  'AbortSignal',
  'Event',
  'EventTarget',
  'CustomEvent',
  'ErrorEvent',
  'MessageChannel',
  'MessageEvent',
  'MessagePort',
  'PromiseRejectionEvent',
  'DOMException',
  'Headers',
  'Request',
  'Response',
  'FormData',
  'Blob',
  'File',
  'CompressionStream',
  'DecompressionStream',
  'ByteLengthQueuingStrategy',
  'CountQueuingStrategy',
  'ReadableByteStreamController',
  'ReadableStream',
  'ReadableStreamBYOBReader',
  'ReadableStreamBYOBRequest',
  'ReadableStreamDefaultController',
  'ReadableStreamDefaultReader',
  'TransformStream',
  'TransformStreamDefaultController',
  'WritableStream',
  'WritableStreamDefaultController',
  'WritableStreamDefaultWriter',
  'TextDecoder',
  'TextDecoderStream',
  'TextEncoder',
  'TextEncoderStream',
  'URL',
  'URLSearchParams',
  'URLPattern',
  'Crypto',
  'CryptoKey',
  'SubtleCrypto',
  'Performance',
];

const requiredFunctions = [
  'atob',
  'btoa',
  'clearTimeout',
  'clearInterval',
  'queueMicrotask',
  'reportError',
  'setTimeout',
  'setInterval',
  'structuredClone',
  'fetch',
];

const missing = [];
for (const name of requiredGlobals) {
  if (typeof globalThis[name] !== 'function') missing.push(`${name} constructor`);
}
for (const name of requiredFunctions) {
  if (typeof globalThis[name] !== 'function') missing.push(`${name}()`);
}
for (const name of ['console', 'crypto', 'performance', 'navigator', 'self']) {
  if (!(name in globalThis)) missing.push(name);
}
if (!globalThis.navigator || typeof globalThis.navigator.userAgent !== 'string') {
  missing.push('navigator.userAgent');
}

const wasm = globalThis.WebAssembly;
for (const name of [
  'Global', 'Instance', 'Memory', 'Module', 'Table', 'Tag', 'Exception',
  'CompileError', 'LinkError', 'RuntimeError', 'compile', 'compileStreaming',
  'instantiate', 'instantiateStreaming', 'validate',
]) {
  if (!wasm || typeof wasm[name] !== 'function') missing.push(`WebAssembly.${name}`);
}

if (missing.length > 0) {
  throw new Error(`Missing WinterTC API surface:\n${missing.join('\n')}`);
}
