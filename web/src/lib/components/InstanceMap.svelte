<script lang="ts">
	import { site } from '$lib/context.svelte';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import { loadMapIndex, type MapIndex } from './ZoneMap.svelte';

	/** Map of a dungeon or raid with one tab per floor. QuestieDB has no coordinates inside
	 *  instances, so the floors are plain images; spawns stay on the outdoor map. */
	let { uiMapId }: { uiMapId: number } = $props();

	let mapIndex = $state<MapIndex>({ maps: [] });
	$effect(() => {
		const flavor = site.flavor;
		loadMapIndex(flavor).then((index) => {
			if (site.flavor === flavor) mapIndex = index;
		});
	});
	const floors = $derived(mapIndex.instances?.[uiMapId] ?? []);

	// The chosen floor is kept in the URL (?floor=<uiMapId>), like the map tab of ZoneMap.
	let selected = $state<number | null>(param.num(urlParams(), 'floor'));
	$effect(() => {
		syncUrl({ floor: selected });
	});
	const current = $derived(
		floors.find((f) => f.uiMapId === selected) ?? floors.find((f) => f.uiMapId === uiMapId) ?? floors[0]
	);
	const file = $derived(current ? `maps/${site.flavor}/${current.uiMapId}.webp` : '');
</script>

{#if current}
	<section class="panel">
		{#if floors.length > 1}
			<div class="tabs" role="tablist">
				{#each floors as f (f.uiMapId)}
					<button
						role="tab"
						aria-selected={f === current}
						class:active={f === current}
						onclick={() => (selected = f.uiMapId)}
					>
						{f.name}
					</button>
				{/each}
			</div>
		{:else}
			<h3 class="mapname">{current.name}</h3>
		{/if}
		<a href={file} target="_blank" rel="noopener" title="Open full size">
			<img src={file} alt="Map of {current.name}" width="1002" height="668" />
		</a>
	</section>
{/if}

<style>
	img {
		display: block;
		width: 100%;
		height: auto;
		background: var(--map-bg);
		border: 1px solid var(--border);
		border-radius: 6px;
	}
	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-bottom: 0.4rem;
	}
	.tabs button {
		background: var(--panel);
		border: 1px solid var(--border);
		color: var(--text);
		padding: 0.25rem 0.6rem;
		border-radius: 4px;
		cursor: pointer;
		font: inherit;
		font-size: 0.85rem;
	}
	.tabs button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.mapname {
		margin: 0 0 0.4rem;
		font-size: 1rem;
	}
</style>
