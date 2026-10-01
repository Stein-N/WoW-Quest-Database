<script lang="ts">
	import { money } from '$lib/format';

	let { copper }: { copper: number } = $props();
	const m = $derived(money(copper));
</script>

<span class="money">
	{#if m.g}<span class="gold">{m.g}g</span>{/if}
	{#if m.s}<span class="silver">{m.s}s</span>{/if}
	{#if m.c || (!m.g && !m.s)}<span class="copper">{m.c}c</span>{/if}
</span>
