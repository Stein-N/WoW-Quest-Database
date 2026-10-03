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
	/** texts table name; default derived from varName (questData -> questTexts) */
	textVarName?: string;
}

/** Texts are always written to their own file (<name>Texts.<locale>.lua), keyed by entity ID. */
export const TEXT_FIELDS: Record<ExportType, string[]> = {
	quest: ['name', 'objectivesText', 'details', 'progress', 'completion', 'endText'],
	npc: ['name', 'subName'],
	object: ['name'],
	item: ['name', 'description'],
	questline: []
};

/** The player's name placeholder $N becomes ${playerName} in exported texts. */
function exportText(value: Json): Json {
	if (Array.isArray(value)) return value.map(exportText);
	return typeof value === 'string' ? value.replace(/\$[Nn]/g, '${playerName}') : value;
}

export function textVarFor(varName: string): string {
	return varName.endsWith('Data') ? `${varName.slice(0, -4)}Texts` : `${varName}Texts`;
}

/** Top-level fields of each record type, in display order (see types.ts). */
export const FIELDS: Record<ExportType, string[]> = {
	quest: [
		'name', 'level', 'reqLevel', 'maxLevel', 'side', 'races', 'classes', 'zone', 'uiMapId', 'type',
		'suggestedPlayers', 'timeLimit', 'repeatable', 'objectivesText', 'details', 'progress',
		'completion', 'endText', 'startedBy', 'finishedBy', 'objectives', 'providedItem', 'requiredItems',
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

/** What each field contains, shown as a tooltip on the export page. */
export const FIELD_DOCS: Record<ExportType, Record<string, string>> = {
	quest: {
		name: 'Quest title.',
		level: 'Quest level (the level shown in the quest log).',
		reqLevel: 'Minimum character level to accept the quest.',
		maxLevel: 'Maximum character level; above it the quest is no longer offered.',
		side: 'Faction: "A" Alliance, "H" Horde, "B" both.',
		races: 'Races that may take the quest, as names; only set when the quest is limited to some races.',
		classes: 'Classes that may take the quest, as names; only set for class quests.',
		zone: 'Zone of the quest (AreaTable ID). Negative values are categories such as classes, professions or holidays.',
		uiMapId: 'Map ID of the quest zone for the in-game map API (C_Map); missing for categories.',
		type: 'Quest type such as "Group", "Dungeon", "Raid", "PvP" or "Legendary"; missing for normal quests.',
		suggestedPlayers: 'Suggested group size.',
		timeLimit: 'Time limit in seconds.',
		repeatable: 'true if the quest can be done repeatedly.',
		objectivesText: 'Short objective text from the quest log, as a list of lines.',
		details: 'Quest description shown when accepting the quest. ${playerName} is the name of the player, $C and $R class and race, $B a line break.',
		progress: 'Text shown when talking to the quest ender before the objectives are complete.',
		completion: 'Text shown when turning the quest in.',
		endText: 'Quest log text once all objectives are done (e.g. "Return to …").',
		startedBy: 'Who starts the quest (as in QuestieDB): NPC, object or item IDs (choose "with type & name" to tell them apart).',
		finishedBy: 'Who the quest is turned in to (as in QuestieDB): NPC or object IDs.',
		objectives: 'Objectives: list of { kind = kill/item/object/reputation/killcredit/spell/event/extra, target, count, text, sources = where items drop }.',
		providedItem: 'Item ID the quest giver hands out when the quest is accepted (letters, tools …).',
		requiredItems: 'Item IDs needed for the quest that are not counted objectives.',
		chain: 'Quest chain: { prev, next, preSingle (one of), preGroup (all of), children, parent, groupWith, exclusive, breadcrumbs, breadcrumbFor } with quest IDs.',
		requirements: 'Other requirements: { skill = { id, value }, minRep / maxRep = { id (faction), value }, spell, money (copper) }.',
		rewards: 'Rewards: { type = "all" | "single", items, fixed, counts, xp, money, moneyMaxLevel (copper), spell, reputation = { { id, value } } }.',
		spawns: 'Map positions of the quest givers, turn-in targets and objective targets: { ["npc:123"] = { spawns = { [areaId] = { { x, y } } } } }, x/y in percent of the map.',
		questline: 'The questline this quest belongs to: { id, size }.',
		sources: 'Where the data comes from: "questie", "vmangos", "cache" (game client cache).'
	},
	npc: {
		name: 'NPC name.',
		subName: 'Title under the name, e.g. "Weaponsmith".',
		minLevel: 'Lowest level.',
		maxLevel: 'Highest level.',
		minHealth: 'Health at the lowest level.',
		maxHealth: 'Health at the highest level.',
		rank: '"Normal", "Elite", "Rare", "Rare Elite" or "Boss".',
		react: 'Friendly to: "A" Alliance, "H" Horde, "AH" both; missing = hostile to both.',
		faction: 'Faction ID (with "with type & name": { id, name }).',
		roles: 'Services as names, e.g. "Vendor", "Trainer", "Flight Master", "Quest Giver".',
		zone: 'Main zone (AreaTable ID).',
		spawns: 'Positions: { [areaId] = { { x, y }, … } }, x/y in percent of the zone map.',
		waypoints: 'Patrol paths: { [areaId] = { { { x, y }, … }, … } }.',
		starts: 'Quest IDs this NPC starts.',
		ends: 'Quest IDs turned in at this NPC.',
		objectiveOf: 'Quest IDs that require killing or interacting with this NPC.',
		sells: 'Items this NPC sells (QuestieDB and VMangos): item IDs, or { id, limit, restock (seconds) } for limited stock; vmangos = true marks entries known only from VMangos, which may be outdated.',
		loot: 'Drops: list of { id, chance (%), min, max } or plain item IDs.',
		sources: 'Where the data comes from: "questie", "vmangos".'
	},
	object: {
		name: 'Object name.',
		zone: 'Main zone (AreaTable ID).',
		spawns: 'Positions: { [areaId] = { { x, y }, … } }, x/y in percent of the zone map.',
		waypoints: 'Movement paths (transports): { [areaId] = { { { x, y }, … }, … } }.',
		starts: 'Quest IDs this object starts.',
		ends: 'Quest IDs turned in at this object.',
		objectiveOf: 'Quest IDs that require using this object.',
		contains: 'Item IDs that can be looted from this object.'
	},
	item: {
		name: 'Item name.',
		quality: '0 Poor, 1 Common, 2 Uncommon, 3 Rare, 4 Epic, 5 Legendary, 6 Artifact.',
		itemLevel: 'Item level.',
		reqLevel: 'Required character level.',
		class: 'Item class, e.g. "Weapon", "Armor", "Consumable", "Quest".',
		subClass: 'Sub class, e.g. "Dagger", "Cloth", "Bow".',
		slot: 'Equipment slot, e.g. "Head", "Two-Hand", "Finger".',
		bonding: 'e.g. "Binds when picked up", "Binds when equipped", "Quest Item".',
		unique: 'true if you can carry only one.',
		stack: 'Maximum stack size (only if more than 1).',
		slots: 'Number of slots (bags).',
		armor: 'Armor value.',
		block: 'Block value (shields).',
		durability: 'Maximum durability.',
		sellPrice: 'Vendor sell price in copper.',
		buyPrice: 'Vendor buy price in copper.',
		description: 'Flavor text shown in yellow at the bottom of the tooltip.',
		classes: 'Classes that can use the item, as names; only set when limited.',
		races: 'Races that can use the item, as names; only set when limited.',
		reqSkill: 'Required skill: { id, value } (with "with type & name": also name).',
		reqRep: 'Required reputation: { id (faction), value (standing) }.',
		stats: 'Stats: list of { stat = "Strength" …, value }.',
		damage: 'Weapon damage: list of { min, max, school }.',
		speed: 'Weapon speed in seconds.',
		resistances: 'Resistances: { fire = …, frost = …, … }.',
		spells: 'Effects: list of { id, trigger = "Use"/"Equip"/"Chance on hit", name, description }.',
		startsQuest: 'Quest ID this item starts.',
		droppedBy: 'NPCs that drop the item: list of { id, chance (%) } or NPC IDs.',
		objectDrops: 'Object IDs the item can be looted from.',
		containedIn: 'Item IDs (bags, boxes) that contain this item.',
		vendors: 'NPCs that sell the item (QuestieDB and VMangos): NPC IDs, or { id, limit, restock (seconds) } for limited stock; vmangos = true marks entries known only from VMangos, which may be outdated.',
		rewardFrom: 'Quest IDs that reward the item.',
		objectiveOf: 'Quest IDs that require the item.',
		sources: 'Where the data comes from: "questie", "vmangos".'
	},
	questline: {
		root: 'Quest ID of the first quest; its name names the questline.',
		zone: 'Main zone (AreaTable ID).',
		levels: 'Level range of the quests: { min, max }.',
		side: 'Faction: "A" Alliance, "H" Horde, "B" both or mixed.',
		quests: 'Quest IDs in the questline.',
		edges: 'Links between quests: { { from, to, kind } }, kind "pre" (from must be done first) or "breadcrumb".',
		exclusive: 'Pairs of quest IDs of which only one can be done.'
	}
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

/**
 * {t, id, name, ...} -> id, keeping extra facts such as chance or count. Zone references become
 * their area ID and faction/skill references lose their name, so data files carry no display text.
 */
function compactRefs(value: Json): Json {
	if (Array.isArray(value)) return value.map(compactRefs);
	if (value && typeof value === 'object') {
		const keys = Object.keys(value);
		const has = (k: string) => k in value;
		if (keys.length === 2 && has('name') && (has('zone') || has('sort'))) return (value.zone ?? value.sort) as Json;
		if (has('id') && has('name') && !has('t') && keys.every((k) => k === 'id' || k === 'name' || k === 'value')) {
			return has('value') ? { id: value.id, value: value.value } : value.id;
		}
		if ('t' in value && 'id' in value) {
			const extra = Object.entries(value).filter(([k]) => !REF_DETAIL.has(k));
			if (!extra.length) return value.id;
			return { id: value.id, ...Object.fromEntries(extra.map(([k, v]) => [k, compactRefs(v)])) };
		}
		return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, compactRefs(v)]));
	}
	return value;
}

/**
 * rewards.items groups -> the QuestRewards.lua shape, merged into rewards:
 *   type = "all",    items = {...}                  every item is rewarded
 *   type = "single", items = {...}, fixed = {...}   choose one of items, plus all fixed ones
 * With ID references, item lists are plain IDs and amounts above one go to counts[itemId].
 */
function questRewardsFormat(rewards: Rec, refs: 'id' | 'full'): Rec {
	const groups = rewards.items as { kind: string; items: Rec[] }[] | undefined;
	if (!groups?.length) return rewards;
	const fixed = groups.find((g) => g.kind === 'fixed')?.items ?? [];
	const choice = groups.find((g) => g.kind === 'choice')?.items ?? [];
	const out: Rec = choice.length
		? { type: 'single', items: choice as Json[], fixed: fixed as Json[] }
		: { type: 'all', items: fixed as Json[] };
	if (!fixed.length || !choice.length) delete out.fixed;
	if (refs === 'id') {
		const counts = Object.fromEntries(
			[...choice, ...fixed].filter((r) => ((r.count as number) || 1) > 1).map((r) => [String(r.id), r.count])
		);
		out.items = (out.items as Rec[]).map((r) => r.id);
		if (out.fixed) out.fixed = (out.fixed as Rec[]).map((r) => r.id);
		if (Object.keys(counts).length) out.counts = counts;
	}
	const rest = Object.fromEntries(Object.entries(rewards).filter(([k]) => k !== 'items'));
	return { ...out, ...rest };
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

export interface ExportFile {
	fileName: string;
	text: string;
	count: number;
}

function header(fileName: string, description: string, count: number, meta: Meta, opts: ExportOptions): string[] {
	return [
		`-- ${fileName}`,
		'--',
		`-- ${description}`,
		`-- Sources: QuestieDB ${meta.questie}, VMangos ${meta.vmangos} (built ${meta.built}).`,
		`-- Generated ${new Date().toISOString().slice(0, 19)}Z on the website: type=${opts.type}` +
			`${opts.fields.length ? ` fields=${opts.fields.join(',')}` : ''}${opts.ids ? ` ids=${opts.ids}` : ''}` +
			`${opts.zone !== null ? ` zone=${opts.zone}` : ''} locale=${opts.locale} refs=${opts.refs}`,
		`-- ${count} entries.`,
		''
	];
}

const entries = (map: Map<number, Json>) =>
	[...map].sort((a, b) => a[0] - b[0]).map(([id, rec]) => `    [${id}] = ${luaValue(rec)},`);

export async function exportLua(
	opts: ExportOptions,
	onProgress?: (done: number, total: number) => void
): Promise<ExportFile[]> {
	const textVar = opts.textVarName || textVarFor(opts.varName);
	for (const name of [opts.varName, textVar]) {
		if (!IDENT.test(name) || KEYWORDS.has(name)) throw new Error(`Table names must be Lua identifiers: ${name}`);
	}
	const meta: Meta = await getMeta();
	const allLocales = ['enUS', ...meta.locales];
	if (opts.locale !== 'all' && !allLocales.includes(opts.locale)) throw new Error(`Unknown language ${opts.locale}`);
	// "all": one data file (English references) plus a texts file for every language
	const locales = opts.locale === 'all' ? allLocales : [opts.locale];
	const textFields = TEXT_FIELDS[opts.type];
	const translatedLocales = textFields.length || opts.refs === 'full' ? locales.filter((l) => l !== 'enUS') : [];
	const wantedIds = parseIds(opts.ids);
	let records = new Map<number, Rec>();
	let buckets: number[] = [];

	// a few requests in parallel keeps it quick without flooding the server
	async function eachBucket(fn: (bucket: number) => Promise<void>) {
		const queue = [...buckets];
		const worker = async () => {
			for (let b = queue.shift(); b !== undefined; b = queue.shift()) await fn(b);
		};
		await Promise.all(Array.from({ length: 6 }, worker));
	}

	let done = 0;
	if (opts.type === 'questline') {
		for (const line of await getQuestlines(opts.flavor)) records.set(line.id, line as unknown as Rec);
		if (wantedIds) records = new Map([...records].filter(([id]) => wantedIds.has(id)));
		onProgress?.(1, 1);
	} else {
		const kind = opts.type;
		let ids = await allIds(opts.flavor, kind);
		if (wantedIds) ids = ids.filter((i) => wantedIds.has(i));
		const wanted = new Set(ids);
		buckets = [...new Set(ids.map((i) => Math.floor(i / BUCKET)))].sort((a, b) => a - b);
		const total = buckets.length * (1 + translatedLocales.length);
		onProgress?.(0, total);
		await eachBucket(async (b) => {
			const shard = await getShard<Rec>(opts.flavor, kind, b);
			for (const [id, rec] of Object.entries(shard)) if (wanted.has(Number(id))) records.set(Number(id), rec);
			onProgress?.(++done, total);
		});
	}
	if (opts.zone !== null) {
		records = new Map([...records].filter(([, r]) => zoneOf(r) === opts.zone));
	}

	async function localized(locale: string): Promise<Map<number, Rec>> {
		if (locale === 'enUS') return records;
		const kind = opts.type;
		const translations: Record<string, Rec> = {};
		if (kind !== 'questline') {
			const total = buckets.length * (1 + translatedLocales.length);
			await eachBucket(async (b) => {
				Object.assign(translations, await getShard<Rec>(opts.flavor, kind, b, locale));
				onProgress?.(++done, total);
			});
		}
		const [names, zones] = await Promise.all([getNames(opts.flavor, locale), getZoneNames(opts.flavor, locale)]);
		const table = (names ?? {}) as unknown as Record<string, Record<string, string>>;
		return new Map(
			[...records].map(([id, rec]) => [id, localizeRefs({ ...rec, ...(translations[id] ?? {}) }, table, zones) as Rec])
		);
	}

	const keep = opts.fields.length ? new Set(opts.fields) : null;
	function split(recs: Map<number, Rec>) {
		const data = new Map<number, Json>();
		const texts = new Map<number, Json>();
		for (const [id, rec] of recs) {
			const kept = Object.entries(rec).filter(([k]) => k !== 'id' && k !== 'azerothcore' && (!keep || keep.has(k)));
			const text = kept.filter(([k]) => textFields.includes(k));
			const rest: Rec = Object.fromEntries(kept.filter(([k]) => !textFields.includes(k)));
			if (opts.type === 'quest' && rest.rewards) rest.rewards = questRewardsFormat(rest.rewards as Rec, opts.refs);
			data.set(id, opts.refs === 'id' ? compactRefs(rest) : rest);
			if (text.length) {
				// field order as in TEXT_FIELDS, like the Python tool
				texts.set(id, Object.fromEntries(textFields.filter((f) => text.some(([k]) => k === f)).map((f) => [f, exportText(rec[f])])));
			}
		}
		return { data, texts };
	}

	const label = meta.flavors[opts.flavor]?.label ?? opts.flavor;
	const dataFile = `${opts.varName}.lua`;
	const files: ExportFile[] = [];
	for (const [n, locale] of locales.entries()) {
		const { data, texts } = split(await localized(locale));
		const textsFile = texts.size ? `${textVar}.${locale}.lua` : null;
		const hasData = [...data.values()].some((v) => v && typeof v === 'object' && Object.keys(v).length);
		if (n === 0 && (hasData || !texts.size)) {
			const lines = header(dataFile, `${opts.type} data for ${label}, exported from the WoW Quest Database.`, data.size, meta, opts);
			const reference = locales.length > 1 ? `${textVar}.<locale>.lua (one file per language)` : textsFile;
			if (textsFile) lines.splice(3, 0, `-- Texts (names, descriptions, ...) are in ${reference}, keyed by the same IDs.`);
			const body =
				opts.style === 'return'
					? ['return {', ...entries(data), '}', '']
					: ['local _, addon = ...', '', `addon.${opts.varName} = {`, ...entries(data), '}', ''];
			files.push({ fileName: dataFile, text: [...lines, ...body].join('\n'), count: data.size });
		}
		if (!textsFile) break; // no text fields selected: nothing per language
		const lines = header(textsFile, `${opts.type} texts (${locale}) for ${label}, keyed by ${opts.type} ID.`, texts.size, meta, opts);
		const table = `addon.${textVar}`;
		const body =
			opts.style === 'return'
				? ['return {', ...entries(texts), '}', '']
				: ['local _, addon = ...', '', `${table} = ${table} or {}`, `${table}[${luaString(locale)}] = {`, ...entries(texts), '}', ''];
		files.push({ fileName: textsFile, text: [...lines, ...body].join('\n'), count: texts.size });
	}
	return files;
}
