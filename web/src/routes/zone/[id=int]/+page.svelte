<script lang="ts">
	import { page } from '$app/state';
	import { getQuestIndex, getQuestlines, getZoneGivers } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';
	import QuestTable from '$lib/components/QuestTable.svelte';
	import ZoneMap, { loadMapIndex, type MapLayer } from '$lib/components/ZoneMap.svelte';

	const flavor = FLAVOR;
	const id = $derived(Number(page.params.id));
	const zone = $derived(site.zones?.zones[id]);

	async function load(flavor: string, id: number) {
		const [rows, zoneData, lines, mapIndex] = await Promise.all([
			getQuestIndex(flavor),
			getZoneGivers(flavor, id),
			getQuestlines(flavor),
			loadMapIndex(flavor)
		]);
		const z = site.zones?.zones[id];
		const floors = (z?.instance && z.uiMapId && mapIndex.instances?.[z.uiMapId]) || [];
		// The zone's own world map comes first (after an instance's floors: its parent zone).
		const worldZone = z?.instance ? z.parent : id;
		const worldMap = worldZone ? site.zones?.zones[worldZone]?.uiMapId : undefined;
		const primary =
			worldZone && worldMap && mapIndex.maps.includes(worldMap) ? { uiMapId: worldMap, name: site.zoneName(worldZone) } : undefined;
		const inZone = rows.filter((r) => r[5] === id);
		const sides = new Map(rows.map((r) => [r[0], r[4]]));
		const layer = (label: string, color: string, side: string): MapLayer => ({
			label,
			color,
			glyph: '!',
			entries: (zoneData.givers ?? [])
				.filter((g) => {
					const s = new Set(g.quests.map((q) => sides.get(q)));
					return side === 'B' ? s.has('B') || (s.has('A') && s.has('H')) : s.size === 1 && s.has(side as 'A');
				})
				.map((g) => ({
					name: `${site.names?.[g.t]?.[g.id] ?? g.name} (${g.quests.length} quest${g.quests.length > 1 ? 's' : ''})`,
					href: `#/${g.t}/${g.id}`,
					data: { spawns: g.spawns }
				}))
		});
		const names = new Map(rows.map((r) => [r[0], r[1]]));
		const zoneLines = lines
			.filter((l) => l.zone === id && l.quests.length >= 2)
			.map((l) => ({ ...l, title: site.names?.quest?.[l.root] ?? names.get(l.root) ?? '' }))
			.sort((a, b) => (a.levels?.[0] ?? 0) - (b.levels?.[0] ?? 0));
		return {
			floors,
			primary,
			lines: zoneLines,
			rows: inZone,
			layers: [layer('Alliance quest givers', '#4f8cff', 'A'), layer('Horde quest givers', '#ff5c4f', 'H'), layer('Neutral quest givers', '#ffd100', 'B')]
		};
	}
</script>

<svelte:head><title>{site.zoneName(id)} – WoW Quest Database</title></svelte:head>

<h1>{site.zoneName(id)}</h1>
{#if zone?.instance}<p class="muted" style="margin-top:0">Instance{#if zone.parent}{' in '}<a href="#/zone/{zone.parent}">{site.zoneName(zone.parent)}</a>{/if}</p>{/if}

{#await load(flavor, id)}
	<p class="muted">Loading…</p>
{:then data}
	{#if data.floors.length || data.primary || data.layers.some((l) => l.entries.length)}
		<section class="panel">
			{#key `${flavor}:${id}`}
				<ZoneMap layers={data.layers} floors={data.floors} primary={data.primary} />
			{/key}
		</section>
	{/if}
	{#if data.lines.length}
		<h2>Questlines <span class="count">{data.lines.length}</span></h2>
		<ul class="zone-lines">
			{#each data.lines as l (l.id)}
				<li>
					<a href="#/questline/{l.id}">{l.title}</a>
					<span class="muted">{l.quests.length} quests{#if l.levels} · {l.levels[0]}–{l.levels[1]}{/if}</span>
				</li>
			{/each}
		</ul>
	{/if}
	<h2>Quests <span class="count">{data.rows.length}</span></h2>
	<QuestTable rows={data.rows} showZone={false} />
{/await}

<style>
	.zone-lines {
		columns: 20rem;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.zone-lines li {
		break-inside: avoid;
		padding: 0.1rem 0;
	}
	.zone-lines .muted {
		font-size: 0.85rem;
	}
</style>
