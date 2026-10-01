export const QUALITY_NAMES = ['Poor', 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Artifact'];

export const FLAVOR_LABELS: Record<string, string> = {
	classic: 'Classic Era',
	forever: 'WoW Forever'
};

export const SIDE_LABELS: Record<string, string> = { A: 'Alliance', H: 'Horde', B: 'Both' };

export const CLASS_BITS: [number, string][] = [
	[1, 'Warrior'],
	[2, 'Paladin'],
	[4, 'Hunter'],
	[8, 'Rogue'],
	[16, 'Priest'],
	[64, 'Shaman'],
	[128, 'Mage'],
	[256, 'Warlock'],
	[1024, 'Druid']
];

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

/**
 * Quest text with the client's placeholders resolved:
 * $N name, $C class, $R race, $G male:female; and $B line breaks.
 */
export function questText(text: string | undefined | null): string {
	if (!text) return '';
	return escapeHtml(text)
		.replace(/\$[Gg]\s*([^:;]*):([^;]*);/g, '<span class="ph">$1/$2</span>')
		.replace(/\$[Nn]/g, '<span class="ph">&lt;name&gt;</span>')
		.replace(/\$[Cc]/g, '<span class="ph">&lt;class&gt;</span>')
		.replace(/\$[Rr]/g, '<span class="ph">&lt;race&gt;</span>')
		.replace(/\$[Bb]/g, '<br>');
}

export function money(copper: number): { g: number; s: number; c: number } {
	return {
		g: Math.floor(copper / 10000),
		s: Math.floor((copper % 10000) / 100),
		c: copper % 100
	};
}

export function duration(seconds: number): string {
	const m = Math.floor(seconds / 60);
	const s = seconds % 60;
	return m ? `${m} min${s ? ` ${s} s` : ''}` : `${s} s`;
}

export function levelRange(min?: number | null, max?: number | null): string {
	if (!min && !max) return '?';
	return !max || min === max ? String(min ?? max) : `${min}–${max}`;
}

export function chance(value?: number): string {
	if (value === undefined || value === null) return '';
	return value >= 1 ? `${Math.round(value * 10) / 10}%` : `${Math.round(value * 100) / 100}%`;
}

/** Normalises for accent- and case-insensitive search. */
export function fold(s: string): string {
	return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}
