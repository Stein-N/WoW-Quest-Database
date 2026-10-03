<script lang="ts">
	import { getSearchIndex } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';
	import { fold } from '$lib/format';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import type { SearchIndex } from '$lib/types';

	type Entry = SearchIndex['object'][number];
	/** objects sharing a name are one row; `ids` and `zones` cover all of them */
	interface Row {
		id: number;
		name: string;
		ids: number[];
		zones: number[];
	}
	const flavor = FLAVOR;

	const p = urlParams();
	let text = $state(param.str(p, 'q'));
	let zone = $state(param.str(p, 'zone'));
	$effect(() => {
		syncUrl({ q: text.trim(), zone });
	});

	const name = (r: Row) => site.names?.object?.[r.id] ?? r.name;

	// grouped by the English name, which is the same in every language
	const grouped = new WeakMap<Entry[], Row[]>();
	function group(entries: Entry[]): Row[] {
		let rows = grouped.get(entries);
		if (!rows) {
			const byName = new Map<string, Row>();
			for (const [id, n, z] of entries) {
				const row = byName.get(n);
				if (!row) byName.set(n, { id, name: n, ids: [id], zones: z ? [z] : [] });
				else {
					row.ids.push(id);
					if (z && !row.zones.includes(z)) row.zones.push(z);
				}
			}
			rows = [...byName.values()];
			for (const r of rows) {
				r.ids.sort((a, b) => a - b);
				r.id = r.ids[0];
			}
			grouped.set(entries, rows);
		}
		return rows;
	}

	function filter(rows: Row[]): Row[] {
		const needle = fold(text.trim());
		return rows.filter((r) => {
			if (needle && !fold(name(r)).includes(needle) && !fold(r.name).includes(needle) && !r.ids.some((i) => String(i) === needle))
				return false;
			if (zone && !r.zones.some((z) => String(z) === zone)) return false;
			return true;
		});
	}

	const zoneText = (r: Row) =>
		r.zones.length === 1 ? site.zoneName(r.zones[0]) : r.zones.length ? `${r.zones.length} zones` : '';

	const zonesOf = (rows: Entry[]) =>
		[...new Set(rows.map((r) => r[2]).filter(Boolean))]
			.map((id) => ({ id, name: site.zoneName(id) }))
			.sort((a, b) => a.name.localeCompare(b.name));

	const columns: Column<Row>[] = [
		{ key: 'name', label: 'Name', value: (r) => name(r), href: (r) => `#/object/${r.id}`, cls: () => 'link-object' },
		{ key: 'zone', label: 'Zone', value: zoneText },
		{ key: 'count', label: 'Objects', num: true, value: (r) => r.ids.length, cls: () => 'muted' },
		{ key: 'id', label: 'ID', num: true, value: (r) => r.id, text: (r) => (r.ids.length > 1 ? `${r.id} +${r.ids.length - 1}` : String(r.id)), cls: () => 'muted' }
	];
</script>

<svelte:head><title>Objects – WoW Quest Database</title></svelte:head>

<h1>Objects</h1>
{#await getSearchIndex(flavor)}
	<p class="muted">Loading…</p>
{:then index}
	<div class="filters">
		<input type="search" placeholder="Filter by name or ID" bind:value={text} />
		<select bind:value={zone} aria-label="Zone">
			<option value="">All zones</option>
			{#each zonesOf(index.object) as z (z.id)}<option value={String(z.id)}>{z.name}</option>{/each}
		</select>
	</div>
	<DataTable
		rows={filter(group(index.object))}
		{columns}
		rowKey={(r) => r.id}
		filterKey={JSON.stringify([text, zone])}
		defaultSort="name"
		noun="objects"
	/>
{/await}
