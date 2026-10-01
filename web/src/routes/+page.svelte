<script lang="ts">
	import { getMeta } from '$lib/data';
</script>

<h1>WoW Quest Database</h1>
<p class="muted">
	Quests, NPCs, objects and items for Classic Era and WoW Forever, built from QuestieDB and the
	VMangos world database.
</p>

{#await getMeta() then meta}
	<div class="cols" style="margin-top:1rem">
		{#each Object.entries(meta.flavors) as [id, f] (id)}
			<a class="panel card" href="#/{id}">
				<h2>{f.label}</h2>
				<dl class="facts">
					<dt>Quests</dt><dd>{f.counts.quest.toLocaleString('en')}</dd>
					<dt>NPCs</dt><dd>{f.counts.npc.toLocaleString('en')}</dd>
					<dt>Objects</dt><dd>{f.counts.object.toLocaleString('en')}</dd>
					<dt>Items</dt><dd>{f.counts.item.toLocaleString('en')}</dd>
				</dl>
			</a>
		{/each}
	</div>
	<p class="muted" style="font-size:0.85rem">
		Data: QuestieDB {meta.questie ?? 'unknown'} · VMangos {meta.vmangos ?? 'unknown'} · built
		{new Date(meta.built).toLocaleString('en-GB')}
	</p>
{:catch err}
	<p class="notice">Site data is missing ({err.message}). Run <code>make data</code> first.</p>
{/await}

<style>
	.card {
		color: inherit;
		text-decoration: none;
		display: block;
	}
	.card:hover {
		border-color: var(--accent);
	}
	.card h2 {
		margin-top: 0;
		color: var(--accent);
	}
</style>
