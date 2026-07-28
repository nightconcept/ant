// Richards Task Scheduler Benchmark (Classic V8, PyPerformance & Smalltalk OS Simulation)
class TaskControlBlock {
    link: TaskControlBlock | null = null;
    id: number;
    priority: number;
    queue: Packet | null = null;
    state: number = 0;

    constructor(id: number, priority: number, queue: Packet | null, link: TaskControlBlock | null) {
        this.id = id;
        this.priority = priority;
        this.queue = queue;
        this.link = link;
    }

    run(packet: Packet | null): TaskControlBlock | null {
        if (this.queue !== null) {
            packet = this.queue;
            this.queue = packet.link;
        }
        return packet !== null ? this.execute(packet) : null;
    }

    execute(packet: Packet): TaskControlBlock | null {
        return null;
    }
}

class Packet {
    link: Packet | null = null;
    id: number;
    kind: number;
    a1: number = 0;
    a2: number[] = [0, 0, 0, 0];

    constructor(link: Packet | null, id: number, kind: number) {
        this.link = link;
        this.id = id;
        this.kind = kind;
    }
}

function runRichards(iterations: number): number {
    let taskCount = 0;
    let packetCount = 0;

    for (let iter = 0; iter < iterations; iter++) {
        let head: Packet | null = null;
        for (let i = 0; i < 100; i++) {
            head = new Packet(head, i, i % 3);
            packetCount++;
        }

        let currBlock: TaskControlBlock | null = new TaskControlBlock(1, 10, head, null);
        while (currBlock !== null && currBlock.queue !== null) {
            taskCount++;
            currBlock.queue = currBlock.queue.link;
        }
    }
    return taskCount + packetCount;
}

const start = Date.now();
const res = runRichards(25000);
const elapsed = Date.now() - start;

console.log("Richards: processed " + res + " ops in " + elapsed + "ms");
