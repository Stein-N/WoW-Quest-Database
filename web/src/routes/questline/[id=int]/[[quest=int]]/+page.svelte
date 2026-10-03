<script lang="ts">
	import { page } from '$app/state';
	import { getQuestIndex, getQuestlines } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';
	import { SIDE_LABELS } from '$lib/format';
	import QuestlineGraph from '$lib/components/QuestlineGraph.svelte';
	import type { QuestIndexRow, Questline } from '$lib/types';

	const flavor = FLAVOR;
	const id = $derived(Number(page.params.id));
	const highlight = $derived(page.params.quest ? Number(page.params.quest) : undefined);

	let data = $state<{ line: Questline | null; rows: Map<number, QuestIndexRow> } | undefined>();

	$effect(() => {
		const [f, i] = [flavor, id];
		data = undefined;
		let current = true;
		Promise.all([getQuestlines(f), getQuestIndex(f)]).then(([lines, index]) => {
			if (!current) return;
			data = { line: lines.find((l) => l.id === i) ?? null, rows: new Map(index.map((r) => [r[0], r])) };
		});
		return () => (current = false);
	});

	const title = $derived(
		data?.line ? (site.names?.quest?.[data.line.root] ?? data.rows.get(data.line.root)?.[1] ?? `Questline ${id}`) : 'Questline'
	);
</script>

<svelte:head><title>{title} – Questline – Forever Database</title></svelte:head>

{#if data === undefined}
	<p class="muted">Loading…</p>
{:else if !data.line}
	<h1>Questline not found</h1>
	<p class="muted">
		Questline IDs can change when the data is rebuilt. Try the <a href="#/questlines">questline list</a>.
	</p>
{:else}
	{@const line = data.line}
	<h1>{title}</h1>
	<p class="subtitle">
		<span class="badge">Questline</span>
		<span class="badge">{line.quests.length} quests</span>
		{#if line.levels}<span class="badge"
				>Level {line.levels[0]}{line.levels[1] !== line.levels[0] ? `–${line.levels[1]}` : ''}</span
			>{/if}
		{#if line.side !== 'B'}<span class="badge side-{line.side}">{SIDE_LABELS[line.side]}</span>{/if}
		{#if line.zone}<a href="#/zone/{line.zone}">{site.zoneName(line.zone)}</a>{/if}
	</p>
	{#key `${flavor}:${line.id}`}
		<QuestlineGraph {line} rows={data.rows} {highlight} />
	{/key}
	<p class="muted legend">
		Lines show prerequisites from top to bottom; dashed gold lines are breadcrumbs. Tick the check
		mark to track your progress — it is stored in this browser only.
	</p>
{/if}

<style>
	.subtitle {
		margin: 0 0 1rem;
	}
	.legend {
		font-size: 0.85rem;
	}
</style>
