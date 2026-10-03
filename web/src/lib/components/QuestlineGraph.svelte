<script lang="ts">
	import { site } from '$lib/context.svelte';
	import { progress } from '$lib/progress.svelte';
	import { CLASS_BITS } from '$lib/format';
	import { layoutQuestline, NODE_H, NODE_W } from '$lib/questline-layout';
	import type { QuestIndexRow, Questline } from '$lib/types';
	import { param, syncUrl, urlParams } from '$lib/url-state';

	let {
		line,
		rows,
		highlight
	}: { line: Questline; rows: Map<number, QuestIndexRow>; highlight?: number } = $props();

	// Show one faction's view by default when the line mixes both.
	const highlightSide = $derived(highlight ? rows.get(highlight)?.[4] : undefined);
	// Explicit choices are kept in the URL (?side=both|A|H&class=<bit>, class=0 = all classes);
	// without them the faction and class of the highlighted quest are preselected.
	const p = urlParams();
	const urlSide = p.get('side');
	let sideChoice = $state<'' | 'A' | 'H' | null>(
		urlSide === 'both' ? '' : urlSide === 'A' || urlSide === 'H' ? urlSide : null
	);
	const side = $derived(sideChoice ?? (highlightSide === 'A' || highlightSide === 'H' ? highlightSide : ''));
	const mixed = $derived(line.quests.some((q) => rows.get(q)?.[4] === 'A') && line.quests.some((q) => rows.get(q)?.[4] === 'H'));

	// Class-specific variants (e.g. the dungeon set quests) get a class filter.
	const classes = $derived(CLASS_BITS.filter(([bit]) => line.quests.some((q) => (rows.get(q)?.[6] ?? 0) & bit)));
	const highlightClass = $derived.by(() => {
		const mask = highlight ? (rows.get(highlight)?.[6] ?? 0) : 0;
		const match = CLASS_BITS.filter(([bit]) => mask & bit);
		return match.length === 1 ? match[0][0] : 0;
	});
	let classChoice = $state<number | null>(param.num(p, 'class'));
	$effect(() => {
		syncUrl({
			side: sideChoice === null ? null : sideChoice || 'both',
			class: classChoice === null ? null : String(classChoice)
		});
	});
	const cls = $derived(classChoice ?? highlightClass);

	const visible = $derived(
		line.quests.filter((q) => {
			const row = rows.get(q);
			if (side && row && row[4] !== 'B' && row[4] !== side) return false;
			if (cls && row && row[6] && !(row[6] & cls)) return false;
			return true;
		})
	);
	const layout = $derived.by(() => {
		const keep = new Set(visible);
		return layoutQuestline({
			nodes: visible,
			edges: line.edges.filter(([a, b]) => keep.has(a) && keep.has(b)),
			rank: (id) => (rows.get(id)?.[2] ?? 0) * 100000 + id
		});
	});

	const name = (id: number) => site.names?.quest?.[id] ?? rows.get(id)?.[1] ?? `Quest ${id}`;
	const doneCount = $derived(visible.filter((q) => progress.isDone(site.flavor, q)).length);

	function path(points: [number, number][]): string {
		return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x},${y}`).join(' ');
	}

	let scroller: HTMLDivElement | undefined = $state();
	$effect(() => {
		// Bring the highlighted quest (or else the start of the line) into view.
		const node =
			layout.nodes.find((n) => n.id === highlight) ??
			layout.nodes.find((n) => n.id === line.root) ??
			[...layout.nodes].sort((a, b) => a.y - b.y)[0];
		if (!scroller || !node) return;
		scroller.scrollTo({
			left: node.x + NODE_W / 2 - scroller.clientWidth / 2,
			top: node.id === highlight ? node.y + NODE_H / 2 - scroller.clientHeight / 2 : 0
		});
	});
</script>

<div class="toolbar">
	{#if mixed}
		<div class="seg" role="group" aria-label="Faction">
			<button class:active={side === ''} onclick={() => (sideChoice = '')}>Both</button>
			<button class:active={side === 'A'} onclick={() => (sideChoice = 'A')}>Alliance</button>
			<button class:active={side === 'H'} onclick={() => (sideChoice = 'H')}>Horde</button>
		</div>
	{/if}
	{#if classes.length > 1}
		<select
			aria-label="Class"
			value={cls}
			onchange={(e) => (classChoice = Number(e.currentTarget.value))}
		>
			<option value={0}>All classes</option>
			{#each classes as [bit, label] (bit)}
				<option value={bit}>{label}</option>
			{/each}
		</select>
	{/if}
	<span class="muted">{doneCount} / {visible.length} completed</span>
</div>

<div class="board" bind:this={scroller}>
	<div class="canvas" style="width:{layout.width}px;height:{layout.height}px">
		<svg class="edges" width={layout.width} height={layout.height} aria-hidden="true">
			<defs>
				<!-- userSpaceOnUse: straight vertical edges have a zero-width bounding box -->
				<filter id="ql-glow" filterUnits="userSpaceOnUse" x="0" y="0" width={layout.width} height={layout.height}>
					<feGaussianBlur stdDeviation="2.5" result="blur" />
					<feMerge>
						<feMergeNode in="blur" />
						<feMergeNode in="SourceGraphic" />
					</feMerge>
				</filter>
			</defs>
			{#each layout.edges as e (`${e.from}-${e.to}`)}
				<path class="edge-shadow" d={path(e.points)} />
				<path
					class="edge"
					class:breadcrumb={e.kind === 'breadcrumb'}
					class:pending={!progress.isDone(site.flavor, e.from)}
					d={path(e.points)}
					filter="url(#ql-glow)"
				/>
			{/each}
		</svg>
		{#each layout.nodes as n (n.id)}
			{@const row = rows.get(n.id)}
			{@const done = progress.isDone(site.flavor, n.id)}
			<div
				class="quest"
				class:current={n.id === highlight}
				class:done
				style="left:{n.x}px;top:{n.y}px;width:{NODE_W}px;height:{NODE_H}px"
			>
				<a href="#/quest/{n.id}" title="{name(n.id)}{row?.[2] ? ` (level ${row[2]})` : ''}">
					<span class="title">{name(n.id)}</span>
					<span class="meta">
						{#if row?.[2]}<span class="lvl">{row[2]}</span>{/if}
						{#if row?.[4] === 'A'}<span class="side a">Alliance</span>{:else if row?.[4] === 'H'}<span class="side h">Horde</span>{/if}
					</span>
				</a>
				<span class="icons">
					{#if row && row[7] & 2}
						<svg viewBox="0 0 20 20" class="icon" aria-label="Dungeon / Raid"
							><path
								d="M10 2C5.6 2 3 5 3 8.6c0 2.3 1.1 3.8 2.5 4.6V16h2v-2h1.5v2h2v-2h1.5v2h2v-2.8c1.4-.8 2.5-2.3 2.5-4.6C17 5 14.4 2 10 2Zm-3 9.3a1.8 1.8 0 1 1 0-3.6 1.8 1.8 0 0 1 0 3.6Zm6 0a1.8 1.8 0 1 1 0-3.6 1.8 1.8 0 0 1 0 3.6Z"
							/></svg
						>
					{/if}
					{#if row && row[7] & 4}
						<svg viewBox="0 0 20 20" class="icon" aria-label="Group"
							><circle cx="7" cy="6" r="3" /><circle cx="13.5" cy="7" r="2.5" /><path
								d="M1.5 17c0-3.3 2.5-5.5 5.5-5.5s5.5 2.2 5.5 5.5Zm12 0c0-1.9-.6-3.5-1.7-4.6.5-.2 1-.3 1.7-.3 2.6 0 4.5 1.9 4.5 4.9Z"
							/></svg
						>
					{/if}
					<button
						class="check"
						class:on={done}
						title={done ? 'Mark as not completed' : 'Mark as completed'}
						aria-pressed={done}
						onclick={() => progress.toggle(site.flavor, n.id)}
					>
						<svg viewBox="0 0 20 20"><path d="M3 10.5 8 15.5 17.5 4.5" /></svg>
					</button>
				</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.toolbar {
		display: flex;
		gap: 1rem;
		align-items: center;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
	}
	.seg button {
		background: var(--panel);
		border: none;
		padding: 0.3rem 0.7rem;
		cursor: pointer;
		font-size: 0.85rem;
	}
	.seg button + button {
		border-left: 1px solid var(--border);
	}
	.seg button.active {
		background: var(--accent);
		color: var(--bg);
	}

	.board {
		overflow: auto;
		max-height: 78vh;
		border-radius: 8px;
		border: 1px solid #000;
		box-shadow: inset 0 0 40px #000;
		background-color: #161514;
		background-image:
			radial-gradient(ellipse at 20% 30%, rgba(255, 255, 255, 0.035), transparent 45%),
			radial-gradient(ellipse at 80% 70%, rgba(255, 255, 255, 0.03), transparent 50%),
			repeating-linear-gradient(45deg, rgba(0, 0, 0, 0.18) 0 2px, transparent 2px 9px),
			repeating-linear-gradient(-45deg, rgba(255, 255, 255, 0.015) 0 2px, transparent 2px 11px);
	}
	.canvas {
		position: relative;
		margin: 0 auto;
	}
	.edges {
		position: absolute;
		inset: 0;
		overflow: visible;
	}
	.edge-shadow {
		fill: none;
		stroke: #000;
		stroke-width: 8;
		stroke-linejoin: round;
		opacity: 0.6;
	}
	.edge {
		fill: none;
		stroke: #1fbf1f;
		stroke-width: 4;
		stroke-linejoin: round;
	}
	.edge.pending {
		stroke: #1a8f1a;
	}
	.edge.breadcrumb {
		stroke-dasharray: 8 7;
		stroke: #c9a227;
	}

	.quest {
		position: absolute;
		display: flex;
		align-items: stretch;
		border-radius: 3px;
		border: 1px solid #000;
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 40%),
			repeating-linear-gradient(60deg, rgba(0, 0, 0, 0.12) 0 3px, transparent 3px 10px),
			linear-gradient(180deg, #3d3220, #251d12);
		box-shadow:
			0 3px 8px rgba(0, 0, 0, 0.8),
			inset 0 0 0 1px rgba(255, 210, 120, 0.12);
		transition: box-shadow 0.15s;
	}
	.quest:hover {
		box-shadow:
			0 3px 10px rgba(0, 0, 0, 0.9),
			inset 0 0 0 1px rgba(255, 210, 120, 0.45);
	}
	.quest.current {
		box-shadow:
			0 0 0 2px #ffd100,
			0 0 18px rgba(255, 209, 0, 0.55);
	}
	.quest a {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		justify-content: center;
		padding: 0.25rem 0.4rem 0.25rem 0.7rem;
		color: #f0c53e;
		text-decoration: none;
		text-shadow: 0 1px 1px #000;
		font-family: Georgia, 'Times New Roman', serif;
	}
	.quest.done a {
		color: #d8b75a;
	}
	.title {
		font-size: 0.95rem;
		line-height: 1.15;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.meta {
		font-family: system-ui, sans-serif;
		font-size: 0.7rem;
		color: #a8987a;
		display: flex;
		gap: 0.4rem;
	}
	.lvl::before {
		content: 'Level ';
	}
	.side.a {
		color: #7fa8ff;
	}
	.side.h {
		color: #ff7f72;
	}
	.icons {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		padding: 0 6px;
	}
	.icon {
		width: 18px;
		height: 18px;
		fill: #e8c34a;
		filter: drop-shadow(0 1px 1px #000);
	}
	.check {
		background: none;
		border: none;
		padding: 0;
		width: 22px;
		height: 22px;
		cursor: pointer;
	}
	.check svg {
		width: 22px;
		height: 22px;
		fill: none;
		stroke: rgba(255, 255, 255, 0.12);
		stroke-width: 3;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.check:hover svg {
		stroke: rgba(80, 220, 80, 0.5);
	}
	.check.on svg {
		stroke: #3ee03e;
		filter: drop-shadow(0 0 2px rgba(40, 200, 40, 0.8)) drop-shadow(0 1px 1px #000);
	}
</style>
