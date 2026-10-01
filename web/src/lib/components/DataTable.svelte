<script lang="ts" module>
	export interface Column<R> {
		key: string;
		label: string;
		/** value used for sorting (and shown when no `text` is given) */
		value: (row: R) => string | number | null | undefined;
		text?: (row: R) => string;
		href?: (row: R) => string;
		cls?: (row: R) => string | undefined;
		num?: boolean;
	}
</script>

<script lang="ts" generics="R">
	import { untrack } from 'svelte';
	import { param, syncUrl, urlParams } from '$lib/url-state';

	let {
		rows,
		columns,
		rowKey,
		filterKey,
		defaultSort,
		pageSize = 100,
		noun = 'entries'
	}: {
		rows: R[];
		columns: Column<R>[];
		rowKey: (row: R) => number | string;
		/** changes whenever the parent's filters change; resets to page 1 */
		filterKey: string;
		defaultSort: string;
		pageSize?: number;
		noun?: string;
	} = $props();

	// sort and page live in the URL next to the parent's filters
	const p = urlParams();
	let sortKey = $state(untrack(() => (columns.some((c) => c.key === p.get('sort')) ? p.get('sort')! : defaultSort)));
	let sortDir = $state(p.get('dir') === 'desc' ? -1 : 1);
	let pageIndex = $state(Math.max(0, (param.num(p, 'page', 1) ?? 1) - 1));

	const sorted = $derived.by(() => {
		const col = columns.find((c) => c.key === sortKey) ?? columns[0];
		return [...rows].sort((a, b) => {
			const va = col.value(a);
			const vb = col.value(b);
			// empty values always last
			if (va === null || va === undefined || va === '') return vb === null || vb === undefined || vb === '' ? 0 : 1;
			if (vb === null || vb === undefined || vb === '') return -1;
			const c = typeof va === 'string' ? va.localeCompare(String(vb)) : va - (vb as number);
			return c * sortDir || String(rowKey(a)).localeCompare(String(rowKey(b)), undefined, { numeric: true });
		});
	});
	const pages = $derived(Math.max(1, Math.ceil(sorted.length / pageSize)));
	const shown = $derived(sorted.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize));

	let lastFilterKey = untrack(() => filterKey);
	$effect(() => {
		if (filterKey !== lastFilterKey) {
			lastFilterKey = filterKey;
			pageIndex = 0;
		}
	});
	$effect(() => {
		if (pageIndex > 0 && pageIndex >= pages) pageIndex = pages - 1;
	});
	$effect(() => {
		syncUrl(
			{ sort: sortKey, dir: sortDir < 0 ? 'desc' : '', page: pageIndex + 1 },
			{ sort: untrack(() => defaultSort), page: 1 }
		);
	});

	function sortBy(key: string) {
		if (sortKey === key) sortDir = -sortDir;
		else {
			sortKey = key;
			sortDir = 1;
		}
	}
	const arrow = (key: string) => (sortKey === key ? (sortDir > 0 ? ' ▲' : ' ▼') : '');
</script>

<p class="muted count-line">{sorted.length.toLocaleString('en')} {noun}</p>

<div class="table-wrap">
	<table class="list">
		<thead>
			<tr>
				{#each columns as c (c.key)}
					<th class:num={c.num} onclick={() => sortBy(c.key)}>{c.label}{arrow(c.key)}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each shown as row (rowKey(row))}
				<tr>
					{#each columns as c (c.key)}
						{@const text = c.text ? c.text(row) : String(c.value(row) ?? '')}
						<td class:num={c.num} class={c.cls?.(row)}>
							{#if c.href}<a class={c.cls?.(row)} href={c.href(row)}>{text}</a>{:else}{text}{/if}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

{#if pages > 1}
	<div class="pager">
		<button disabled={pageIndex === 0} onclick={() => pageIndex--}>‹ Prev</button>
		<span class="muted">Page {pageIndex + 1} of {pages}</span>
		<button disabled={pageIndex >= pages - 1} onclick={() => pageIndex++}>Next ›</button>
	</div>
{/if}

<style>
	.count-line {
		margin: 0 0 0.4rem;
		font-size: 0.9rem;
	}
</style>
