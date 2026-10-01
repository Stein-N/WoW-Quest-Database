// Loads the static JSON produced by etl/build.py. Everything lives under ./data relative to
// index.html; with hash routing the document URL never changes, so relative fetches are safe.

import type { Kind, Ref, Zones, Meta, QuestIndexRow, SearchIndex, L10nEntry } from './types';

export const BUCKET = 100;
const DATA = 'data';

const cache = new Map<string, Promise<unknown>>();

function load<T>(path: string): Promise<T> {
	let p = cache.get(path) as Promise<T> | undefined;
	if (!p) {
		p = fetch(`${DATA}/${path}`).then((r) => {
			if (!r.ok) throw new Error(`${r.status} ${path}`);
			return r.json() as Promise<T>;
		});
		p.catch(() => cache.delete(path));
		cache.set(path, p);
	}
	return p;
}

/** Like load(), but a missing file (e.g. a bucket without translations) resolves to {}. */
function loadOptional<T extends object>(path: string): Promise<T> {
	return load<T>(path).catch(() => ({}) as T);
}

export const getMeta = () => load<Meta>('meta.json');
export const getZones = (flavor: string) => load<Zones>(`${flavor}/zones.json`);
export const getQuestIndex = (flavor: string) => load<QuestIndexRow[]>(`${flavor}/quests.json`);
export const getSearchIndex = (flavor: string) => load<SearchIndex>(`${flavor}/search.json`);

export async function getEntity<T>(flavor: string, kind: Kind, id: number): Promise<T | null> {
	const shard = await loadOptional<Record<string, T>>(
		`${flavor}/${kind}/${Math.floor(id / BUCKET)}.json`
	);
	return shard[id] ?? null;
}

export async function getEntityL10n(
	flavor: string,
	locale: string,
	kind: Kind,
	id: number
): Promise<L10nEntry | null> {
	if (locale === 'enUS') return null;
	const shard = await loadOptional<Record<string, L10nEntry>>(
		`${flavor}/l10n/${locale}/${kind}/${Math.floor(id / BUCKET)}.json`
	);
	return shard[id] ?? null;
}

export type NameTable = Record<Kind, Record<string, string>>;

export function getNames(flavor: string, locale: string): Promise<NameTable | null> {
	if (locale === 'enUS') return Promise.resolve(null);
	return loadOptional<NameTable>(`${flavor}/l10n/${locale}/search.json`);
}

export function getZoneNames(flavor: string, locale: string): Promise<Record<string, string>> {
	if (locale === 'enUS') return Promise.resolve({});
	return loadOptional<Record<string, string>>(`${flavor}/l10n/${locale}/zones.json`);
}

export function refName(ref: Ref, names: NameTable | null): string {
	return names?.[ref.t]?.[ref.id] ?? ref.name;
}

export interface ZoneGiver extends Ref {
	spawns: Record<string, [number, number][]>;
	quests: number[];
}

export function getZoneGivers(flavor: string, areaId: number): Promise<{ givers?: ZoneGiver[] }> {
	return loadOptional(`${flavor}/zone/${areaId}.json`);
}
