// Layered top-to-bottom layout for questline graphs (Sugiyama style, kept small):
// cycle removal -> longest-path layering -> dummy nodes for long edges ->
// barycenter ordering -> iterative x placement.

export interface LayoutInput {
	nodes: number[];
	/** [from, to, kind] — from must come before to */
	edges: [number, number, string][];
	/** stable initial order inside a layer (e.g. quest level) */
	rank?: (id: number) => number;
}

export interface LayoutNode {
	id: number;
	x: number; // left
	y: number; // top
}

export interface LayoutEdge {
	from: number;
	to: number;
	kind: string;
	points: [number, number][];
}

export interface Layout {
	width: number;
	height: number;
	nodes: LayoutNode[];
	edges: LayoutEdge[];
}

export const NODE_W = 230;
export const NODE_H = 58;
const DUMMY_W = 8;
const H_GAP = 36;
const V_GAP = 46;
const PAD = 24;

type Key = string; // "q:<id>" for quests, "d:<n>" for dummies

export function layoutQuestline({ nodes, edges, rank = (id) => id }: LayoutInput): Layout {
	const ids = new Set(nodes);
	const succ = new Map<number, number[]>();
	const pred = new Map<number, number[]>();
	for (const n of nodes) {
		succ.set(n, []);
		pred.set(n, []);
	}

	// 1. Drop edges that would close a cycle (DFS back edges).
	const kept: [number, number, string][] = [];
	{
		const out = new Map<number, [number, string][]>();
		for (const [a, b, k] of edges) {
			if (!ids.has(a) || !ids.has(b) || a === b) continue;
			out.set(a, [...(out.get(a) ?? []), [b, k]]);
		}
		const state = new Map<number, 1 | 2>(); // 1 = on stack, 2 = done
		const visit = (start: number) => {
			const stack: [number, number][] = [[start, 0]];
			state.set(start, 1);
			while (stack.length) {
				const top = stack[stack.length - 1];
				const children = out.get(top[0]) ?? [];
				if (top[1] < children.length) {
					const [b, k] = children[top[1]++];
					const s = state.get(b);
					if (s === 1) continue; // back edge
					kept.push([top[0], b, k]);
					if (!s) {
						state.set(b, 1);
						stack.push([b, 0]);
					}
				} else {
					state.set(top[0], 2);
					stack.pop();
				}
			}
		};
		const incoming = new Set(edges.map((e) => e[1]));
		const order = [...nodes].sort((a, b) => Number(incoming.has(a)) - Number(incoming.has(b)) || rank(a) - rank(b));
		for (const n of order) if (!state.has(n)) visit(n);
	}
	for (const [a, b] of kept) {
		succ.get(a)!.push(b);
		pred.get(b)!.push(a);
	}

	// 2. Longest-path layering, then pull pure sources down next to their first child.
	const layer = new Map<number, number>();
	{
		const indeg = new Map(nodes.map((n) => [n, pred.get(n)!.length]));
		const queue = nodes.filter((n) => indeg.get(n) === 0).sort((a, b) => rank(a) - rank(b));
		for (const n of queue) layer.set(n, 0);
		while (queue.length) {
			const n = queue.shift()!;
			for (const s of succ.get(n)!) {
				layer.set(s, Math.max(layer.get(s) ?? 0, layer.get(n)! + 1));
				indeg.set(s, indeg.get(s)! - 1);
				if (indeg.get(s) === 0) queue.push(s);
			}
		}
		for (const n of nodes) {
			if (pred.get(n)!.length === 0 && succ.get(n)!.length > 0) {
				const minChild = Math.min(...succ.get(n)!.map((s) => layer.get(s)!));
				layer.set(n, Math.max(0, minChild - 1));
			}
		}
	}

	// 3. Graph over keys with dummy nodes so every edge spans exactly one layer.
	const keyLayer = new Map<Key, number>();
	const up = new Map<Key, Key[]>();
	const down = new Map<Key, Key[]>();
	const width = new Map<Key, number>();
	const addKey = (k: Key, l: number, w: number) => {
		keyLayer.set(k, l);
		up.set(k, []);
		down.set(k, []);
		width.set(k, w);
	};
	for (const n of nodes) addKey(`q:${n}`, layer.get(n)!, NODE_W);
	const chains: { from: number; to: number; kind: string; keys: Key[] }[] = [];
	let dummy = 0;
	for (const [a, b, kind] of kept) {
		const keys: Key[] = [`q:${a}`];
		for (let l = layer.get(a)! + 1; l < layer.get(b)!; l++) {
			const k = `d:${dummy++}`;
			addKey(k, l, DUMMY_W);
			keys.push(k);
		}
		keys.push(`q:${b}`);
		for (let i = 0; i + 1 < keys.length; i++) {
			down.get(keys[i])!.push(keys[i + 1]);
			up.get(keys[i + 1])!.push(keys[i]);
		}
		chains.push({ from: a, to: b, kind, keys });
	}

	// 4. Ordering by barycenter sweeps.
	const depth = Math.max(0, ...keyLayer.values()) + 1;
	const layers: Key[][] = Array.from({ length: depth }, () => []);
	const sortKey = (k: Key) => (k.startsWith('q:') ? rank(Number(k.slice(2))) : 0);
	for (const [k, l] of keyLayer) layers[l].push(k);
	layers[0].sort((a, b) => sortKey(a) - sortKey(b));
	const pos = new Map<Key, number>();
	const index = (l: number) => layers[l].forEach((k, i) => pos.set(k, i));
	index(0);
	const sweep = (l: number, neighbours: Map<Key, Key[]>) => {
		const bary = new Map<Key, number>();
		for (const k of layers[l]) {
			const ns = neighbours.get(k)!;
			bary.set(k, ns.length ? ns.reduce((s, n) => s + pos.get(n)!, 0) / ns.length : (pos.get(k) ?? 0));
		}
		layers[l].sort((a, b) => bary.get(a)! - bary.get(b)! || sortKey(a) - sortKey(b));
		layers[l] = centreHeavy(layers[l], bary);
		index(l);
	};
	// Siblings with the same parent position: the one continuing the line (most descendants)
	// goes in the middle, dead-end side quests spread out to both sides.
	const descendants = new Map<Key, number>();
	const countDesc = (k: Key): number => {
		if (!descendants.has(k)) {
			descendants.set(k, 0); // guard; graph is acyclic here
			descendants.set(k, down.get(k)!.reduce((s, c) => s + 1 + countDesc(c), 0));
		}
		return descendants.get(k)!;
	};
	const centreHeavy = (row: Key[], bary: Map<Key, number>): Key[] => {
		const out: Key[] = [];
		for (let i = 0; i < row.length; ) {
			let j = i;
			while (j < row.length && bary.get(row[j]) === bary.get(row[i])) j++;
			const run = row.slice(i, j);
			if (run.length > 2) {
				const byWeight = [...run].sort((a, b) => countDesc(b) - countDesc(a) || sortKey(a) - sortKey(b));
				const left: Key[] = [];
				const right: Key[] = [];
				byWeight.slice(1).forEach((k, n) => (n % 2 ? left : right).push(k));
				out.push(...left.reverse(), byWeight[0], ...right);
			} else {
				out.push(...run);
			}
			i = j;
		}
		return out;
	};
	for (let l = 1; l < depth; l++) sweep(l, up);
	for (let iter = 0; iter < 6; iter++) {
		for (let l = depth - 2; l >= 0; l--) sweep(l, down);
		for (let l = 1; l < depth; l++) sweep(l, up);
	}

	// 5. X placement: pull towards neighbours, keep order and spacing.
	const x = new Map<Key, number>(); // centre
	for (const row of layers) {
		let cursor = 0;
		for (const k of row) {
			x.set(k, cursor + width.get(k)! / 2);
			cursor += width.get(k)! + H_GAP;
		}
	}
	const place = (row: Key[], neighbours: Map<Key, Key[]>) => {
		if (!row.length) return;
		const desired = row.map((k) => {
			const ns = neighbours.get(k)!;
			return ns.length ? ns.reduce((s, n) => s + x.get(n)!, 0) / ns.length : x.get(k)!;
		});
		const placed = [...desired];
		const gap = (i: number) => (width.get(row[i - 1])! + width.get(row[i])!) / 2 + H_GAP;
		for (let i = 1; i < row.length; i++) placed[i] = Math.max(placed[i], placed[i - 1] + gap(i));
		for (let i = row.length - 2; i >= 0; i--) placed[i] = Math.min(placed[i], placed[i + 1] - gap(i + 1));
		// keep the layer centred on what its neighbours want
		const shift = desired.reduce((s, d, i) => s + d - placed[i], 0) / row.length;
		row.forEach((k, i) => x.set(k, placed[i] + shift));
	};
	for (let iter = 0; iter < 12; iter++) {
		for (let l = 1; l < depth; l++) place(layers[l], up);
		for (let l = depth - 2; l >= 0; l--) place(layers[l], down);
	}

	const minX = Math.min(...[...x].map(([k, v]) => v - width.get(k)! / 2));
	const offset = PAD - minX;
	const top = (l: number) => PAD + l * (NODE_H + V_GAP);
	const out: Layout = {
		width: Math.max(...[...x].map(([k, v]) => v + width.get(k)! / 2)) + offset + PAD,
		height: top(depth - 1) + NODE_H + PAD,
		nodes: nodes.map((n) => ({
			id: n,
			x: x.get(`q:${n}`)! + offset - NODE_W / 2,
			y: top(layer.get(n)!)
		})),
		edges: chains.map((c) => ({
			from: c.from,
			to: c.to,
			kind: c.kind,
			points: c.keys.map((k, i): [number, number] => {
				const cx = x.get(k)! + offset;
				const l = keyLayer.get(k)!;
				if (i === 0) return [cx, top(l) + NODE_H];
				if (i === c.keys.length - 1) return [cx, top(l)];
				return [cx, top(l) + NODE_H / 2];
			})
		}))
	};
	return out;
}
