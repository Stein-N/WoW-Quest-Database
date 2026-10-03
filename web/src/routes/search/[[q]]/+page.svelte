<script lang="ts">
	import { page } from '$app/state';
	import { getQuestIndex, getSearchIndex } from '$lib/data';
	import { FLAVOR, site } from '$lib/context.svelte';
	import { fold, levelRange } from '$lib/format';
	import type { Kind } from '$lib/types';

	const flavor = FLAVOR;
	const q = $derived(decodeURIComponent(page.params.q ?? '').trim());

	interface Hit {
		id: number;
		name: string;
		extra?: string;
		cls?: string;
		rank: number;
	}

	const LIMIT = 50;
	const SECTIONS: { kind: Kind; title: string }[] = [
		{ kind: 'quest', title: 'Quests' },
		{ kind: 'npc', title: 'NPCs' },
		{ kind: 'item', title: 'Items' },
		{ kind: 'object', title: 'Objects' }
	];

	let expanded = $state<Record<string, boolean>>({});

	async function run(flavor: string, query: string) {
		const [quests, index] = await Promise.all([getQuestIndex(flavor), getSearchIndex(flavor)]);
		const needle = fold(query);
		const numeric = /^\d+$/.test(query) ? Number(query) : null;
		const names = site.names;

		function rank(name: string, id: number): number {
			if (numeric !== null) return id === numeric ? 0 : -1;
			const f = fold(name);
			if (f === needle) return 0;
			if (f.startsWith(needle)) return 1;
			if (f.includes(needle)) return 2;
			return -1;
		}
		function collect<T extends [number, string, ...unknown[]]>(
			kind: Kind,
			rows: T[],
			extra: (r: T) => Partial<Hit>
		): Hit[] {
			const hits: Hit[] = [];
			for (const r of rows) {
				const local = names?.[kind]?.[r[0]];
				const rk = Math.min(
					...[rank(r[1], r[0]), local ? rank(local, r[0]) : -1].map((x) => (x < 0 ? 99 : x))
				);
				if (rk < 99) hits.push({ id: r[0], name: local ?? r[1], rank: rk, ...extra(r) });
			}
			return hits.sort((a, b) => a.rank - b.rank || a.name.length - b.name.length || a.name.localeCompare(b.name));
		}
		return {
			quest: collect('quest', quests, (r) => ({
				extra: `${r[2] ? `Level ${r[2]}` : ''}${r[5] ? ` · ${site.zoneName(r[5])}` : ''} · #${r[0]}`,
				cls: 'link-quest'
			})),
			npc: collect('npc', index.npc, (r) => ({
				extra: `${r[2] ? `<${r[2]}> · ` : ''}Level ${levelRange(r[3], r[4])}`
			})),
			item: collect('item', index.item, (r) => ({ cls: r[2] !== null ? `q${r[2]}` : undefined })),
			object: collect('object', index.object, () => ({}))
		} as Record<Kind, Hit[]>;
	}

	const results = $derived(q.length >= 2 || /^\d+$/.test(q) ? run(flavor, q) : null);
</script>

<svelte:head><title>Search – Forever Database</title></svelte:head>

<h1>Search{q ? `: ${q}` : ''}</h1>

{#if !results}
	<p class="muted">Enter at least two characters (or an ID) in the search box above.</p>
{:else}
	{#await results}
		<p class="muted">Searching…</p>
	{:then res}
		{#if SECTIONS.every((s) => res[s.kind].length === 0)}
			<p>No results.</p>
		{/if}
		<div class="cols">
			{#each SECTIONS as s (s.kind)}
				{@const hits = res[s.kind]}
				{#if hits.length}
					<section class="panel">
						<h3>{s.title} <span class="count">{hits.length}</span></h3>
						<ul class="reflist">
							{#each expanded[s.kind] ? hits : hits.slice(0, LIMIT) as h (h.id)}
								<li>
									<a class={h.cls} href="#/{s.kind}/{h.id}">{h.name}</a>
									{#if h.extra}<span class="muted" style="font-size:0.85rem"> {h.extra}</span>{/if}
								</li>
							{/each}
						</ul>
						{#if hits.length > LIMIT}
							<button class="linkish" onclick={() => (expanded = { ...expanded, [s.kind]: !expanded[s.kind] })}>
								{expanded[s.kind] ? 'Show less' : `Show all ${hits.length}`}
							</button>
						{/if}
					</section>
				{/if}
			{/each}
		</div>
	{/await}
{/if}
