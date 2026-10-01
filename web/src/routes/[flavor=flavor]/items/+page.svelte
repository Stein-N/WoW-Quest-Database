<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { getSearchIndex } from '$lib/data';
	import { site } from '$lib/context.svelte';
	import { fold, QUALITY_NAMES } from '$lib/format';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import type { SearchIndex } from '$lib/types';

	type Row = SearchIndex['item'][number];
	const flavor = $derived(page.params.flavor!);

	const p = urlParams();
	let text = $state(param.str(p, 'q'));
	let quality = $state(param.str(p, 'quality'));
	let cls = $state(param.str(p, 'class'));
	let sub = $state(param.str(p, 'sub'));
	let slot = $state(param.str(p, 'slot'));
	let minLevel = $state<number | null>(param.num(p, 'min'));
	let maxLevel = $state<number | null>(param.num(p, 'max'));
	$effect(() => {
		syncUrl({ q: text.trim(), quality, class: cls, sub, slot, min: minLevel, max: maxLevel });
	});
	// a sub type only makes sense within its class
	let lastClass = untrack(() => cls);
	$effect(() => {
		if (cls !== lastClass) {
			lastClass = cls;
			sub = '';
		}
	});

	const name = (r: Row) => site.names?.item?.[r[0]] ?? r[1];
	const distinct = (values: string[]) => [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));

	function filter(rows: Row[]): Row[] {
		const needle = fold(text.trim());
		return rows.filter((r) => {
			if (needle && !fold(name(r)).includes(needle) && !fold(r[1]).includes(needle) && String(r[0]) !== needle) return false;
			if (quality !== '' && String(r[2]) !== quality) return false;
			if (cls && r[5] !== cls) return false;
			if (sub && r[6] !== sub) return false;
			if (slot && r[7] !== slot) return false;
			if (minLevel !== null && (r[3] ?? 0) < minLevel) return false;
			if (maxLevel !== null && (r[3] ?? 0) > maxLevel) return false;
			return true;
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'name', label: 'Name', value: (r) => name(r), href: (r) => `#/${flavor}/item/${r[0]}`, cls: (r) => (r[2] !== null ? `q${r[2]}` : undefined) },
		{ key: 'ilvl', label: 'Item level', num: true, value: (r) => r[3] },
		{ key: 'req', label: 'Req.', num: true, value: (r) => r[4] },
		{ key: 'type', label: 'Type', value: (r) => (r[6] && r[6] !== r[5] ? `${r[5]} / ${r[6]}` : r[5]) },
		{ key: 'slot', label: 'Slot', value: (r) => r[7] },
		{ key: 'id', label: 'ID', num: true, value: (r) => r[0], cls: () => 'muted' }
	];
</script>

<svelte:head><title>Items – WoW Quest Database</title></svelte:head>

<h1>Items</h1>
{#await getSearchIndex(flavor)}
	<p class="muted">Loading…</p>
{:then index}
	<div class="filters">
		<input type="search" placeholder="Filter by name or ID" bind:value={text} />
		<select bind:value={quality} aria-label="Quality">
			<option value="">Any quality</option>
			{#each QUALITY_NAMES.slice(0, 6) as q, i (q)}<option value={String(i)}>{q}</option>{/each}
		</select>
		<select bind:value={cls} aria-label="Type">
			<option value="">All types</option>
			{#each distinct(index.item.map((r) => r[5])) as c (c)}<option value={c}>{c}</option>{/each}
		</select>
		{#if cls}
			{@const subs = distinct(index.item.filter((r) => r[5] === cls).map((r) => r[6]))}
			{#if subs.length > 1}
				<select bind:value={sub} aria-label="Sub type">
					<option value="">All {cls.toLowerCase()}</option>
					{#each subs as s (s)}<option value={s}>{s}</option>{/each}
				</select>
			{/if}
		{/if}
		<select bind:value={slot} aria-label="Slot">
			<option value="">Any slot</option>
			{#each distinct(index.item.map((r) => r[7])) as s (s)}<option value={s}>{s}</option>{/each}
		</select>
		<input type="number" min="1" placeholder="Min ilvl" bind:value={minLevel} style="width:6.5rem" />
		<input type="number" min="1" placeholder="Max ilvl" bind:value={maxLevel} style="width:6.5rem" />
	</div>
	<DataTable
		rows={filter(index.item)}
		{columns}
		rowKey={(r) => r[0]}
		filterKey={JSON.stringify([text, quality, cls, sub, slot, minLevel, maxLevel])}
		defaultSort="name"
		noun="items"
	/>
{/await}
