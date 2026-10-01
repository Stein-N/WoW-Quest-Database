// Browser version of etl/export_lua.py: turns site data into a Lua file. Keep both in sync.

import { BUCKET, getMeta, getNames, getQuestIndex, getQuestlines, getSearchIndex, getShard, getZoneNames } from './data';
import type { Kind, Meta } from './types';

export type ExportType = Kind | 'questline';

export interface ExportOptions {
	flavor: string;
	type: ExportType;
	/** top-level fields to keep; empty = all */
	fields: string[];
	ids: string;
	zone: number | null;
	locale: string;
	refs: 'id' | 'full';
	style: 'addon' | 'return';
	varName: string;
}

/** Top-level fields of each record type, in display order (see types.ts). */
export const FIELDS: Record<ExportType, string[]> = {
	quest: [
		'name', 'level', 'reqLevel', 'maxLevel', 'side', 'races', 'classes', 'zone', 'type',
		'suggestedPlayers', 'timeLimit', 'repeatable', 'objectivesText', 'details', 'progress',
		'completion', 'endText', 'starters', 'enders', 'objectives', 'providedItem', 'requiredItems',
		'chain', 'requirements', 'rewards', 'spawns', 'questline', 'sources'
	],
	npc: [
		'name', 'subName', 'minLevel', 'maxLevel', 'minHealth', 'maxHealth', 'rank', 'react', 'faction',
		'roles', 'zone', 'spawns', 'waypoints', 'starts', 'ends', 'objectiveOf', 'sells', 'loot', 'sources'
	],
	object: ['name', 'zone', 'spawns', 'waypoints', 'starts', 'ends', 'objectiveOf', 'contains'],
	item: [
		'name', 'quality', 'itemLevel', 'reqLevel', 'class', 'subClass', 'slot', 'bonding', 'unique',
		'stack', 'slots', 'armor', 'block', 'durability', 'sellPrice', 'buyPrice', 'description', 'classes',
		'races', 'reqSkill', 'reqRep', 'stats', 'damage', 'speed', 'resistances', 'spells', 'startsQuest',
		'droppedBy', 'objectDrops', 'containedIn', 'vendors', 'rewardFrom', 'objectiveOf', 'sources'
	],
	questline: ['root', 'zone', 'levels', 'side', 'quests', 'edges', 'exclusive']
};

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type Rec = Record<string, Json>;

// ------------------------------------------------------------------ selection

export function parseIds(spec: string): Set<number> | null {
	const ids = new Set<number>();
	for (const raw of spec.split(',')) {
		const part = raw.trim();
		if (!part) continue;
		const range = part.match(/^(\d+)\s*-\s*(\d+)$/);
		if (range) {
			const [lo, hi] = [Number(range[1]), Number(range[2])];
			if (hi - lo > 1_000_000) throw new Error(`range too large: ${part}`);
			for (let i = lo; i <= hi; i++) ids.add(i);
		} else if (/^\d+$/.test(part)) {
			ids.add(Number(part));
		} else {
			throw new Error(`not an ID or range: ${part}`);
		}
	}
	return ids.size ? ids : null;
}

function zoneOf(rec: Rec): number | undefined {
	const z = rec.zone;
	if (z && typeof z === 'object' && !Array.isArray(z)) return (z.zone ?? z.sort) as number | undefined;
	return typeof z === 'number' ? z : undefined;
}

async function allIds(flavor: string, type: Kind): Promise<number[]> {
	if (type === 'quest') return (await getQuestIndex(flavor)).map((r) => r[0]);
	const index = await getSearchIndex(flavor);
	return index[type].map((r) => r[0]);
}

// ------------------------------------------------------------------ transforms

function localizeRefs(value: Json, names: Record<string, Record<string, string>>, zones: Record<string, string>): Json {
	if (Array.isArray(value)) return value.map((v) => localizeRefs(v, names, zones));
	if (value && typeof value === 'object') {
		let v = value;
		if ('t' in v && 'id' in v && 'name' in v) {
			const n = names[v.t as string]?.[String(v.id)];
			if (n) v = { ...v, name: n };
		} else if ('zone' in v && 'name' in v && zones[String(v.zone)]) {
			v = { ...v, name: zones[String(v.zone)] };
		}
		return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, localizeRefs(x, names, zones)]));
	}
	return value;
}

const REF_DETAIL = new Set(['t', 'id', 'name', 'q', 'lvl', 'missing']);

function compactRefs(value: Json): Json {
	if (Array.isArray(value)) return value.map(compactRefs);
	if (value && typeof value === 'object') {
		if ('t' in value && 'id' in value) {
			const extra = Object.entries(value).filter(([k]) => !REF_DETAIL.has(k));
			if (!extra.length) return value.id;
			return { id: value.id, ...Object.fromEntries(extra.map(([k, v]) => [k, compactRefs(v)])) };
		}
		return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, compactRefs(v)]));
	}
	return value;
}

// ------------------------------------------------------------------ Lua serialisation

const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;
const KEYWORDS = new Set(
	'and break do else elseif end false for function goto if in local nil not or repeat return then true until while'.split(' ')
);

function luaString(s: string): string {
	const body = s
		.replace(/\\/g, '\\\\')
		.replace(/"/g, '\\"')
		.replace(/\n/g, '\\n')
		.replace(/\r/g, '\\r')
		// eslint-disable-next-line no-control-regex
		.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, (c) => `\\${String(c.charCodeAt(0)).padStart(3, '0')}`);
	return `"${body}"`;
}

function luaKey(key: string): string {
	if (/^-?\d+$/.test(key)) return `[${Number(key)}]`;
	if (IDENT.test(key) && !KEYWORDS.has(key)) return key;
	return `[${luaString(key)}]`;
}

export function luaValue(value: Json | undefined): string {
	if (value === null || value === undefined) return 'nil';
	if (value === true) return 'true';
	if (value === false) return 'false';
	if (typeof value === 'number') return String(value);
	if (typeof value === 'string') return luaString(value);
	if (Array.isArray(value)) return `{${value.map(luaValue).join(', ')}}`;
	const items = Object.entries(value).filter(([, v]) => v !== null && v !== undefined);
	return items.length ? `{ ${items.map(([k, v]) => `${luaKey(k)} = ${luaValue(v)}`).join(', ')} }` : '{}';
}

// ------------------------------------------------------------------ export

export interface ExportResult {
	text: string;
	count: number;
	fileName: string;
}

export async function exportLua(
	opts: ExportOptions,
	onProgress?: (done: number, total: number) => void
): Promise<ExportResult> {
	if (!IDENT.test(opts.varName) || KEYWORDS.has(opts.varName)) {
		throw new Error(`Table name must be a Lua identifier: ${opts.varName}`);
	}
	const meta: Meta = await getMeta();
	const wantedIds = parseIds(opts.ids);
	const localized = opts.locale !== 'enUS';
	let records = new Map<number, Rec>();

	if (opts.type === 'questline') {
		for (const line of await getQuestlines(opts.flavor)) records.set(line.id, line as unknown as Rec);
		onProgress?.(1, 1);
	} else {
		const kind = opts.type;
		let ids = await allIds(opts.flavor, kind);
		if (wantedIds) ids = ids.filter((i) => wantedIds.has(i));
		const buckets = [...new Set(ids.map((i) => Math.floor(i / BUCKET)))].sort((a, b) => a - b);
		const wanted = new Set(ids);
		let done = 0;
		onProgress?.(0, buckets.length);
		// a few requests in parallel keeps it quick without flooding the server
		const queue = [...buckets];
		const worker = async () => {
			for (let b = queue.shift(); b !== undefined; b = queue.shift()) {
				const [shard, tr] = await Promise.all([
					getShard<Rec>(opts.flavor, kind, b),
					localized ? getShard<Rec>(opts.flavor, kind, b, opts.locale) : Promise.resolve({} as Record<string, Rec>)
				]);
				for (const [id, rec] of Object.entries(shard)) {
					if (wanted.has(Number(id))) records.set(Number(id), { ...rec, ...(tr[id] ?? {}) });
				}
				onProgress?.(++done, buckets.length);
			}
		};
		await Promise.all(Array.from({ length: 6 }, worker));
	}

	if (wantedIds && opts.type === 'questline') {
		records = new Map([...records].filter(([id]) => wantedIds.has(id)));
	}
	if (opts.zone !== null) {
		records = new Map([...records].filter(([, r]) => zoneOf(r) === opts.zone));
	}

	if (localized) {
		const [names, zones] = await Promise.all([getNames(opts.flavor, opts.locale), getZoneNames(opts.flavor, opts.locale)]);
		const table = (names ?? {}) as unknown as Record<string, Record<string, string>>;
		for (const [id, rec] of records) records.set(id, localizeRefs(rec, table, zones) as Rec);
	}

	const keep = opts.fields.length ? new Set(opts.fields) : null;
	const lines: string[] = [];
	for (const [id, rec] of [...records].sort((a, b) => a[0] - b[0])) {
		let out: Json = Object.fromEntries(
			Object.entries(rec).filter(([k]) => k !== 'id' && (!keep || keep.has(k)))
		);
		if (opts.refs === 'id') out = compactRefs(out);
		lines.push(`    [${id}] = ${luaValue(out)},`);
	}

	const fileName = `${opts.varName}.lua`;
	const header = [
		`-- ${fileName}`,
		'--',
		`-- ${opts.type} data for ${meta.flavors[opts.flavor]?.label ?? opts.flavor}, exported from the WoW Quest Database.`,
		`-- Sources: QuestieDB ${meta.questie}, VMangos ${meta.vmangos} (built ${meta.built}).`,
		`-- Generated ${new Date().toISOString().slice(0, 19)}Z on the website: type=${opts.type}` +
			`${opts.fields.length ? ` fields=${opts.fields.join(',')}` : ''}${opts.ids ? ` ids=${opts.ids}` : ''}` +
			`${opts.zone !== null ? ` zone=${opts.zone}` : ''} locale=${opts.locale} refs=${opts.refs}`,
		`-- ${lines.length} entries.`,
		''
	];
	const body =
		opts.style === 'return'
			? ['return {', ...lines, '}', '']
			: ['local _, addon = ...', '', `addon.${opts.varName} = {`, ...lines, '}', ''];
	return { text: [...header, ...body].join('\n'), count: lines.length, fileName };
}
