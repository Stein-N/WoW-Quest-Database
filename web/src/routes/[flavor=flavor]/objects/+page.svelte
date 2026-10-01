<script lang="ts">
	import { page } from '$app/state';
	import { getSearchIndex } from '$lib/data';
	import { site } from '$lib/context.svelte';
	import { fold } from '$lib/format';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import type { SearchIndex } from '$lib/types';

	type Row = SearchIndex['object'][number];
	const flavor = $derived(page.params.flavor!);

	const p = urlParams();
	let text = $state(param.str(p, 'q'));
	let zone = $state(param.str(p, 'zone'));
	$effect(() => {
		syncUrl({ q: text.trim(), zone });
	});

	const name = (r: Row) => site.names?.object?.[r[0]] ?? r[1];

	function filter(rows: Row[]): Row[] {
		const needle = fold(text.trim());
		return rows.filter((r) => {
			if (needle && !fold(name(r)).includes(needle) && !fold(r[1]).includes(needle) && String(r[0]) !== needle) return false;
			if (zone && String(r[2]) !== zone) return false;
			return true;
		});
	}

	const zonesOf = (rows: Row[]) =>
		[...new Set(rows.map((r) => r[2]).filter(Boolean))]
			.map((id) => ({ id, name: site.zoneName(id) }))
			.sort((a, b) => a.name.localeCompare(b.name));

	const columns: Column<Row>[] = [
		{ key: 'name', label: 'Name', value: (r) => name(r), href: (r) => `#/${flavor}/object/${r[0]}`, cls: () => 'link-object' },
		{ key: 'zone', label: 'Zone', value: (r) => (r[2] ? site.zoneName(r[2]) : '') },
		{ key: 'id', label: 'ID', num: true, value: (r) => r[0], cls: () => 'muted' }
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
		rows={filter(index.object)}
		{columns}
		rowKey={(r) => r[0]}
		filterKey={JSON.stringify([text, zone])}
		defaultSort="name"
		noun="objects"
	/>
{/await}
