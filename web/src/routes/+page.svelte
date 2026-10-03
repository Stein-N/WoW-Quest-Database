<script lang="ts">
	import { FLAVOR } from '$lib/context.svelte';
	import { getChangelog, getMeta } from '$lib/data';
	import { FLAVOR_LABELS } from '$lib/format';
</script>

<h1>WoW Forever Quest Database</h1>
<p class="muted">
	Quests, NPCs, objects and items for WoW Forever, built from QuestieDB's Forever data. Texts,
	rewards, vendors and loot are completed from VMangos (Classic 1.12), the game's cache, Wowhead and
	AzerothCore where QuestieDB has none; quests new to Forever may lack them.
</p>

{#await getMeta() then meta}
	{@const f = meta.flavors[FLAVOR]}
	<div class="cols" style="margin-top:1rem">
		<a class="panel tile" href="#/quests"><strong>{f.counts.quest.toLocaleString('en')}</strong> Quests</a>
		<a class="panel tile" href="#/questlines"><strong>Questlines</strong> Quest chains as a graph</a>
		<a class="panel tile" href="#/zones"><strong>Zones</strong> Browse quests by zone</a>
		<a class="panel tile" href="#/npcs"><strong>{f.counts.npc.toLocaleString('en')}</strong> NPCs</a>
		<a class="panel tile" href="#/items"><strong>{f.counts.item.toLocaleString('en')}</strong> Items</a>
		<a class="panel tile" href="#/objects"><strong>{f.counts.object.toLocaleString('en')}</strong> Objects</a>
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
					{#if v.website?.length}
						<h3>Website</h3>
						<ul>
							{#each v.website as note, j (j)}<li>{note}</li>{/each}
						</ul>
					{/if}
					{#if v.dataNotes?.length || v.dataChanges}
						<h3>Data</h3>
						<ul>
							{#each v.dataNotes ?? [] as note, j (j)}<li>{note}</li>{/each}
							{#each Object.entries(v.dataChanges ?? {}) as [flavor, lines] (flavor)}
								<li><strong>{FLAVOR_LABELS[flavor] ?? flavor}:</strong> {lines.join(' ')}</li>
							{/each}
						</ul>
					{/if}
					{#if v.commits?.length}
						<details class="tech">
							<summary class="muted">Technical changes ({v.commits.length})</summary>
							<ul>
								{#each v.commits as c, j (j)}<li>{c}</li>{/each}
							</ul>
						</details>
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
	.notes h3 {
		font-size: 0.95rem;
		margin: 0.7rem 0 0.2rem;
	}
	.notes .tech {
		margin-top: 0.6rem;
		font-size: 0.88rem;
	}
	.notes .tech summary {
		cursor: pointer;
	}
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
