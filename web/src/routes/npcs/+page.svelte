<script lang="ts">
	import { getSearchIndex } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';
	import { fold, levelRange } from '$lib/format';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import type { SearchIndex } from '$lib/types';

	type Row = SearchIndex['npc'][number];
	const flavor = FLAVOR;

	const SERVICES: [number, string][] = [
		[2, 'Quest giver'],
		[4, 'Vendor'],
		[16384, 'Repair'],
		[16, 'Trainer'],
		[8, 'Flight master'],
		[128, 'Innkeeper'],
		[256, 'Banker'],
		[4096, 'Auctioneer'],
		[8192, 'Stable master'],
		[2048, 'Battlemaster']
	];
	const REACT: Record<string, string> = { A: 'Alliance', H: 'Horde', AH: 'Both' };

	const p = urlParams();
	let text = $state(param.str(p, 'q'));
	let zone = $state(param.str(p, 'zone'));
	let react = $state(param.str(p, 'react'));
	let rank = $state(param.str(p, 'rank'));
	let service = $state(param.num(p, 'service', 0)!);
	let minLevel = $state<number | null>(param.num(p, 'min'));
	let maxLevel = $state<number | null>(param.num(p, 'max'));
	$effect(() => {
		syncUrl({ q: text.trim(), zone, react, rank, service, min: minLevel, max: maxLevel }, { service: 0 });
	});

	const name = (r: Row) => site.names?.npc?.[r[0]] ?? r[1];

	function filter(rows: Row[]): Row[] {
		const needle = fold(text.trim());
		return rows.filter((r) => {
			if (needle && !fold(name(r)).includes(needle) && !fold(r[1]).includes(needle) && !fold(r[2]).includes(needle) && String(r[0]) !== needle)
				return false;
			if (zone && String(r[6]) !== zone) return false;
			if (react === 'friendly-a' && !r[5].includes('A')) return false;
			if (react === 'friendly-h' && !r[5].includes('H')) return false;
			if (react === 'hostile' && r[5]) return false;
			if (rank && r[7] !== rank) return false;
			if (service && !(r[8] & service)) return false;
			if (minLevel !== null && (r[4] ?? r[3] ?? 0) < minLevel) return false;
			if (maxLevel !== null && (r[3] ?? 0) > maxLevel) return false;
			return true;
		});
	}

	const zonesOf = (rows: Row[]) =>
		[...new Set(rows.map((r) => r[6]).filter(Boolean))]
			.map((id) => ({ id, name: site.zoneName(id) }))
			.sort((a, b) => a.name.localeCompare(b.name));

	const columns: Column<Row>[] = [
		{ key: 'name', label: 'Name', value: (r) => name(r), href: (r) => `#/npc/${r[0]}`, cls: () => 'link-npc' },
		{ key: 'title', label: 'Title', value: (r) => r[2] },
		{ key: 'level', label: 'Level', num: true, value: (r) => r[4] ?? r[3], text: (r) => levelRange(r[3], r[4]) },
		{ key: 'rank', label: 'Rank', value: (r) => (r[7] === 'Normal' ? '' : r[7]) },
		{ key: 'react', label: 'Reaction', value: (r) => REACT[r[5]] ?? '', cls: (r) => (r[5].length === 1 ? `side-${r[5]}` : undefined) },
		{ key: 'zone', label: 'Zone', value: (r) => (r[6] ? site.zoneName(r[6]) : '') },
		{ key: 'id', label: 'ID', num: true, value: (r) => r[0], cls: () => 'muted' }
	];
</script>

<svelte:head><title>NPCs – Forever Database</title></svelte:head>

<h1>NPCs</h1>
{#await getSearchIndex(flavor)}
	<p class="muted">Loading…</p>
{:then index}
	<div class="filters">
		<input type="search" placeholder="Filter by name, title or ID" bind:value={text} />
		<select bind:value={zone} aria-label="Zone">
			<option value="">All zones</option>
			{#each zonesOf(index.npc) as z (z.id)}<option value={String(z.id)}>{z.name}</option>{/each}
		</select>
		<select bind:value={react} aria-label="Reaction">
			<option value="">Any reaction</option>
			<option value="friendly-a">Friendly to Alliance</option>
			<option value="friendly-h">Friendly to Horde</option>
			<option value="hostile">Hostile to both</option>
		</select>
		<select bind:value={rank} aria-label="Rank">
			<option value="">Any rank</option>
			{#each ['Normal', 'Elite', 'Rare', 'Rare Elite', 'Boss'] as r (r)}<option value={r}>{r}</option>{/each}
		</select>
		<select bind:value={service} aria-label="Service">
			<option value={0}>Any service</option>
			{#each SERVICES as [bit, label] (bit)}<option value={bit}>{label}</option>{/each}
		</select>
		<input type="number" min="1" max="63" placeholder="Min lvl" bind:value={minLevel} style="width:6rem" />
		<input type="number" min="1" max="63" placeholder="Max lvl" bind:value={maxLevel} style="width:6rem" />
	</div>
	<DataTable
		rows={filter(index.npc)}
		{columns}
		rowKey={(r) => r[0]}
		filterKey={JSON.stringify([text, zone, react, rank, service, minLevel, maxLevel])}
		defaultSort="name"
		noun="NPCs"
	/>
{/await}
