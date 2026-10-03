<script lang="ts">
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { getEntity, getSearchIndex } from '$lib/data';
	import { useEntity } from '$lib/entity.svelte';
	import TranslationNote from '$lib/components/TranslationNote.svelte';
	import RefList from '$lib/components/RefList.svelte';
	import ZoneMap from '$lib/components/ZoneMap.svelte';
	import type { GameObject, Ref } from '$lib/types';

	const flavor = $derived(page.params.flavor!);
	const id = $derived(Number(page.params.id));
	const entity = useEntity<GameObject>('object', () => ({ flavor, id }));
	const obj = $derived(entity.value);
	const name = $derived(entity.tr?.name ?? obj?.name);

	// Objects with the same (English) name are shown as one: e.g. every "Campfire".
	let group = $state<GameObject[]>([]);
	$effect(() => {
		const o = obj;
		const f = flavor;
		group = o ? [o] : [];
		if (!o) return;
		let current = true;
		getSearchIndex(f)
			.then((index) => {
				const ids = index.object.filter((r) => r[1] === o.name && r[0] !== o.id).map((r) => r[0]);
				return Promise.all(ids.map((i) => getEntity<GameObject>(f, 'object', i)));
			})
			.then((others) => {
				if (current) group = [o, ...others.filter((x): x is GameObject => !!x)].sort((a, b) => a.id - b.id);
			});
		return () => (current = false);
	});

	function merged(key: 'starts' | 'ends' | 'objectiveOf' | 'contains'): Ref[] | undefined {
		const seen = new Map<string, Ref>();
		for (const o of group) for (const r of o[key] ?? []) seen.set(`${r.t}:${r.id}`, r);
		return seen.size ? [...seen.values()] : undefined;
	}

	const spawned = $derived(group.filter((o) => o.spawns));
	let shownMap = $state('');
	let shownIds = $state<number[]>([]);
</script>

<svelte:head><title>{name ?? 'Object'} – WoW Quest Database</title></svelte:head>

{#if obj === undefined}
	<p class="muted">Loading…</p>
{:else if obj === null}
	<h1>Object {id} not found</h1>
{:else}
	<h1>{name}</h1>
	<TranslationNote tr={entity.tr} />
	<div class="grid">
		<div>
			{#if spawned.length}
				<section class="panel">
					{#key `${flavor}:${id}:${spawned.length}`}
						<ZoneMap
							layers={[{ label: name ?? '', color: '#4aa3e8', entries: spawned.map((o) => ({ name: `${name} (${o.id})`, id: o.id, data: o })) }]}
							bind:shownMap
							bind:shownIds
						/>
					{/key}
				</section>
			{:else}
				<p class="notice">No known spawn locations.</p>
			{/if}
			<div class="cols">
				<RefList title="Starts" refs={merged('starts')} />
				<RefList title="Ends" refs={merged('ends')} />
				<RefList title="Objective of" refs={merged('objectiveOf')} />
				<RefList title="Contains" refs={merged('contains')} />
			</div>
		</div>
		<aside>
			<section class="panel">
				<h3>Quick facts</h3>
				<dl class="facts">
					{#if group.length > 1}
						<dt>Objects</dt><dd>{group.length} with this name</dd>
						{#if shownIds.length}
							<dt>IDs on {shownMap}</dt>
							<dd class="ids">{shownIds.join(', ')}</dd>
						{/if}
					{:else}
						{#if obj.zone}<dt>Zone</dt><dd><a href="#/{flavor}/zone/{obj.zone.zone}">{site.zoneName(obj.zone.zone)}</a></dd>{/if}
						<dt>ID</dt><dd>{obj.id}</dd>
					{/if}
				</dl>
			</section>
		</aside>
	</div>
{/if}

<style>
	.ids {
		max-height: 20rem;
		overflow-y: auto;
		overflow-wrap: anywhere;
	}
</style>
