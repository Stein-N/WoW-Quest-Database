<script lang="ts">
	import { site } from '$lib/context.svelte';
	import { refName } from '$lib/data';
	import type { Ref } from '$lib/types';

	let { ref, showLevel = false }: { ref: Ref; showLevel?: boolean } = $props();

	const name = $derived(refName(ref, site.names));
	const cls = $derived(ref.t === 'item' && ref.q !== undefined ? `q${ref.q}` : `link-${ref.t}`);
</script>

{#if ref.missing}<span class="muted" title="Not in this game version's data">{name}</span
	>{:else}<a class={cls} href="#/{site.flavor}/{ref.t}/{ref.id}">{name}</a>{/if}{#if showLevel && ref.lvl}{' '}<span
		class="muted">[{ref.lvl}]</span
	>{/if}
