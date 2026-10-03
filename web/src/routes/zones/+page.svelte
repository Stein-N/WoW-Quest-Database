<script lang="ts">
	import { getQuestIndex } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';

	const flavor = FLAVOR;

	function groups(rows: [number, ...unknown[]][]) {
		const counts = new Map<number, number>();
		for (const r of rows) {
			const z = r[5] as number;
			if (z) counts.set(z, (counts.get(z) ?? 0) + 1);
		}
		const all = [...counts.entries()].map(([id, n]) => ({ id, n, name: site.zoneName(id) }));
		const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);
		const zones = site.zones?.zones ?? {};
		const kind = (id: number) => zones[id]?.instanceType;
		const group = (id: number) => site.zones?.sortGroups?.[id] ?? 'other';
		const sorts = all.filter((z) => z.id < 0);
		return [
			{ title: 'Zones', items: all.filter((z) => z.id > 0 && !kind(z.id)).sort(byName) },
			{ title: 'Dungeons', items: all.filter((z) => z.id > 0 && kind(z.id) === 'dungeon').sort(byName) },
			{ title: 'Raids', items: all.filter((z) => z.id > 0 && kind(z.id) === 'raid').sort(byName) },
			{ title: 'Battlegrounds', items: all.filter((z) => z.id > 0 && kind(z.id) === 'battleground').sort(byName) },
			{ title: 'Classes', items: sorts.filter((z) => group(z.id) === 'class').sort(byName) },
			{ title: 'Professions', items: sorts.filter((z) => group(z.id) === 'profession').sort(byName) },
			{ title: 'Events', items: sorts.filter((z) => group(z.id) === 'event').sort(byName) },
			{ title: 'Other categories', items: sorts.filter((z) => group(z.id) === 'other').sort(byName) }
		].filter((g) => g.items.length);
	}
</script>

<svelte:head><title>Zones – Forever Database</title></svelte:head>

<h1>Zones</h1>
{#await getQuestIndex(flavor) then rows}
	{#each groups(rows) as g (g.title)}
		<h2>{g.title}</h2>
		<ul class="zone-list">
			{#each g.items as z (z.id)}
				<li><a href="#/zone/{z.id}">{z.name}</a> <span class="count">{z.n}</span></li>
			{/each}
		</ul>
	{/each}
{/await}

<style>
	.zone-list {
		columns: 16rem;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.zone-list li {
		padding: 0.1rem 0;
		break-inside: avoid;
	}
</style>
