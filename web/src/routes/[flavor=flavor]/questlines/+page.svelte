<script lang="ts">
	import { page } from '$app/state';
	import { getQuestIndex, getQuestlines } from '$lib/data';
	import { site } from '$lib/context.svelte';
	import { fold } from '$lib/format';
	import { progress } from '$lib/progress.svelte';
	import type { QuestIndexRow, Questline } from '$lib/types';

	const flavor = $derived(page.params.flavor!);

	let text = $state('');
	let side = $state('');
	let minSize = $state(3);

	async function load(flavor: string) {
		const [lines, index] = await Promise.all([getQuestlines(flavor), getQuestIndex(flavor)]);
		return { lines, rows: new Map(index.map((r) => [r[0], r])) };
	}

	function grouped(lines: Questline[], rows: Map<number, QuestIndexRow>) {
		const needle = fold(text.trim());
		const title = (l: Questline) => site.names?.quest?.[l.root] ?? rows.get(l.root)?.[1] ?? '';
		const matches = lines.filter((l) => {
			if (l.quests.length < minSize) return false;
			if (side && l.side !== 'B' && l.side !== side) return false;
			if (needle && !l.quests.some((q) => fold(site.names?.quest?.[q] ?? rows.get(q)?.[1] ?? '').includes(needle))) return false;
			return true;
		});
		const byZone = new Map<number, Questline[]>();
		for (const l of matches) byZone.set(l.zone, [...(byZone.get(l.zone) ?? []), l]);
		return [...byZone.entries()]
			.map(([zone, ls]) => ({
				zone,
				name: zone ? site.zoneName(zone) : 'Other',
				lines: ls.sort((a, b) => (a.levels?.[0] ?? 0) - (b.levels?.[0] ?? 0) || title(a).localeCompare(title(b)))
			}))
			.sort((a, b) => Number(a.zone < 0) - Number(b.zone < 0) || a.name.localeCompare(b.name));
	}
</script>

<svelte:head><title>Questlines – WoW Quest Database</title></svelte:head>

<h1>Questlines</h1>

<div class="filters">
	<input type="search" placeholder="Find a questline by quest name" bind:value={text} />
	<select bind:value={side} aria-label="Faction">
		<option value="">Both factions</option>
		<option value="A">Alliance</option>
		<option value="H">Horde</option>
	</select>
	<select bind:value={minSize} aria-label="Minimum length">
		<option value={2}>2+ quests</option>
		<option value={3}>3+ quests</option>
		<option value={5}>5+ quests</option>
		<option value={10}>10+ quests</option>
	</select>
</div>

{#await load(flavor)}
	<p class="muted">Loading…</p>
{:then { lines, rows }}
	{@const groups = grouped(lines, rows)}
	{#if !groups.length}<p>No questlines match.</p>{/if}
	{#each groups as g (g.zone)}
		<h2>{g.name} <span class="count">{g.lines.length}</span></h2>
		<ul class="lines">
			{#each g.lines as l (l.id)}
				{@const done = l.quests.filter((q) => progress.isDone(flavor, q)).length}
				<li>
					<a href="#/{flavor}/questline/{l.id}">{site.names?.quest?.[l.root] ?? rows.get(l.root)?.[1]}</a>
					<span class="muted">
						{l.quests.length} quests{#if l.levels} · {l.levels[0]}{l.levels[1] !== l.levels[0] ? `–${l.levels[1]}` : ''}{/if}
					</span>
					{#if l.side !== 'B'}<span class="side-{l.side}" title={l.side === 'A' ? 'Alliance' : 'Horde'}>●</span>{/if}
					{#if done}<span class="progress">{done}/{l.quests.length} ✓</span>{/if}
				</li>
			{/each}
		</ul>
	{/each}
{/await}

<style>
	.lines {
		columns: 22rem;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.lines li {
		break-inside: avoid;
		padding: 0.15rem 0;
	}
	.lines .muted {
		font-size: 0.85rem;
	}
	.progress {
		color: #2ea02e;
		font-size: 0.8rem;
		margin-left: 0.3rem;
	}
</style>
