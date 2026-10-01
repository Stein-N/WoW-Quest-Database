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
				</li>
			{/each}
		</ul>
		{#if refs.length > limit}
			<button class="linkish" onclick={() => (expanded = !expanded)}>
				{expanded ? 'Show less' : `Show all ${refs.length}`}
			</button>
		{/if}
	</section>
{/if}
