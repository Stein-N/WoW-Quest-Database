<script lang="ts">
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { useEntity } from '$lib/entity.svelte';
	import RefList from '$lib/components/RefList.svelte';
	import ZoneMap from '$lib/components/ZoneMap.svelte';
	import type { GameObject } from '$lib/types';

	const flavor = $derived(page.params.flavor!);
	const id = $derived(Number(page.params.id));
	const entity = useEntity<GameObject>('object', () => ({ flavor, id }));
	const obj = $derived(entity.value);
	const name = $derived(entity.tr?.name ?? obj?.name);
</script>

<svelte:head><title>{name ?? 'Object'} – WoW Quest Database</title></svelte:head>

{#if obj === undefined}
	<p class="muted">Loading…</p>
{:else if obj === null}
	<h1>Object {id} not found</h1>
{:else}
	<h1>{name}</h1>
	<div class="grid">
		<div>
			{#if obj.spawns}
				<section class="panel">
					{#key `${flavor}:${id}`}
						<ZoneMap layers={[{ label: name ?? '', color: '#4aa3e8', entries: [{ name: name ?? '', data: obj }] }]} />
					{/key}
				</section>
			{:else}
				<p class="notice">No known spawn locations.</p>
			{/if}
			<div class="cols">
				<RefList title="Starts" refs={obj.starts} />
				<RefList title="Ends" refs={obj.ends} />
				<RefList title="Objective of" refs={obj.objectiveOf} />
				<RefList title="Contains" refs={obj.contains} />
			</div>
		</div>
		<aside>
			<section class="panel">
				<h3>Quick facts</h3>
				<dl class="facts">
					{#if obj.zone}<dt>Zone</dt><dd><a href="#/{flavor}/zone/{obj.zone.zone}">{site.zoneName(obj.zone.zone)}</a></dd>{/if}
					<dt>ID</dt><dd>{obj.id}</dd>
				</dl>
			</section>
		</aside>
	</div>
{/if}
