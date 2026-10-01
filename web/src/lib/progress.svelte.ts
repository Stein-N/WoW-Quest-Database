// Quests the viewer ticked off in questline views, per flavor, remembered in localStorage.

class Progress {
	// Plain cache (filled lazily while rendering); `version` makes readers reactive.
	#done = new Map<string, Set<number>>();
	#version = $state(0);

	#load(flavor: string): Set<number> {
		let set = this.#done.get(flavor);
		if (!set) {
			let ids: number[] = [];
			try {
				ids = JSON.parse(localStorage.getItem(`done:${flavor}`) ?? '[]');
			} catch {
				ids = [];
			}
			set = new Set(ids);
			this.#done.set(flavor, set);
		}
		return set;
	}

	isDone(flavor: string, id: number): boolean {
		void this.#version;
		return this.#load(flavor).has(id);
	}

	toggle(flavor: string, id: number) {
		const set = this.#load(flavor);
		if (set.has(id)) set.delete(id);
		else set.add(id);
		this.#version++;
		try {
			localStorage.setItem(`done:${flavor}`, JSON.stringify([...set]));
		} catch {
			// not remembered in private mode
		}
	}
}

export const progress = new Progress();
