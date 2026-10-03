<script lang="ts">
	import type { L10nEntry } from '$lib/types';

	let { tr }: { tr: L10nEntry | null } = $props();

	const LABELS: Record<string, string> = {
		name: 'name',
		subName: 'title',
		objectivesText: 'objectives',
		details: 'description',
		progress: 'progress text',
		completion: 'completion text',
		endText: 'log text',
		description: 'description'
	};
	const fields = $derived((tr?.azerothcore ?? []).map((f) => LABELS[f] ?? f));
</script>

{#if fields.length}
	<p class="note muted">
		Translation of the {fields.join(', ')} from AzerothCore (Wrath of the Lich King 3.3.5), as no
		Classic source has it; it may differ from the text in Classic.
	</p>
{/if}

<style>
	.note {
		font-size: 0.8rem;
		margin: -0.4rem 0 0.8rem;
	}
</style>
