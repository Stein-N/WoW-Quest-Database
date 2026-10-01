<script lang="ts">
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { useEntity } from '$lib/entity.svelte';
	import { levelRange } from '$lib/format';
	import RefList from '$lib/components/RefList.svelte';
	import ZoneMap from '$lib/components/ZoneMap.svelte';
	import type { Npc } from '$lib/types';

	const flavor = $derived(page.params.flavor!);
	const id = $derived(Number(page.params.id));
	const entity = useEntity<Npc>('npc', () => ({ flavor, id }));
	const npc = $derived(entity.value);
	const name = $derived(entity.tr?.name ?? npc?.name);
	const subName = $derived(entity.tr?.subName ?? npc?.subName);

	const REACT: Record<string, string> = { A: 'Alliance', H: 'Horde', AH: 'Friendly to both' };
</script>

<svelte:head><title>{name ?? 'NPC'} – WoW Quest Database</title></svelte:head>

{#if npc === undefined}
	<p class="muted">Loading…</p>
{:else if npc === null}
	<h1>NPC {id} not found</h1>
{:else}
	<h1>{name}</h1>
	{#if subName}<p class="muted" style="margin-top:0">&lt;{subName}&gt;</p>{/if}

	<div class="grid">
		<div>
			{#if npc.spawns || npc.waypoints}
				<section class="panel">
					{#key `${flavor}:${id}`}
						<ZoneMap layers={[{ label: name ?? '', color: '#e8524a', entries: [{ name: name ?? '', data: npc }] }]} />
					{/key}
				</section>
			{:else}
				<p class="notice">No known spawn locations.</p>
			{/if}
			<div class="cols">
				<RefList title="Starts" refs={npc.starts} />
				<RefList title="Ends" refs={npc.ends} />
				<RefList title="Objective of" refs={npc.objectiveOf} />
			</div>
			<div class="cols">
				<RefList title="Drops" refs={npc.loot} showChance limit={30} />
				<RefList title="Sells" refs={npc.sells} limit={30} />
			</div>
		</div>
		<aside>
			<section class="panel">
				<h3>Quick facts</h3>
				<dl class="facts">
					<dt>Level</dt><dd>{levelRange(npc.minLevel, npc.maxLevel)}</dd>
					{#if npc.rank && npc.rank !== 'Normal'}<dt>Classification</dt><dd>{npc.rank}</dd>{/if}
					{#if npc.minHealth}<dt>Health</dt><dd>{levelRange(npc.minHealth, npc.maxHealth)}</dd>{/if}
					{#if npc.react}<dt>Reaction</dt><dd class="side-{npc.react.length === 1 ? npc.react : ''}">{REACT[npc.react] ?? npc.react}</dd>{/if}
					{#if npc.faction}<dt>Faction</dt><dd>{npc.faction.name}</dd>{/if}
					{#if npc.roles}<dt>Services</dt><dd>{npc.roles.join(', ')}</dd>{/if}
					{#if npc.zone}<dt>Zone</dt><dd><a href="#/{flavor}/zone/{npc.zone.zone}">{site.zoneName(npc.zone.zone)}</a></dd>{/if}
					<dt>ID</dt><dd>{npc.id}</dd>
				</dl>
			</section>
		</aside>
	</div>
{/if}
