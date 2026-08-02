# WinterTC Coverage Matrix

Status: active
Last reviewed: 2026-08-01
Owner: theMackabu

This matrix tracks the TC55 Minimum Common Web API draft dated 31 July 2026.
The normative index is at
[min-common-api.proposal.wintertc.org](https://min-common-api.proposal.wintertc.org/).

The API-surface contract checks that each listed global exists. The selected
WPT paths check behavior. A matrix entry does not mean that Ant passes it.
Read the current WinterTC manifest for pass and failure evidence.

| TC55 surface | Local contract | Behavioral evidence |
| --- | --- | --- |
| `AbortController`, `AbortSignal` | `api-surface.js` | `dom/abort/**/*.any.js` |
| `Event`, `EventTarget`, `CustomEvent`, `ErrorEvent`, `MessageEvent`, `PromiseRejectionEvent` | `api-surface.js` | `dom/events/**/*.any.js` and `dom/abort/**/*.any.js` |
| `MessageChannel`, `MessagePort` | `api-surface.js` | API contract; add focused WPT coverage in Phase 6 |
| `DOMException` | `api-surface.js` | DOM, streams, fetch, and Web Crypto selections |
| `Headers`, `Request`, `Response` | `api-surface.js` | `fetch/api/headers/*.any.js`, `fetch/api/request/*.any.js`, and `fetch/api/response/*.any.js` |
| `FormData` | `api-surface.js` | API contract; add focused WPT coverage in Phase 6 |
| `Blob`, `File` | `api-surface.js` | `FileAPI/blob/**/*.any.js` and `FileAPI/file/File-constructor*.any.js` |
| `CompressionStream`, `DecompressionStream` | `api-surface.js` | `compression/**/*.any.js` |
| `ByteLengthQueuingStrategy`, `CountQueuingStrategy` | `api-surface.js` | `streams/**/*.any.js` |
| `ReadableByteStreamController`, `ReadableStream`, `ReadableStreamBYOBReader`, `ReadableStreamBYOBRequest`, `ReadableStreamDefaultController`, `ReadableStreamDefaultReader` | `api-surface.js` | `streams/**/*.any.js` |
| `TransformStream`, `TransformStreamDefaultController` | `api-surface.js` | `streams/**/*.any.js` |
| `WritableStream`, `WritableStreamDefaultController`, `WritableStreamDefaultWriter` | `api-surface.js` | `streams/**/*.any.js` |
| `TextDecoder`, `TextDecoderStream`, `TextEncoder`, `TextEncoderStream` | `api-surface.js` | `encoding/**/*.any.js` |
| `URL`, `URLSearchParams` | `api-surface.js` | `url/**/*.any.js` |
| `URLPattern` | `api-surface.js` | `urlpattern/**/*.any.js` |
| `Crypto`, `CryptoKey`, `SubtleCrypto` | `api-surface.js` | `WebCryptoAPI/**/*.any.js` |
| `Performance` | `api-surface.js` | `hr-time/**/*.any.js` |
| `WebAssembly.Global`, `Instance`, `Memory`, `Module`, `Table`, `Tag`, `Exception`, `CompileError`, `LinkError`, `RuntimeError` | `api-surface.js` | `wasm/jsapi/**/*.any.js` |
| `globalThis`, `self` | `api-surface.js` | API contract and every selected WPT file |
| `atob()`, `btoa()` | `api-surface.js` | API contract; add focused WPT coverage in Phase 6 |
| `clearTimeout()`, `clearInterval()`, `setTimeout()`, `setInterval()` | `api-surface.js` | API contract and asynchronous WPT tests |
| `navigator.userAgent` | `api-surface.js` | API contract; add syntax validation in Phase 6 |
| `onerror`, `onunhandledrejection`, `onrejectionhandled` | `api-surface.js` | API contract; document the TC55 global-scope exception if Ant uses it |
| `queueMicrotask()`, `reportError()`, `structuredClone()` | `api-surface.js` | API contract plus DOM and streams selections |
| `fetch()` | `api-surface.js` | Shell-compatible fetch value-object tests; network behavior waits for the WPT server phase |
| `console` | `api-surface.js` | `console/**/*.any.js` |
| `crypto`, `performance` | `api-surface.js` | Web Crypto and high-resolution time selections |
| `WebAssembly.compile()`, `compileStreaming()`, `instantiate()`, `instantiateStreaming()`, `validate()`, `JSTag` | `api-surface.js` | `wasm/jsapi/**/*.any.js` |

The manifest classifies Window-only and server-backed sources explicitly.
Do not remove an exclusion until the required environment exists or the test is
proved applicable to Ant's global scope.
