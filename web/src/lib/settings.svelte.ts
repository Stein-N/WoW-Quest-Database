// Per-viewer preferences, remembered in localStorage.

export const LOCALES: Record<string, string> = {
	enUS: 'English',
	deDE: 'Deutsch',
	frFR: 'Français',
	esES: 'Español (EU)',
	esMX: 'Español (AL)',
	itIT: 'Italiano',
	ptBR: 'Português',
	ruRU: 'Русский',
	koKR: '한국어',
	zhCN: '简体中文',
	zhTW: '繁體中文'
};

function read(key: string, fallback: string): string {
	try {
		return localStorage.getItem(key) ?? fallback;
	} catch {
		return fallback;
	}
}

function write(key: string, value: string) {
	try {
		localStorage.setItem(key, value);
	} catch {
		// private mode etc. — the setting simply isn't remembered
	}
}

class Settings {
	#locale = $state(read('locale', 'enUS'));
	#mapFog = $state(read('mapFog', '0') === '1');

	/** Show maps unexplored (base art only) instead of fully revealed. */
	get mapFog() {
		return this.#mapFog;
	}
	set mapFog(value: boolean) {
		this.#mapFog = value;
		write('mapFog', value ? '1' : '0');
	}

	get locale() {
		return this.#locale;
	}
	set locale(value: string) {
		this.#locale = value in LOCALES ? value : 'enUS';
		write('locale', this.#locale);
	}
}

export const settings = new Settings();
