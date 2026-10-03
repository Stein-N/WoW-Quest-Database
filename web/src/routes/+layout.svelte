<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { site } from '$lib/context.svelte';
	import { LOCALES, settings } from '$lib/settings.svelte';

	let { children } = $props();

	let query = $state('');

	$effect(() => {
		void settings.locale;
		site.ensure();
	});

	// links from when the site also covered Classic Era: #/classic/quest/2, #/forever/quest/2
	function dropOldFlavor() {
		const m = window.location.hash.match(/^#\/(?:classic|forever)(\/.*)?$/);
		if (m) window.location.replace(`#${m[1] ?? '/'}`);
	}
	onMount(() => {
		dropOldFlavor();
		window.addEventListener('hashchange', dropOldFlavor);
		return () => window.removeEventListener('hashchange', dropOldFlavor);
	});

	function search(e: SubmitEvent) {
		e.preventDefault();
		const q = query.trim();
		window.location.hash = `/search/${encodeURIComponent(q)}`;
	}
</script>

<svelte:head>
	<link rel="icon" type="image/png" href="favicon.png" />
	<link rel="apple-touch-icon" href="apple-touch-icon.png" />
	<title>WoW Forever Quest Database</title>
</svelte:head>

<header>
	<div class="bar">
		<a class="brand" href="#/"><img src="logo.png" alt="" width="28" height="28" />Quest Database</a>
		<nav>
			<a href="#/quests">Quests</a>
			<a href="#/questlines">Questlines</a>
			<a href="#/npcs">NPCs</a>
			<a href="#/items">Items</a>
			<a href="#/objects">Objects</a>
			<a href="#/zones">Zones</a>
			<a href="#/export">Export</a>
		</nav>
		<form class="search" onsubmit={search} role="search">
			<input type="search" placeholder="Search quests, NPCs, items, objects…" bind:value={query} />
		</form>
		<div class="switches">
			<select
				aria-label="Content language"
				value={settings.locale}
				onchange={(e) => (settings.locale = e.currentTarget.value)}
			>
				{#each Object.entries(LOCALES) as [code, label] (code)}
					<option value={code}>{label}</option>
				{/each}
			</select>
		</div>
	</div>
</header>

<main>
	{#if site.zones}
		{@render children()}
	{:else}
		<p class="muted">Loading…</p>
	{/if}
</main>

<style>
	header {
		background: var(--panel);
		border-bottom: 1px solid var(--border);
		position: sticky;
		top: 0;
		z-index: 1100;
	}
	.bar {
		max-width: 1200px;
		margin: 0 auto;
		padding: 0.5rem 16px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 700;
		color: var(--accent);
		font-size: 1.05rem;
	}
	nav {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.8rem;
		min-width: 0;
	}
	nav a {
		color: var(--text);
	}
	.search {
		flex: 1 1 220px;
	}
	.search input {
		width: 100%;
	}
	.switches {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
</style>
