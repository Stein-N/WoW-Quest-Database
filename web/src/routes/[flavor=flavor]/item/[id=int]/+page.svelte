<script lang="ts">
	import { page } from '$app/state';
	import { useEntity } from '$lib/entity.svelte';
	import { QUALITY_NAMES } from '$lib/format';
	import EntityLink from '$lib/components/EntityLink.svelte';
	import Money from '$lib/components/Money.svelte';
	import RefList from '$lib/components/RefList.svelte';
	import type { Item } from '$lib/types';

	const flavor = $derived(page.params.flavor!);
	const id = $derived(Number(page.params.id));
	const entity = useEntity<Item>('item', () => ({ flavor, id }));
	const item = $derived(entity.value);
	const name = $derived(entity.tr?.name ?? item?.name);
	const description = $derived(entity.tr?.description ?? item?.description);

	const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
</script>

<svelte:head><title>{name ?? 'Item'} – WoW Quest Database</title></svelte:head>

{#if item === undefined}
	<p class="muted">Loading…</p>
{:else if item === null}
	<h1>Item {id} not found</h1>
{:else}
	{@const it = item}
	<h1 class="q{it.quality ?? 1}">{name}</h1>
	<div class="grid">
		<div>
			<div class="cols">
				<RefList title="Dropped by" refs={it.droppedBy} showChance limit={25} />
				<RefList title="Contained in object" refs={it.objectDrops} />
				<RefList title="Contained in item" refs={it.containedIn} />
				<RefList title="Sold by" refs={it.vendors} />
				<RefList title="Reward from" refs={it.rewardFrom} />
				<RefList title="Objective of" refs={it.objectiveOf} />
			</div>
		</div>
		<aside>
			<section class="panel tooltip">
				<div class="q{it.quality ?? 1} title">{name}</div>
				{#if it.bonding}<div>{it.bonding}</div>{/if}
				{#if it.unique}<div>Unique</div>{/if}
				{#if it.startsQuest}<div>This Item Begins a Quest: <EntityLink ref={it.startsQuest} /></div>{/if}
				{#if it.slot || it.subClass}
					<div class="split"><span>{it.slot ?? ''}</span><span>{it.subClass ?? ''}</span></div>
				{/if}
				{#if it.damage}
					<div class="split">
						<span>
							{#each it.damage as d, i (i)}
								<div>{i ? '+ ' : ''}{d.min} – {d.max} {d.school} Damage</div>
							{/each}
						</span>
						{#if it.speed}<span>Speed {it.speed.toFixed(2)}</span>{/if}
					</div>
					{#if it.speed}
						<div>
							({(it.damage.reduce((s, d) => s + (d.min + d.max) / 2, 0) / it.speed).toFixed(1)} damage per second)
						</div>
					{/if}
				{/if}
				{#if it.armor}<div>{it.armor} Armor</div>{/if}
				{#if it.block}<div>{it.block} Block</div>{/if}
				{#each it.stats ?? [] as s (s.stat)}
					<div>{s.value > 0 ? '+' : ''}{s.value} {s.stat}</div>
				{/each}
				{#each Object.entries(it.resistances ?? {}) as [school, v] (school)}
					<div>+{v} {cap(school)} Resistance</div>
				{/each}
				{#if it.slots}<div>{it.slots} Slot Bag</div>{/if}
				{#if it.durability}<div>Durability {it.durability} / {it.durability}</div>{/if}
				{#if it.classes}<div>Classes: {it.classes.join(', ')}</div>{/if}
				{#if it.races}<div>Races: {it.races.join(', ')}</div>{/if}
				{#if it.reqLevel}<div>Requires Level {it.reqLevel}</div>{/if}
				{#if it.reqSkill}<div>Requires {it.reqSkill.name} ({it.reqSkill.value})</div>{/if}
				{#if it.reqRep}<div>Requires {it.reqRep.name}</div>{/if}
				{#each it.spells ?? [] as sp (sp.id)}
					<div class="spell">{sp.trigger}: {sp.description || sp.name || `Spell #${sp.id}`}</div>
				{/each}
				{#if description}<div class="desc">"{description}"</div>{/if}
				{#if it.sellPrice}<div>Sell Price: <Money copper={it.sellPrice} /></div>{/if}
			</section>
			<section class="panel">
				<dl class="facts">
					{#if it.quality !== undefined && it.quality !== null}<dt>Quality</dt><dd class="q{it.quality}">{QUALITY_NAMES[it.quality]}</dd>{/if}
					{#if it.itemLevel}<dt>Item level</dt><dd>{it.itemLevel}</dd>{/if}
					{#if it.class}<dt>Type</dt><dd>{it.class}{it.subClass && it.subClass !== it.class ? ` / ${it.subClass}` : ''}</dd>{/if}
					{#if it.stack}<dt>Stack</dt><dd>{it.stack}</dd>{/if}
					{#if it.buyPrice}<dt>Buy price</dt><dd><Money copper={it.buyPrice} /></dd>{/if}
					<dt>ID</dt><dd>{it.id}</dd>
					<dt>Sources</dt><dd>{it.sources.map((s) => (({ questie: 'QuestieDB', vmangos: 'VMangos', cache: 'WoW client cache', wowhead: 'Wowhead' }) as Record<string, string>)[s] ?? s).join(', ')}</dd>
				</dl>
			</section>
		</aside>
	</div>
{/if}

<style>
	.tooltip {
		background: #0c0f1a;
		color: #fff;
		border-color: #5a6170;
		font-size: 0.92rem;
		line-height: 1.4;
		--q1: #fff;
		--q0: #9d9d9d;
		--q2: #1eff00;
		--q3: #2a8cff;
		--q4: #b45cff;
		--q5: #ff8000;
		--link: #ffd100;
		--accent: #ffd100;
		--gold: #ffd100;
		--silver: #c7c7cf;
		--copper: #d0834f;
	}
	.title {
		font-size: 1.05rem;
		font-weight: 600;
	}
	.split {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	.spell {
		color: #1eff00;
	}
	.desc {
		color: #ffd100;
	}
</style>
