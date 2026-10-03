// Shapes of the JSON written by etl/build.py.

export type Kind = 'quest' | 'npc' | 'object' | 'item';

export interface Ref {
	t: Kind;
	id: number;
	name: string;
	/** item quality */
	q?: number;
	/** quest level */
	lvl?: number;
	chance?: number;
	count?: number;
	min?: number;
	max?: number;
	vendor?: boolean;
	/** vendor entry known only from VMangos (may be outdated) */
	vmangos?: boolean;
	/** limited vendor stock: at most this many, refilled every `restock` seconds */
	limit?: number;
	restock?: number;
	/** offered only under a condition (e.g. reputation) */
	conditional?: boolean;
	/** referenced entity is absent from this flavor's data */
	missing?: boolean;
}

export type Point = [number, number];
/** areaId -> points (percent coordinates on that area's map) */
export type SpawnMap = Record<string, Point[]>;
/** areaId -> list of paths */
export type WaypointMap = Record<string, Point[][]>;

export interface SpawnData {
	spawns?: SpawnMap;
	waypoints?: WaypointMap;
}

export interface Faction {
	id: number;
	name: string;
	value?: number;
}

export interface ZoneRef {
	zone?: number;
	sort?: number;
	name: string;
}

export interface Objective {
	kind: 'kill' | 'object' | 'item' | 'reputation' | 'killcredit' | 'spell' | 'event' | 'extra';
	target?: Ref;
	targets?: Ref[];
	text?: string;
	count?: number;
	sources?: Ref[];
	faction?: Faction;
	spell?: { id: number; name: string | null };
	spawnKey?: string;
}

export interface Quest {
	id: number;
	name: string;
	level?: number;
	reqLevel?: number;
	maxLevel?: number;
	side: 'A' | 'H' | 'B';
	races?: string[];
	classes?: string[];
	zone?: ZoneRef;
	/** UiMapId of the quest's zone (WoW map API); missing for categories */
	uiMapId?: number;
	type?: string;
	suggestedPlayers?: number;
	timeLimit?: number;
	repeatable?: boolean;
	objectivesText?: string[];
	details?: string;
	progress?: string;
	completion?: string;
	endText?: string;
	/** who starts the quest (NPCs, objects, items) — QuestieDB's startedBy */
	startedBy: Ref[];
	/** who the quest is turned in to (NPCs, objects) — QuestieDB's finishedBy */
	finishedBy: Ref[];
	objectives: Objective[];
	providedItem?: Ref;
	requiredItems?: Ref[];
	chain?: {
		prev?: Ref[];
		next?: Ref;
		preSingle?: Ref[];
		preGroup?: Ref[];
		children?: Ref[];
		parent?: Ref;
		groupWith?: Ref[];
		exclusive?: Ref[];
		breadcrumbs?: Ref[];
		breadcrumbFor?: Ref;
	};
	requirements?: {
		skill?: { id: number; name: string; value?: number };
		minRep?: Faction;
		maxRep?: Faction;
		spell?: { id: number; name: string | null; lacking: boolean };
		money?: number;
	};
	rewards?: {
		items?: { kind: 'fixed' | 'choice'; items: Ref[] }[];
		xp?: number;
		money?: number;
		moneyMaxLevel?: number;
		spell?: { id: number; name: string | null; description: string | null };
		reputation?: Faction[];
	};
	spawns?: Record<string, SpawnData>;
	questline?: { id: number; size: number };
	sources: string[];
}

export interface Npc extends SpawnData {
	id: number;
	name: string;
	subName?: string;
	minLevel?: number;
	maxLevel?: number;
	minHealth?: number;
	maxHealth?: number;
	rank?: string;
	react?: string;
	faction?: Faction;
	roles?: string[];
	zone?: ZoneRef;
	starts?: Ref[];
	ends?: Ref[];
	objectiveOf?: Ref[];
	sells?: Ref[];
	loot?: Ref[];
	sources: string[];
}

export interface GameObject extends SpawnData {
	id: number;
	name: string;
	zone?: ZoneRef;
	starts?: Ref[];
	ends?: Ref[];
	objectiveOf?: Ref[];
	contains?: Ref[];
}

export interface Item {
	id: number;
	name: string;
	/** positions of vendors, droppers and objects for the map, keyed "npc:ID" / "object:ID" */
	spawns?: Record<string, SpawnData>;
	quality?: number | null;
	itemLevel?: number;
	reqLevel?: number;
	class?: string;
	subClass?: string;
	slot?: string;
	bonding?: string;
	unique?: boolean;
	stack?: number;
	slots?: number;
	armor?: number;
	block?: number;
	durability?: number;
	sellPrice?: number;
	buyPrice?: number;
	description?: string;
	classes?: string[];
	races?: string[];
	reqSkill?: { id: number; name: string; value: number };
	reqRep?: Faction;
	stats?: { stat: string; value: number }[];
	damage?: { min: number; max: number; school: string }[];
	speed?: number;
	resistances?: Record<string, number>;
	spells?: { id: number; trigger: string; name: string | null; description: string | null }[];
	startsQuest?: Ref;
	droppedBy?: Ref[];
	objectDrops?: Ref[];
	containedIn?: Ref[];
	vendors?: Ref[];
	rewardFrom?: Ref[];
	objectiveOf?: Ref[];
	sources: string[];
}

export interface Zone {
	name: string;
	uiMapId?: number;
	parent?: number;
	instance?: boolean;
	/** kind of instance for the zone list (also on the outdoor quest zone of some instances, e.g. Gnomeregan); absent for e.g. Deeprun Tram */
	instanceType?: 'dungeon' | 'raid' | 'battleground';
	entrances?: { zone: number; x: number; y: number }[];
}

export interface Zones {
	zones: Record<string, Zone>;
	sorts: Record<string, string>;
	/** quest category -> group in the zone list */
	sortGroups?: Record<string, 'class' | 'profession' | 'event' | 'other'>;
}

export interface ChangelogEntry {
	version: string;
	date: string;
	/** notes on the website (hand-written) */
	website?: string[];
	/** notes on the data (hand-written) */
	dataNotes?: string[];
	/** data changes compared with the previous release, in plain words, per flavor */
	dataChanges?: Record<string, string[]>;
	/** commit subjects */
	commits?: string[];
	data?: {
		questie: { commit: string; date: string; subject: string };
		vmangos: { snapshot: string; published: string };
	};
}

export interface Meta {
	built: string;
	questie: string | null;
	vmangos: string | null;
	locales: string[];
	flavors: Record<string, { label: string; counts: Record<Kind, number> }>;
}

/** [id, name, level, reqLevel, side, zoneOrSort, classMask, flags] */
export type QuestIndexRow = [number, string, number | null, number | null, 'A' | 'H' | 'B', number, number, number];

export interface SearchIndex {
	/** [id, name, subName, minLevel, maxLevel, react, zone, rank, npcFlags] */
	npc: [number, string, string, number | null, number | null, string, number, string, number][];
	/** [id, name, zone] */
	object: [number, string, number][];
	/** [id, name, quality, itemLevel, reqLevel, class, subClass, slot] */
	item: [number, string, number | null, number | null, number | null, string, string, string][];
}

export interface L10nEntry {
	name?: string;
	subName?: string;
	objectivesText?: string[];
	details?: string;
	progress?: string;
	completion?: string;
	endText?: string;
	description?: string;
	/** fields taken from AzerothCore (WotLK 3.3.5), which may differ from Classic */
	azerothcore?: string[];
}

export interface Questline {
	id: number;
	/** first quest of the line; its (localized) name names the questline */
	root: number;
	zone: number;
	levels: [number, number] | null;
	side: 'A' | 'H' | 'B';
	quests: number[];
	/** [from, to, kind]: 'pre' = from before to, 'breadcrumb' = from leads to to */
	edges: [number, number, string][];
	exclusive?: [number, number][];
}
