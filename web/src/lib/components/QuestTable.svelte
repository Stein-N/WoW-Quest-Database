<script lang="ts">
	import { site } from '$lib/context.svelte';
	import { CLASS_BITS, fold, SIDE_LABELS } from '$lib/format';
	import type { QuestIndexRow } from '$lib/types';

	let { rows, showZone = true, pageSize = 100 }: { rows: QuestIndexRow[]; showZone?: boolean; pageSize?: number } =
		$props();

	let text = $state('');
	let side = $state('');
	let cls = $state(0);
	let minLevel = $state<number | null>(null);
	let maxLevel = $state<number | null>(null);
	let kind = $state('');
	let zone = $state('');
	let sortKey = $state<'id' | 'name' | 'level' | 'req' | 'zone'>('level');
	let sortDir = $state(1);
	let pageIndex = $state(0);

	const name = (r: QuestIndexRow) => site.names?.quest?.[r[0]] ?? r[1];

	const zoneOptions = $derived.by(() => {
		const ids = [...new Set(rows.map((r) => r[5]).filter(Boolean))];
		return ids
			.map((id) => ({ id, name: site.zoneName(id) }))
			.sort((a, b) => Number(a.id < 0) - Number(b.id < 0) || a.name.localeCompare(b.name));
	});

	const filtered = $derived.by(() => {
		const needle = fold(text.trim());
		const kinds: Record<string, number> = { repeatable: 1, instance: 2, group: 4, pvp: 8 };
		const out = rows.filter((r) => {
			if (needle && !fold(name(r)).includes(needle) && String(r[0]) !== needle) return false;
			if (side && r[4] !== side && r[4] !== 'B') return false;
			if (cls && r[6] && !(r[6] & cls)) return false;
			if (minLevel !== null && (r[2] ?? 0) < minLevel) return false;
			if (maxLevel !== null && (r[2] ?? 0) > maxLevel) return false;
			if (kind && !(r[7] & kinds[kind])) return false;
			if (zone && String(r[5]) !== zone) return false;
			return true;
		});
		const key = (r: QuestIndexRow): string | number => {
			switch (sortKey) {
				case 'id':
					return r[0];
				case 'name':
					return name(r);
				case 'level':
					return r[2] ?? -1;
				case 'req':
					return r[3] ?? -1;
				case 'zone':
					return site.zoneName(r[5]);
			}
		};
		return out.sort((a, b) => {
			const ka = key(a);
			const kb = key(b);
			const c = typeof ka === 'string' ? ka.localeCompare(kb as string) : ka - (kb as number);
			return c * sortDir || a[0] - b[0];
		});
	});

	const pages = $derived(Math.max(1, Math.ceil(filtered.length / pageSize)));
	const shown = $derived(filtered.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize));

	$effect(() => {
		void filtered;
		pageIndex = 0;
	});

	function sortBy(key: typeof sortKey) {
		if (sortKey === key) sortDir = -sortDir;
		else {
			sortKey = key;
			sortDir = 1;
		}
	}
	const arrow = (key: typeof sortKey) => (sortKey === key ? (sortDir > 0 ? ' ▲' : ' ▼') : '');
</script>

<div class="filters">
	<input type="search" placeholder="Filter by name or ID" bind:value={text} />
	{#if showZone}
		<select bind:value={zone} aria-label="Zone">
			<option value="">All zones &amp; categories</option>
			{#each zoneOptions as z (z.id)}
				<option value={String(z.id)}>{z.name}</option>
			{/each}
		</select>
	{/if}
	<select bind:value={side} aria-label="Faction">
		<option value="">Both factions</option>
		<option value="A">Alliance</option>
		<option value="H">Horde</option>
	</select>
	<select bind:value={cls} aria-label="Class">
		<option value={0}>All classes</option>
		{#each CLASS_BITS as [bit, label] (bit)}
			<option value={bit}>{label}</option>
		{/each}
	</select>
	<select bind:value={kind} aria-label="Type">
		<option value="">All types</option>
		<option value="instance">Dungeon / Raid</option>
		<option value="group">Group</option>
		<option value="pvp">PvP</option>
		<option value="repeatable">Repeatable</option>
	</select>
	<input type="number" min="1" max="60" placeholder="Min lvl" bind:value={minLevel} style="width:6rem" />
	<input type="number" min="1" max="60" placeholder="Max lvl" bind:value={maxLevel} style="width:6rem" />
	<span class="muted">{filtered.length.toLocaleString('en')} quests</span>
</div>

<div class="table-wrap">
	<table class="list">
		<thead>
			<tr>
				<th onclick={() => sortBy('name')}>Name{arrow('name')}</th>
				<th class="num" onclick={() => sortBy('level')}>Level{arrow('level')}</th>
				<th class="num" onclick={() => sortBy('req')}>Req.{arrow('req')}</th>
				<th>Side</th>
				{#if showZone}<th onclick={() => sortBy('zone')}>Zone{arrow('zone')}</th>{/if}
				<th class="num" onclick={() => sortBy('id')}>ID{arrow('id')}</th>
			</tr>
		</thead>
		<tbody>
			{#each shown as r (r[0])}
				<tr>
					<td>
						<a class="link-quest" href="#/{site.flavor}/quest/{r[0]}">{name(r)}</a>
						{#if r[7] & 2}<span class="badge">Instance</span>{/if}
						{#if r[7] & 4}<span class="badge">Group</span>{/if}
						{#if r[7] & 1}<span class="badge">Repeatable</span>{/if}
						{#if r[6]}<span class="muted" style="font-size:0.8rem"
								>{CLASS_BITS.filter(([b]) => r[6] & b)
									.map(([, l]) => l)
									.join(', ')}</span
							>{/if}
					</td>
					<td class="num">{r[2] ?? ''}</td>
					<td class="num">{r[3] ?? ''}</td>
					<td class="side-{r[4]}">{r[4] === 'B' ? '' : SIDE_LABELS[r[4]]}</td>
					{#if showZone}<td>{r[5] ? site.zoneName(r[5]) : ''}</td>{/if}
					<td class="num muted">{r[0]}</td>
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
