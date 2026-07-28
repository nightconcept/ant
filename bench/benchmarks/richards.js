// Richards Task Scheduler Benchmark (Classic V8, PyPerformance & Smalltalk OS Simulation)
function TaskControlBlock(id, priority, queue, link) {
    this.id = id;
    this.priority = priority;
    this.queue = queue;
    this.link = link;
    this.state = 0;
}

TaskControlBlock.prototype.run = function(packet) {
    if (this.queue !== null) {
        packet = this.queue;
        this.queue = packet.link;
    }
    return packet !== null ? this.execute(packet) : null;
};

TaskControlBlock.prototype.execute = function(packet) {
    return null;
};

function Packet(link, id, kind) {
    this.link = link;
    this.id = id;
    this.kind = kind;
    this.a1 = 0;
    this.a2 = [0, 0, 0, 0];
}

function runRichards(iterations) {
    let taskCount = 0;
    let packetCount = 0;

    for (let iter = 0; iter < iterations; iter++) {
        let head = null;
        for (let i = 0; i < 100; i++) {
            head = new Packet(head, i, i % 3);
            packetCount++;
        }

        let currBlock = new TaskControlBlock(1, 10, head, null);
        while (currBlock !== null && currBlock.queue !== null) {
            taskCount++;
            currBlock.queue = currBlock.queue.link;
        }
    }
    return taskCount + packetCount;
}

const start = Date.now();
const res = runRichards(3250);
const elapsed = Date.now() - start;

console.log("Richards: processed " + res + " ops in " + elapsed + "ms");
