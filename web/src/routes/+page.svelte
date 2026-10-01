<script lang="ts">
	import { getChangelog, getMeta } from '$lib/data';
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

{#await getChangelog() then versions}
	{#if versions.length}
		<section class="notes">
			<h2>Patch notes</h2>
			{#each versions as v, i (v.version)}
				<details class="panel" open={i === 0}>
					<summary>
						<span class="version">v{v.version}</span>
						{#if i === 0}<span class="badge">current</span>{/if}
						<span class="muted">{new Date(v.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
					</summary>
					{#if v.data}
						<p class="data muted">
							Data: QuestieDB
							<a href="https://github.com/Questie/QuestieDB/commit/{v.data.questie.commit}" target="_blank" rel="noreferrer"
								>{v.data.questie.commit.slice(0, 7)}</a
							>
							({v.data.questie.date}) · VMangos {v.data.vmangos.snapshot} ({v.data.vmangos.published})
						</p>
					{/if}
					{#if v.changes.length}
						<ul>
							{#each v.changes as change, j (j)}<li>{change}</li>{/each}
						</ul>
					{:else}
						<p class="muted">Data update only.</p>
					{/if}
				</details>
			{/each}
		</section>
	{/if}
{/await}

<style>
	.notes {
		margin-top: 2rem;
	}
	.notes details {
		padding: 0.6rem 1rem;
		margin-bottom: 0.6rem;
	}
	.notes summary {
		cursor: pointer;
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
	}
	.notes .version {
		font-weight: 700;
		color: var(--accent);
	}
	.notes .data {
		font-size: 0.85rem;
		margin: 0.5rem 0 0.3rem;
	}
	.notes ul {
		margin: 0.4rem 0 0.2rem;
		padding-left: 1.2rem;
	}
	.notes li {
		padding: 0.1rem 0;
	}
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
