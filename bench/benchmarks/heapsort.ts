// HeapSort Benchmark (Classic Sorting & Non-Sequential Memory Access)
function heapify(arr: Int32Array, n: number, i: number): void {
    let largest = i;
    const left = 2 * i + 1;
    const right = 2 * i + 2;

    if (left < n && arr[left] > arr[largest]) {
        largest = left;
    }
    if (right < n && arr[right] > arr[largest]) {
        largest = right;
    }

    if (largest !== i) {
        const swap = arr[i];
        arr[i] = arr[largest];
        arr[largest] = swap;
        heapify(arr, n, largest);
    }
}

function heapSort(arr: Int32Array): void {
    const n = arr.length;
    for (let i = Math.floor(n / 2) - 1; i >= 0; i--) {
        heapify(arr, n, i);
    }
    for (let i = n - 1; i > 0; i--) {
        const temp = arr[0];
        arr[0] = arr[i];
        arr[i] = temp;
        heapify(arr, i, 0);
    }
}

function runHeapSortBenchmark(size: number): number {
    const data = new Int32Array(size);
    for (let i = 0; i < size; i++) {
        data[i] = (i * 1103515245 + 12345) & 0x7fffffff;
    }

    heapSort(data);

    let checksum = 0;
    for (let i = 0; i < size; i += 100) {
        checksum += data[i];
    }
    return checksum;
}

const start = Date.now();
const cs = runHeapSortBenchmark(150000);
const elapsed = Date.now() - start;

console.log("HeapSort: checksum " + cs + " in " + elapsed + "ms");
