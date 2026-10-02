<script lang="ts">
	import EntityLink from './EntityLink.svelte';
	import { chance } from '$lib/format';
	import type { Ref } from '$lib/types';

	let {
		title,
		refs,
		showChance = false,
		limit = 50
	}: { title: string; refs: Ref[] | undefined; showChance?: boolean; limit?: number } = $props();

	let expanded = $state(false);
	const shown = $derived(refs ? (expanded ? refs : refs.slice(0, limit)) : []);
	const restockTime = (sec: number) =>
		sec >= 3600 && sec % 3600 === 0 ? `${sec / 3600} h` : sec >= 60 ? `${Math.round(sec / 60)} min` : `${sec} s`;
	const fromVmangos = $derived(refs?.some((r) => r.vmangos) ?? false);
</script>

{#if refs?.length}
	<section class="panel">
		<h3>{title} <span class="count">{refs.length}</span></h3>
		<ul class="reflist">
			{#each shown as ref (`${ref.t}:${ref.id}`)}
				<li>
					<EntityLink {ref} showLevel={ref.t === 'quest'} />
					{#if ref.count && ref.count > 1}<span class="muted">×{ref.count}</span>{/if}
					{#if ref.min && ref.max}<span class="muted">({ref.min}–{ref.max})</span>{/if}
					{#if showChance && ref.chance}<span class="chance">{chance(ref.chance)}</span>{/if}
					{#if ref.limit}
						<span class="muted" title="Limited stock">
							limited: {ref.limit}{ref.restock ? `, restocks every ${restockTime(ref.restock)}` : ''}
						</span>
					{/if}
					{#if ref.conditional}<span class="muted" title="Only offered under a condition, e.g. reputation">conditional</span>{/if}
					{#if ref.vmangos}
						<span class="vm" title="Only in the VMangos database - may be outdated">VMangos</span>
					{/if}
				</li>
			{/each}
		</ul>
		{#if fromVmangos}
			<p class="vm-note muted">
				Entries marked <span class="vm">VMangos</span> come only from the VMangos server
				database and may be outdated or differ from the live game.
			</p>
		{/if}
		{#if refs.length > limit}
			<button class="linkish" onclick={() => (expanded = !expanded)}>
				{expanded ? 'Show less' : `Show all ${refs.length}`}
			</button>
		{/if}
	</section>
{/if}

<style>
	.vm {
		font-size: 0.72rem;
		padding: 0 0.3rem;
		border: 1px solid var(--border);
		border-radius: 4px;
		color: var(--muted);
		white-space: nowrap;
	}
	.vm-note {
		font-size: 0.8rem;
		margin: 0.5rem 0 0;
	}
</style>
