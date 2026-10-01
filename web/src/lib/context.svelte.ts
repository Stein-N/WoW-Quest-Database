// Site-wide state for the flavor being browsed: its zone table and, for a non-English
// content locale, the translated entity and zone names used by every link on the page.

import { getNames, getZoneNames, getZones, type NameTable } from './data';
import { settings } from './settings.svelte';
import type { Zones } from './types';

class Site {
	flavor = $state('classic');
	zones = $state<Zones | null>(null);
	names = $state<NameTable | null>(null);
	zoneNames = $state<Record<string, string>>({});

	#loaded = '';

	/** Loads flavor/locale dependent tables; cheap to call repeatedly. */
	async ensure(flavor: string) {
		const key = `${flavor}|${settings.locale}`;
		if (key === this.#loaded) return;
		this.#loaded = key;
		this.flavor = flavor;
		const [zones, names, zoneNames] = await Promise.all([
			getZones(flavor),
			getNames(flavor, settings.locale),
			getZoneNames(flavor, settings.locale)
		]);
		if (this.#loaded !== key) return;
		this.zones = zones;
		this.names = names;
		this.zoneNames = zoneNames;
	}

	zoneName(id: number | string | undefined): string {
		if (id === undefined) return '';
		const n = Number(id);
		if (n < 0) return this.zones?.sorts[n] ?? `Category ${n}`;
		return this.zoneNames[n] ?? this.zones?.zones[n]?.name ?? `Zone ${n}`;
	}
}

export const site = new Site();
