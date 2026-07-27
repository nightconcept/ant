// Large Object Graph & AST Node Construction Benchmark
interface ASTNode {
    type: string;
    id: number;
    name: string;
    loc: { start: number; end: number };
    children: ASTNode[];
    meta: { visited: boolean; flag: number };
}

function createGraph(count: number): ASTNode[] {
    const nodes: ASTNode[] = [];
    for (let i = 0; i < count; i++) {
        nodes.push({
            type: i % 2 === 0 ? "Identifier" : "Literal",
            id: i,
            name: "node_" + i,
            loc: { start: i * 10, end: i * 10 + 9 },
            children: [],
            meta: { visited: false, flag: i & 0xff }
        });
    }
    for (let i = 0; i < count - 1; i++) {
        if (i % 3 === 0) {
            nodes[i].children.push(nodes[i + 1]);
        }
    }
    return nodes;
}

function traverse(nodes: ASTNode[]): number {
    let visitedCount = 0;
    for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        if (!node.meta.visited) {
            node.meta.visited = true;
            visitedCount++;
        }
        for (let j = 0; j < node.children.length; j++) {
            if (!node.children[j].meta.visited) {
                node.children[j].meta.visited = true;
                visitedCount++;
            }
        }
    }
    return visitedCount;
}

const start = Date.now();
const graph = createGraph(150000);
const visited = traverse(graph);
const elapsed = Date.now() - start;

console.log("ObjectGraph: processed " + visited + " nodes in " + elapsed + "ms");
