// Per-viewer preferences, remembered in localStorage.

export const LOCALES: Record<string, string> = {
	enUS: 'English',
	deDE: 'Deutsch',
	frFR: 'Français',
	esES: 'Español (EU)',
	esMX: 'Español (AL)',
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

	get locale() {
		return this.#locale;
	}
	set locale(value: string) {
		this.#locale = value in LOCALES ? value : 'enUS';
		write('locale', this.#locale);
	}
}

export const settings = new Settings();
