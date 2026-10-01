<script lang="ts">
	import { page } from '$app/state';
	import { getMeta } from '$lib/data';
	import { FLAVOR_LABELS } from '$lib/format';

	const flavor = $derived(page.params.flavor!);
</script>

<h1>{FLAVOR_LABELS[flavor]}</h1>

{#await getMeta() then meta}
	{@const f = meta.flavors[flavor]}
	<div class="cols" style="margin-top:1rem">
		<a class="panel tile" href="#/{flavor}/quests"
			><strong>{f.counts.quest.toLocaleString('en')}</strong> Quests</a
		>
		<a class="panel tile" href="#/{flavor}/zones"><strong>Zones</strong> Browse quests by zone</a>
		<a class="panel tile" href="#/{flavor}/search/"
			><strong>{f.counts.npc.toLocaleString('en')}</strong> NPCs ·
			<strong>{f.counts.item.toLocaleString('en')}</strong> Items ·
			<strong>{f.counts.object.toLocaleString('en')}</strong> Objects</a
		>
	</div>
{/await}

{#if flavor === 'forever'}
	<p class="notice">
		Forever data comes from QuestieDB's Forever flavor. Quest texts and rewards are added from
		VMangos (Classic 1.12) where the quest exists there; quests new to Forever may lack them.
	</p>
{/if}

<style>
	.tile {
		color: inherit;
		display: block;
	}
	.tile:hover {
		border-color: var(--accent);
		text-decoration: none;
	}
	.tile strong {
		color: var(--accent);
		font-size: 1.2rem;
	}
</style>
