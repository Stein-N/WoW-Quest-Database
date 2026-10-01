<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { LOCALES, settings } from '$lib/settings.svelte';
	import { FLAVOR_LABELS } from '$lib/format';

	let { children } = $props();

	const flavor = $derived(page.params.flavor ?? 'classic');
	let query = $state('');

	function switchFlavor(next: string) {
		const path = window.location.hash.replace(/^#/, '') || '/';
		const parts = path.split('/');
		if (parts[1] === 'classic' || parts[1] === 'forever') {
			parts[1] = next;
			window.location.hash = parts.join('/');
		} else {
			window.location.hash = `/${next}`;
		}
	}

	function search(e: SubmitEvent) {
		e.preventDefault();
		const q = query.trim();
		window.location.hash = `/${flavor}/search/${encodeURIComponent(q)}`;
	}
</script>

<svelte:head>
	<link rel="icon" type="image/png" href="favicon.png" />
	<link rel="apple-touch-icon" href="apple-touch-icon.png" />
	<title>WoW Quest Database</title>
</svelte:head>

<header>
	<div class="bar">
		<a class="brand" href="#/{flavor}"><img src="logo.png" alt="" width="28" height="28" />Quest Database</a>
		<nav>
			<a href="#/{flavor}/quests">Quests</a>
			<a href="#/{flavor}/questlines">Questlines</a>
			<a href="#/{flavor}/zones">Zones</a>
			<a href="#/{flavor}/export">Export</a>
		</nav>
		<form class="search" onsubmit={search} role="search">
			<input type="search" placeholder="Search quests, NPCs, items, objects…" bind:value={query} />
		</form>
		<div class="switches">
			<div class="seg" role="group" aria-label="Game version">
				{#each Object.entries(FLAVOR_LABELS) as [id, label] (id)}
					<button class:active={flavor === id} onclick={() => switchFlavor(id)}>{label}</button>
				{/each}
			</div>
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
	{@render children()}
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
		gap: 0.8rem;
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
	.seg {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
	}
	.seg button {
		background: var(--panel);
		border: none;
		padding: 0.3rem 0.6rem;
		cursor: pointer;
		font-size: 0.85rem;
		white-space: nowrap;
	}
	.seg button + button {
		border-left: 1px solid var(--border);
	}
	.seg button.active {
		background: var(--accent);
		color: var(--bg);
	}
</style>
