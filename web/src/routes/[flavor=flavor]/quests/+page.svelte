<script lang="ts">
	import { page } from '$app/state';
	import { getQuestIndex } from '$lib/data';
	import QuestTable from '$lib/components/QuestTable.svelte';
</script>

<svelte:head><title>Quests – WoW Quest Database</title></svelte:head>

<h1>Quests</h1>
{#await getQuestIndex(page.params.flavor!)}
	<p class="muted">Loading…</p>
{:then rows}
	<QuestTable {rows} />
{/await}
