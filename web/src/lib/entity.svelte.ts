import { getEntity, getEntityL10n } from './data';
import { settings } from './settings.svelte';
import type { Kind, L10nEntry } from './types';

/**
 * Loads one entity and its translation for the current content locale, following route
 * changes. Must be called during component initialisation (it registers effects).
 * `value` is undefined while loading and null when the ID does not exist.
 */
export function useEntity<T>(kind: Kind, params: () => { flavor: string; id: number }) {
	const state = $state<{ value: T | null | undefined; tr: L10nEntry | null }>({
		value: undefined,
		tr: null
	});

	$effect(() => {
		const { flavor, id } = params();
		state.value = undefined;
		let current = true;
		getEntity<T>(flavor, kind, id).then((v) => {
			if (current) state.value = v;
		});
		return () => (current = false);
	});

	$effect(() => {
		const { flavor, id } = params();
		const locale = settings.locale;
		state.tr = null;
		let current = true;
		getEntityL10n(flavor, locale, kind, id).then((t) => {
			if (current) state.tr = t;
		});
		return () => (current = false);
	});

	return state;
}
