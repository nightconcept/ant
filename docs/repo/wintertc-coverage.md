# WinterTC Coverage Matrix

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

Source table: `tests/wintertc/api-surface.json` (TC55 draft 2026-07-31).
Regenerate this file and the runtime assertion with
`python3 scripts/generate_wintertc_surface.py`.
A row records coverage; it does not claim that Ant passes the row.

| TC55 interface | Required members | Behavioral evidence | Documented deviation or gap |
| --- | --- | --- | --- |
| `AbortController` | `AbortController.prototype.abort`, `AbortController.prototype.signal` | dom/abort/**/*.any.js | none |
| `AbortSignal` | `AbortSignal.abort`, `AbortSignal.any`, `AbortSignal.timeout`, `AbortSignal.prototype.aborted`, `AbortSignal.prototype.onabort`, `AbortSignal.prototype.reason`, `AbortSignal.prototype.throwIfAborted` | dom/abort/**/*.any.js | none |
| `Event` | `Event.prototype.bubbles`, `Event.prototype.cancelable`, `Event.prototype.composed`, `Event.prototype.composedPath`, `Event.prototype.currentTarget`, `Event.prototype.defaultPrevented`, `Event.prototype.eventPhase`, `Event.prototype.isTrusted`, `Event.prototype.preventDefault`, `Event.prototype.stopImmediatePropagation`, `Event.prototype.stopPropagation`, `Event.prototype.target`, `Event.prototype.timeStamp`, `Event.prototype.type` | dom/events/**/*.any.js | none |
| `EventTarget` | `EventTarget.prototype.addEventListener`, `EventTarget.prototype.dispatchEvent`, `EventTarget.prototype.removeEventListener` | dom/events/**/*.any.js | none |
| `CustomEvent` | `CustomEvent.prototype.detail`, `CustomEvent.prototype.initCustomEvent` | dom/events/**/*.any.js | none |
| `ErrorEvent` | `ErrorEvent.prototype.colno`, `ErrorEvent.prototype.error`, `ErrorEvent.prototype.filename`, `ErrorEvent.prototype.lineno`, `ErrorEvent.prototype.message` | API contract | Not required when Ant uses the TC55 non-EventTarget global exception. |
| `MessageChannel` | `MessageChannel.prototype.port1`, `MessageChannel.prototype.port2` | API contract | Focused WPT coverage is pending. |
| `MessageEvent` | `MessageEvent.prototype.data`, `MessageEvent.prototype.initMessageEvent`, `MessageEvent.prototype.lastEventId`, `MessageEvent.prototype.origin`, `MessageEvent.prototype.ports`, `MessageEvent.prototype.source` | dom/events/**/*.any.js | none |
| `MessagePort` | `MessagePort.prototype.close`, `MessagePort.prototype.onmessage`, `MessagePort.prototype.onmessageerror`, `MessagePort.prototype.postMessage`, `MessagePort.prototype.start` | API contract | Focused WPT coverage is pending. |
| `PromiseRejectionEvent` | `PromiseRejectionEvent.prototype.promise`, `PromiseRejectionEvent.prototype.reason` | API contract | Not required when Ant uses the TC55 non-EventTarget global exception. |
| `DOMException` | `DOMException.prototype.code`, `DOMException.prototype.message`, `DOMException.prototype.name` | DOM, streams, fetch, and Web Crypto WPT selections | none |
| `Headers` | `Headers.prototype.append`, `Headers.prototype.delete`, `Headers.prototype.entries`, `Headers.prototype.forEach`, `Headers.prototype.get`, `Headers.prototype.getSetCookie`, `Headers.prototype.has`, `Headers.prototype.keys`, `Headers.prototype.set`, `Headers.prototype.values` | fetch/api/headers/*.any.js | none |
| `Request` | `Request.prototype.arrayBuffer`, `Request.prototype.blob`, `Request.prototype.body`, `Request.prototype.bodyUsed`, `Request.prototype.bytes`, `Request.prototype.cache`, `Request.prototype.clone`, `Request.prototype.credentials`, `Request.prototype.destination`, `Request.prototype.duplex`, `Request.prototype.formData`, `Request.prototype.headers`, `Request.prototype.integrity`, `Request.prototype.isHistoryNavigation`, `Request.prototype.isReloadNavigation`, `Request.prototype.json`, `Request.prototype.keepalive`, `Request.prototype.method`, `Request.prototype.mode`, `Request.prototype.redirect`, `Request.prototype.referrer`, `Request.prototype.referrerPolicy`, `Request.prototype.signal`, `Request.prototype.text`, `Request.prototype.url` | fetch/api/request/*.any.js | Network-backed cases require the WPT server. |
| `Response` | `Response.error`, `Response.json`, `Response.redirect`, `Response.prototype.arrayBuffer`, `Response.prototype.blob`, `Response.prototype.body`, `Response.prototype.bodyUsed`, `Response.prototype.bytes`, `Response.prototype.clone`, `Response.prototype.formData`, `Response.prototype.headers`, `Response.prototype.json`, `Response.prototype.ok`, `Response.prototype.redirected`, `Response.prototype.status`, `Response.prototype.statusText`, `Response.prototype.text`, `Response.prototype.type`, `Response.prototype.url` | fetch/api/response/*.any.js | Network-backed cases require the WPT server. |
| `FormData` | `FormData.prototype.append`, `FormData.prototype.delete`, `FormData.prototype.entries`, `FormData.prototype.forEach`, `FormData.prototype.get`, `FormData.prototype.getAll`, `FormData.prototype.has`, `FormData.prototype.keys`, `FormData.prototype.set`, `FormData.prototype.values` | API contract | Focused WPT coverage is pending. |
| `Blob` | `Blob.prototype.arrayBuffer`, `Blob.prototype.bytes`, `Blob.prototype.size`, `Blob.prototype.slice`, `Blob.prototype.stream`, `Blob.prototype.text`, `Blob.prototype.type` | FileAPI/blob/**/*.any.js | none |
| `File` | `File.prototype.lastModified`, `File.prototype.name`, `File.prototype.webkitRelativePath` | FileAPI/file/File-constructor*.any.js | none |
| `CompressionStream` | `CompressionStream.prototype.readable`, `CompressionStream.prototype.writable` | compression/**/*.any.js | Server-backed sources remain excluded. |
| `DecompressionStream` | `DecompressionStream.prototype.readable`, `DecompressionStream.prototype.writable` | compression/**/*.any.js | none |
| `ByteLengthQueuingStrategy` | `ByteLengthQueuingStrategy.prototype.highWaterMark`, `ByteLengthQueuingStrategy.prototype.size` | streams/**/*.any.js | none |
| `CountQueuingStrategy` | `CountQueuingStrategy.prototype.highWaterMark`, `CountQueuingStrategy.prototype.size` | streams/**/*.any.js | none |
| `ReadableByteStreamController` | `ReadableByteStreamController.prototype.byobRequest`, `ReadableByteStreamController.prototype.close`, `ReadableByteStreamController.prototype.desiredSize`, `ReadableByteStreamController.prototype.enqueue`, `ReadableByteStreamController.prototype.error` | streams/**/*.any.js | none |
| `ReadableStream` | `ReadableStream.from`, `ReadableStream.prototype.cancel`, `ReadableStream.prototype.getReader`, `ReadableStream.prototype.locked`, `ReadableStream.prototype.pipeThrough`, `ReadableStream.prototype.pipeTo`, `ReadableStream.prototype.tee`, `ReadableStream.prototype.values` | streams/**/*.any.js | none |
| `ReadableStreamBYOBReader` | `ReadableStreamBYOBReader.prototype.cancel`, `ReadableStreamBYOBReader.prototype.closed`, `ReadableStreamBYOBReader.prototype.read`, `ReadableStreamBYOBReader.prototype.releaseLock` | streams/**/*.any.js | none |
| `ReadableStreamBYOBRequest` | `ReadableStreamBYOBRequest.prototype.respond`, `ReadableStreamBYOBRequest.prototype.respondWithNewView`, `ReadableStreamBYOBRequest.prototype.view` | streams/**/*.any.js | none |
| `ReadableStreamDefaultController` | `ReadableStreamDefaultController.prototype.close`, `ReadableStreamDefaultController.prototype.desiredSize`, `ReadableStreamDefaultController.prototype.enqueue`, `ReadableStreamDefaultController.prototype.error` | streams/**/*.any.js | none |
| `ReadableStreamDefaultReader` | `ReadableStreamDefaultReader.prototype.cancel`, `ReadableStreamDefaultReader.prototype.closed`, `ReadableStreamDefaultReader.prototype.read`, `ReadableStreamDefaultReader.prototype.releaseLock` | streams/**/*.any.js | none |
| `TransformStream` | `TransformStream.prototype.readable`, `TransformStream.prototype.writable` | streams/**/*.any.js | none |
| `TransformStreamDefaultController` | `TransformStreamDefaultController.prototype.desiredSize`, `TransformStreamDefaultController.prototype.enqueue`, `TransformStreamDefaultController.prototype.error`, `TransformStreamDefaultController.prototype.terminate` | streams/**/*.any.js | none |
| `WritableStream` | `WritableStream.prototype.abort`, `WritableStream.prototype.close`, `WritableStream.prototype.getWriter`, `WritableStream.prototype.locked` | streams/**/*.any.js | none |
| `WritableStreamDefaultController` | `WritableStreamDefaultController.prototype.error`, `WritableStreamDefaultController.prototype.signal` | streams/**/*.any.js | none |
| `WritableStreamDefaultWriter` | `WritableStreamDefaultWriter.prototype.abort`, `WritableStreamDefaultWriter.prototype.close`, `WritableStreamDefaultWriter.prototype.closed`, `WritableStreamDefaultWriter.prototype.desiredSize`, `WritableStreamDefaultWriter.prototype.ready`, `WritableStreamDefaultWriter.prototype.releaseLock`, `WritableStreamDefaultWriter.prototype.write` | streams/**/*.any.js | none |
| `TextDecoder` | `TextDecoder.prototype.decode`, `TextDecoder.prototype.encoding`, `TextDecoder.prototype.fatal`, `TextDecoder.prototype.ignoreBOM` | encoding/**/*.any.js | none |
| `TextDecoderStream` | `TextDecoderStream.prototype.encoding`, `TextDecoderStream.prototype.fatal`, `TextDecoderStream.prototype.ignoreBOM`, `TextDecoderStream.prototype.readable`, `TextDecoderStream.prototype.writable` | encoding/**/*.any.js | none |
| `TextEncoder` | `TextEncoder.prototype.encode`, `TextEncoder.prototype.encodeInto`, `TextEncoder.prototype.encoding` | encoding/**/*.any.js | none |
| `TextEncoderStream` | `TextEncoderStream.prototype.encoding`, `TextEncoderStream.prototype.readable`, `TextEncoderStream.prototype.writable` | encoding/**/*.any.js | none |
| `URL` | `URL.canParse`, `URL.parse`, `URL.prototype.hash`, `URL.prototype.host`, `URL.prototype.hostname`, `URL.prototype.href`, `URL.prototype.origin`, `URL.prototype.password`, `URL.prototype.pathname`, `URL.prototype.port`, `URL.prototype.protocol`, `URL.prototype.search`, `URL.prototype.searchParams`, `URL.prototype.toJSON`, `URL.prototype.toString`, `URL.prototype.username` | url/**/*.any.js | Server-backed data files remain excluded. |
| `URLSearchParams` | `URLSearchParams.prototype.append`, `URLSearchParams.prototype.delete`, `URLSearchParams.prototype.entries`, `URLSearchParams.prototype.forEach`, `URLSearchParams.prototype.get`, `URLSearchParams.prototype.getAll`, `URLSearchParams.prototype.has`, `URLSearchParams.prototype.keys`, `URLSearchParams.prototype.set`, `URLSearchParams.prototype.size`, `URLSearchParams.prototype.sort`, `URLSearchParams.prototype.toString`, `URLSearchParams.prototype.values` | url/**/*.any.js | none |
| `URLPattern` | `URLPattern.prototype.exec`, `URLPattern.prototype.hash`, `URLPattern.prototype.hasRegExpGroups`, `URLPattern.prototype.hostname`, `URLPattern.prototype.password`, `URLPattern.prototype.pathname`, `URLPattern.prototype.port`, `URLPattern.prototype.protocol`, `URLPattern.prototype.search`, `URLPattern.prototype.test`, `URLPattern.prototype.username` | urlpattern/**/*.any.js | Server-backed generated data remains excluded. |
| `Crypto` | `Crypto.prototype.getRandomValues`, `Crypto.prototype.randomUUID`, `Crypto.prototype.subtle` | WebCryptoAPI/**/*.any.js | none |
| `CryptoKey` | `CryptoKey.prototype.algorithm`, `CryptoKey.prototype.extractable`, `CryptoKey.prototype.type`, `CryptoKey.prototype.usages` | WebCryptoAPI/**/*.any.js | none |
| `SubtleCrypto` | `SubtleCrypto.prototype.decrypt`, `SubtleCrypto.prototype.deriveBits`, `SubtleCrypto.prototype.deriveKey`, `SubtleCrypto.prototype.digest`, `SubtleCrypto.prototype.encrypt`, `SubtleCrypto.prototype.exportKey`, `SubtleCrypto.prototype.generateKey`, `SubtleCrypto.prototype.importKey`, `SubtleCrypto.prototype.sign`, `SubtleCrypto.prototype.unwrapKey`, `SubtleCrypto.prototype.verify`, `SubtleCrypto.prototype.wrapKey` | WebCryptoAPI/**/*.any.js | none |
| `Performance` | `Performance.prototype.now`, `Performance.prototype.timeOrigin`, `Performance.prototype.toJSON` | hr-time/**/*.any.js | none |

| TC55 global | Kind | Behavioral evidence | Documented deviation or gap |
| --- | --- | --- | --- |
| `globalThis` | property | API contract | none |
| `atob` | function | API contract | Focused WPT coverage is pending. |
| `btoa` | function | API contract | Focused WPT coverage is pending. |
| `clearTimeout` | function | Asynchronous selected WPT files | none |
| `clearInterval` | function | Asynchronous selected WPT files | none |
| `navigator.userAgent` | string | API contract | ABNF validation is pending. |
| `onerror` | property | API contract | Not required for a non-EventTarget global. |
| `onunhandledrejection` | property | API contract | Not required for a non-EventTarget global. |
| `onrejectionhandled` | property | API contract | Not required for a non-EventTarget global. |
| `queueMicrotask` | function | API contract and selected WPT files | none |
| `reportError` | function | API contract | Focused WPT coverage is pending. |
| `self` | property | API contract and every selected WPT file | none |
| `setTimeout` | function | Asynchronous selected WPT files | none |
| `setInterval` | function | Asynchronous selected WPT files | none |
| `structuredClone` | function | DOM and streams WPT selections | none |
| `fetch` | function | Fetch value-object WPT selections | Network behavior requires the WPT server. |
| `console` | property | console/**/*.any.js | none |
| `crypto` | property | WebCryptoAPI/**/*.any.js | none |
| `performance` | property | hr-time/**/*.any.js | none |

## WebAssembly namespace

`WebAssembly.Global`, `WebAssembly.Instance`, `WebAssembly.Memory`, `WebAssembly.Module`, `WebAssembly.Table`, `WebAssembly.Tag`, `WebAssembly.Exception`, `WebAssembly.CompileError`, `WebAssembly.LinkError`, `WebAssembly.RuntimeError`, `WebAssembly.compile`, `WebAssembly.compileStreaming`, `WebAssembly.instantiate`, `WebAssembly.instantiateStreaming`, `WebAssembly.JSTag`, `WebAssembly.validate`

Behavioral evidence: `wasm/jsapi/**/*.any.js`.
