<script lang="ts" module>
	import type { SpawnData } from '$lib/types';

	export interface MapEntry {
		name: string;
		href?: string;
		data: SpawnData;
	}

	export interface MapLayer {
		label: string;
		color: string;
		/** '!' / '?' draw quest-giver style glyph markers instead of dots */
		glyph?: string;
		entries: MapEntry[];
	}

	export interface MapIndex {
		maps: number[];
		/** instance uiMapId -> its floors (plain images, no coordinates inside instances) */
		instances?: Record<string, { uiMapId: number; name: string }[]>;
	}

	const indexes = new Map<string, Promise<MapIndex>>();

	/** maps/<flavor>/index.json from etl/maps.py; empty when no map art was extracted. */
	export function loadMapIndex(flavor: string): Promise<MapIndex> {
		let p = indexes.get(flavor);
		if (!p) {
			p = fetch(`maps/${flavor}/index.json`)
				.then((r) => (r.ok ? r.json() : { maps: [] }))
				.catch(() => ({ maps: [] }));
			indexes.set(flavor, p);
		}
		return p;
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { site } from '$lib/context.svelte';
	import { settings } from '$lib/settings.svelte';
	import { param, syncUrl, urlParams } from '$lib/url-state';
	import type * as Leaflet from 'leaflet';
	import 'leaflet/dist/leaflet.css';

	/** floors: instance maps (plain images, no markers) shown as the first tabs */
	let { layers, floors = [] }: { layers: MapLayer[]; floors?: { uiMapId: number; name: string }[] } = $props();

	// World map art is 1002×668; QuestieDB coordinates are percentages of it.
	const W = 1002;
	const H = 668;

	interface Marker {
		layer: number;
		name: string;
		href?: string;
		x: number;
		y: number;
		note?: string;
	}
	interface Path {
		layer: number;
		points: [number, number][];
	}
	interface MapGroup {
		uiMapId: number;
		name: string;
		floor?: boolean;
		markers: Marker[];
		paths: Path[];
	}

	let mapIndex = $state<MapIndex>({ maps: [] });
	$effect(() => {
		const flavor = site.flavor;
		loadMapIndex(flavor).then((index) => {
			if (site.flavor === flavor) mapIndex = index;
		});
	});
	const withArt = $derived(new Set(mapIndex.maps));

	const groups = $derived.by(() => {
		const zones = site.zones?.zones ?? {};
		const byMap = new Map<number, MapGroup>();
		const group = (uiMapId: number, areaId: number) => {
			let g = byMap.get(uiMapId);
			if (!g) {
				g = { uiMapId, name: site.zoneName(areaId), markers: [], paths: [] };
				byMap.set(uiMapId, g);
			}
			return g;
		};
		// Instances without map art are shown at their entrance on the outdoor map.
		const atEntrance = (zone: (typeof zones)[string] | undefined) =>
			!!zone?.instance && !!zone.entrances?.length && !(zone.uiMapId && withArt.has(zone.uiMapId));
		layers.forEach((layer, li) => {
			for (const entry of layer.entries) {
				for (const [area, points] of Object.entries(entry.data.spawns ?? {})) {
					const zone = zones[area];
					if (atEntrance(zone)) {
						for (const e of zone!.entrances!) {
							const outer = zones[e.zone];
							if (!outer?.uiMapId) continue;
							const g = group(outer.uiMapId, e.zone);
							if (!g.markers.some((m) => m.layer === li && m.name === entry.name && m.note)) {
								g.markers.push({
									layer: li,
									name: entry.name,
									href: entry.href,
									x: e.x,
									y: e.y,
									note: `inside ${zone!.name}`
								});
							}
						}
					} else if (zone?.uiMapId) {
						const g = group(zone.uiMapId, Number(area));
						for (const [x, y] of points) {
							if (x >= 0 && y >= 0) g.markers.push({ layer: li, name: entry.name, href: entry.href, x, y });
						}
					}
				}
				for (const [area, paths] of Object.entries(entry.data.waypoints ?? {})) {
					const zone = zones[area];
					if (!zone?.uiMapId || atEntrance(zone)) continue;
					const g = group(zone.uiMapId, Number(area));
					for (const p of paths) g.paths.push({ layer: li, points: p as [number, number][] });
				}
			}
		});
		// Maps showing a glyph (quest giver / turn-in) come first, then by marker count.
		const glyphs = (g: MapGroup) => g.markers.filter((m) => layers[m.layer].glyph).length;
		const floorGroups: MapGroup[] = floors.map((f) => ({ ...f, floor: true, markers: [], paths: [] }));
		return [
			...floorGroups,
			...[...byMap.values()].sort(
				(a, b) => Number(glyphs(b) > 0) - Number(glyphs(a) > 0) || b.markers.length - a.markers.length
			)
		];
	});

	// The chosen map tab is kept in the URL (?map=<uiMapId>), so coming back shows the same map.
	let selected = $state<number | null>(param.num(urlParams(), 'map'));
	$effect(() => {
		syncUrl({ map: selected });
	});
	let hidden = $state<Record<number, boolean>>({});
	const current = $derived(groups.find((g) => g.uiMapId === selected) ?? groups[0]);

	let container: HTMLDivElement | undefined = $state();
	let L: typeof Leaflet | undefined = $state();
	let map: Leaflet.Map | undefined;
	let overlay: Leaflet.LayerGroup | undefined;

	onMount(() => {
		let disposed = false;
		import('leaflet').then((mod) => {
			if (disposed || !container) return;
			L = mod.default ?? mod;
			map = L.map(container, {
				crs: L.CRS.Simple,
				minZoom: -1,
				maxZoom: 3,
				zoomSnap: 0.25,
				attributionControl: false,
				maxBounds: [
					[-H - 100, -100],
					[100, W + 100]
				]
			});
			map.fitBounds([
				[-H, 0],
				[0, W]
			]);
			overlay = L.layerGroup().addTo(map);
		});
		return () => {
			disposed = true;
			map?.remove();
		};
	});

	const toLatLng = (x: number, y: number): [number, number] => [(-y / 100) * H, (x / 100) * W];

	const cssVar = (name: string) =>
		container ? getComputedStyle(container).getPropertyValue(name).trim() || '#888' : '#888';

	function drawGrid(target: Leaflet.LayerGroup) {
		if (!L) return;
		const style = { color: cssVar('--grid'), weight: 1, interactive: false };
		for (let i = 0; i <= 10; i++) {
			L.polyline([toLatLng(i * 10, 0), toLatLng(i * 10, 100)], style).addTo(target);
			L.polyline([toLatLng(0, i * 10), toLatLng(100, i * 10)], style).addTo(target);
		}
	}

	$effect(() => {
		const g = current;
		const hiddenNow = { ...hidden };
		if (!L || !map || !overlay) return;
		const Lx = L;
		const target = overlay;
		target.clearLayers();
		if (!g) return;
		const bounds: Leaflet.LatLngBoundsExpression = [
			[-H, 0],
			[0, W]
		];
		if (g.floor) {
			Lx.imageOverlay(`maps/${site.flavor}/${g.uiMapId}.webp`, bounds, { interactive: false }).addTo(target).bringToBack();
		} else if (withArt.has(g.uiMapId)) {
			const file = `maps/${site.flavor}/${g.uiMapId}${settings.mapFog ? '-fog' : ''}.webp`;
			Lx.imageOverlay(file, bounds, { interactive: false }).addTo(target).bringToBack();
		} else {
			drawGrid(target);
		}
		Lx.rectangle(bounds, { color: cssVar('--border'), weight: 1, fill: false, interactive: false }).addTo(target);

		for (const p of g.paths) {
			if (hiddenNow[p.layer]) continue;
			Lx.polyline(
				p.points.map(([x, y]) => toLatLng(x, y)),
				{ color: layers[p.layer].color, weight: 2, opacity: 0.6, dashArray: '4 4' }
			).addTo(target);
		}
		for (const m of g.markers) {
			if (hiddenNow[m.layer]) continue;
			const layer = layers[m.layer];
			const pos = toLatLng(m.x, m.y);
			const marker = layer.glyph
				? Lx.marker(pos, {
						icon: Lx.divIcon({
							className: 'glyph-marker',
							html: `<span style="--c:${layer.color}">${layer.glyph}</span>`,
							iconSize: [18, 22],
							iconAnchor: [9, 11]
						}),
						zIndexOffset: 1000
					})
				: Lx.circleMarker(pos, {
						radius: 4,
						color: '#000',
						weight: 1,
						fillColor: layer.color,
						fillOpacity: 0.9
					});
			const label = `${m.name}${m.note ? ` (${m.note})` : ''} — ${m.x.toFixed(1)}, ${m.y.toFixed(1)}`;
			marker.bindTooltip(label.replace(/</g, '&lt;'), { direction: 'top' });
			if (m.href) marker.on('click', () => (window.location.hash = m.href!.replace(/^#/, '')));
			marker.addTo(target);
		}
	});
</script>

{#if groups.length}
	<div class="zonemap">
		{#if groups.length > 1}
			<div class="tabs" role="tablist">
				{#each groups as g (g.uiMapId)}
					<button
						role="tab"
						aria-selected={g === current}
						class:active={g === current}
						onclick={() => (selected = g.uiMapId)}
					>
						{g.name}{#if !g.floor}{' '}<span class="count">{g.markers.length}</span>{/if}
					</button>
				{/each}
			</div>
		{:else}
			<h3 class="mapname">{current?.name}</h3>
		{/if}
		<div class="mapbox" bind:this={container}></div>
		<div class="legend">
			{#each layers as layer, i (i)}
				{#if layer.entries.length}
					<label>
						<input
							type="checkbox"
							checked={!hidden[i]}
							onchange={(e) => (hidden = { ...hidden, [i]: !e.currentTarget.checked })}
						/>
						<span class="swatch" style="background:{layer.color}">{layer.glyph ?? ''}</span>
						{layer.label}
					</label>
				{/if}
			{/each}
			{#if current && !current.floor && withArt.has(current.uiMapId)}
				<label class="fog">
					<input type="checkbox" bind:checked={settings.mapFog} />
					Fog of war
				</label>
			{/if}
		</div>
	</div>
{/if}

<style>
	.zonemap {
		margin: 0.5rem 0 1rem;
	}
	.mapbox {
		width: 100%;
		aspect-ratio: 1002 / 668;
		background: var(--map-bg);
		border: 1px solid var(--border);
		border-radius: 6px;
	}
	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-bottom: 0.4rem;
	}
	.tabs button {
		background: var(--panel);
		border: 1px solid var(--border);
		color: var(--text);
		padding: 0.25rem 0.6rem;
		border-radius: 4px;
		cursor: pointer;
		font: inherit;
		font-size: 0.85rem;
	}
	.tabs button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.mapname {
		margin: 0 0 0.4rem;
		font-size: 1rem;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1rem;
		margin-top: 0.4rem;
		font-size: 0.85rem;
	}
	.legend .fog {
		margin-left: auto;
		color: var(--muted);
	}
	.legend label {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		cursor: pointer;
	}
	.swatch {
		display: inline-grid;
		place-items: center;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		font-size: 10px;
		font-weight: 700;
		color: #000;
	}
	:global(.glyph-marker span) {
		display: grid;
		place-items: center;
		width: 18px;
		height: 22px;
		font: 900 20px/1 Georgia, serif;
		color: var(--c);
		text-shadow:
			0 0 2px #000,
			0 0 2px #000,
			0 0 3px #000;
	}
	:global(.leaflet-container) {
		background: var(--map-bg);
		font: inherit;
	}
</style>
