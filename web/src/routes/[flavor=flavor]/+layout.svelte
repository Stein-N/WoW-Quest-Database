<script lang="ts">
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { settings } from '$lib/settings.svelte';

	let { children } = $props();

	$effect(() => {
		void settings.locale;
		site.ensure(page.params.flavor!);
	});
</script>

{#if site.zones}
	{@render children()}
{:else}
	<p class="muted">Loading…</p>
{/if}
