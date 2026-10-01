// Filter state kept in the URL, after the route: #/classic/quests?side=A&min=10
//
// Components read their initial state with `urlParams()` and call `syncUrl()` from an effect.
// The URL is updated in place (no new history entry, no scroll), so going back from a page
// you opened returns to exactly the filtered view you left.

import { replaceState } from '$app/navigation';

type Value = string | number | boolean | null | undefined;

function split(hash: string): [string, string] {
	const h = hash.replace(/^#/, '');
	const i = h.indexOf('?');
	return i < 0 ? [h, ''] : [h.slice(0, i), h.slice(i + 1)];
}

export function urlParams(): URLSearchParams {
	return new URLSearchParams(split(window.location.hash)[1]);
}

export const param = {
	str: (p: URLSearchParams, key: string, fallback = '') => p.get(key) ?? fallback,
	num: (p: URLSearchParams, key: string, fallback: number | null = null) => {
		const v = p.get(key);
		return v !== null && v !== '' && !Number.isNaN(Number(v)) ? Number(v) : fallback;
	},
	list: (p: URLSearchParams, key: string) => (p.get(key) ?? '').split(',').filter(Boolean)
};

let timer: ReturnType<typeof setTimeout> | undefined;
let pending: { path: string; params: URLSearchParams } | null = null;

/**
 * Merges `values` into the query part of the current hash; keys not mentioned are kept, so
 * several components on one page (e.g. map and quest table) can each own their keys. Empty,
 * null and false values, and values equal to their default, remove the key.
 */
export function syncUrl(values: Record<string, Value>, defaults: Record<string, Value> = {}) {
	const [path, query] = split(window.location.hash);
	if (!pending || pending.path !== path) pending = { path, params: new URLSearchParams(query) };
	for (const [key, value] of Object.entries(values)) {
		const omit = value === null || value === undefined || value === '' || value === false || defaults[key] === value;
		if (omit) pending.params.delete(key);
		else pending.params.set(key, value === true ? '1' : String(value));
	}
	clearTimeout(timer);
	timer = setTimeout(() => {
		const update = pending;
		pending = null;
		// only if we are still on the same page and something changed
		if (!update || split(window.location.hash)[0] !== update.path) return;
		const q = update.params.toString().replace(/%2C/g, ',');
		const next = `#${update.path}${q ? `?${q}` : ''}`;
		if (window.location.hash !== next) replaceState(next, {});
	}, 200);
}
