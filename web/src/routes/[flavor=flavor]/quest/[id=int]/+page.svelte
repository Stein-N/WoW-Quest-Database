<script lang="ts">
	import { page } from '$app/state';
	import { useEntity } from '$lib/entity.svelte';
	import { site } from '$lib/context.svelte';
	import { questText, duration, chance, SIDE_LABELS } from '$lib/format';
	import EntityLink from '$lib/components/EntityLink.svelte';
	import Money from '$lib/components/Money.svelte';
	import ZoneMap, { type MapLayer } from '$lib/components/ZoneMap.svelte';
	import type { Objective, Quest, Ref } from '$lib/types';

	const flavor = $derived(page.params.flavor!);
	const id = $derived(Number(page.params.id));

	const entity = useEntity<Quest>('quest', () => ({ flavor, id }));
	const quest = $derived(entity.value);
	const tr = $derived(entity.tr);

	const COLORS = ['#e8524a', '#4aa3e8', '#9be84a', '#e84ad8', '#4ae8c9', '#e8a14a', '#a44ae8', '#e8e24a'];

	function objectiveLabel(o: Objective): string {
		const name = (r?: Ref) => (r ? (site.names?.[r.t]?.[r.id] ?? r.name) : '');
		switch (o.kind) {
			case 'kill':
				return o.text || `${name(o.target)} slain`;
			case 'item':
			case 'object':
				return o.text || name(o.target);
			case 'killcredit':
				return o.text || name(o.target) || 'Kill credit';
			case 'event':
			case 'extra':
				return o.text ?? 'Objective';
			case 'reputation':
				return `Reach ${o.faction?.value} reputation with ${o.faction?.name}`;
			case 'spell':
				return o.text || `Cast ${o.spell?.name ?? o.spell?.id}`;
		}
	}

	const layers = $derived.by((): MapLayer[] => {
		if (!quest) return [];
		const q = quest;
		const spawns = q.spawns ?? {};
		const entries = (refs: Ref[]) =>
			refs
				.filter((r) => spawns[`${r.t}:${r.id}`])
				.map((r) => ({
					name: site.names?.[r.t]?.[r.id] ?? r.name,
					href: `#/${flavor}/${r.t}/${r.id}`,
					data: spawns[`${r.t}:${r.id}`]
				}));
		const out: MapLayer[] = [];
		q.objectives.forEach((o, i) => {
			const refs: Ref[] = [];
			if (o.target && o.kind !== 'item') refs.push(o.target);
			if (o.targets) refs.push(...o.targets.filter((t) => t.t !== 'item'));
			if (o.sources) refs.push(...o.sources.filter((s) => s.t !== 'item'));
			const layer: MapLayer = {
				label: objectiveLabel(o),
				color: COLORS[i % COLORS.length],
				entries: entries(refs)
			};
			if (o.spawnKey && spawns[o.spawnKey]) {
				layer.entries.push({ name: objectiveLabel(o), data: spawns[o.spawnKey] });
			}
			out.push(layer);
		});
		out.push({ label: 'Quest giver', color: '#ffd100', glyph: '!', entries: entries(q.startedBy) });
		out.push({ label: 'Turn in', color: '#ffd100', glyph: '?', entries: entries(q.finishedBy) });
		return out;
	});

	const name = $derived(tr?.name ?? quest?.name);
	const objectivesText = $derived(tr?.objectivesText ?? quest?.objectivesText);
</script>

<svelte:head><title>{name ?? 'Quest'} – WoW Quest Database</title></svelte:head>

{#if quest === undefined}
	<p class="muted">Loading…</p>
{:else if quest === null}
	<h1>Quest {id} not found</h1>
	<p class="muted">This quest does not exist in the {flavor} data.</p>
{:else}
	{@const q = quest}
	<h1>{name}</h1>
	<p class="subtitle">
		{#if q.level}<span class="badge">Level {q.level}</span>{/if}
		{#if q.type}<span class="badge">{q.type}</span>{/if}
		{#if q.repeatable}<span class="badge">Repeatable</span>{/if}
		{#if q.side !== 'B'}<span class="badge side-{q.side}">{SIDE_LABELS[q.side]}</span>{/if}
		{#if q.zone}
			<a href="#/{flavor}/zone/{q.zone.zone ?? q.zone.sort}">{site.zoneName(q.zone.zone ?? q.zone.sort)}</a>
		{/if}
	</p>

	<div class="grid">
		<div>
			{#if objectivesText?.length}
				<section class="panel">
					<h3>Objectives</h3>
					{#each objectivesText as line, i (i)}
						<p class="text">{@html questText(line)}</p>
					{/each}
					{#if q.objectives.length}
						<ul class="objectives">
							{#each q.objectives as o, i (i)}
								<li>
									<span class="dot" style="background:{COLORS[i % COLORS.length]}"></span>
									{#if o.target && (o.kind === 'kill' || o.kind === 'item' || o.kind === 'object' || o.kind === 'killcredit')}
										<EntityLink ref={o.target} />
										{#if o.kind === 'kill' || o.kind === 'killcredit'}<span class="muted">slain</span>{/if}
									{:else}
										{objectiveLabel(o)}
									{/if}
									{#if o.count && o.count > 1}<span class="muted">×{o.count}</span>{/if}
									{#if o.kind === 'killcredit' && o.targets && o.targets.length > 1}
										<div class="sub">
											Counts:
											{#each o.targets as t, j (t.id)}{#if j}{', '}{/if}<EntityLink ref={t} />{/each}
										</div>
									{/if}
									{#if o.sources?.length}
										<div class="sub">
											{#each o.sources as s, j (`${s.t}:${s.id}`)}{#if j}{', '}{/if}<EntityLink
													ref={s}
												/>{#if s.chance}<span class="chance">{chance(s.chance)}</span>{/if}{#if s.vendor}<span
														class="muted"> (vendor)</span
													>{/if}{/each}
										</div>
									{/if}
								</li>
							{/each}
						</ul>
					{/if}
					{#if q.providedItem}
						<p class="muted">Provided item: <EntityLink ref={q.providedItem} /></p>
					{/if}
					{#if q.requiredItems?.length}
						<p class="muted">
							Required items:
							{#each q.requiredItems as r, j (r.id)}{#if j}{', '}{/if}<EntityLink ref={r} />{/each}
						</p>
					{/if}
				</section>
			{/if}

			{#if layers.some((l) => l.entries.length)}
				<section class="panel">
					<h3>Map</h3>
					{#key `${flavor}:${id}`}
						<ZoneMap {layers} />
					{/key}
				</section>
			{/if}

			{#if tr?.details ?? q.details}
				<section class="panel">
					<h3>Description</h3>
					<p class="text">{@html questText(tr?.details ?? q.details)}</p>
				</section>
			{/if}
			{#if tr?.progress ?? q.progress}
				<section class="panel">
					<h3>Progress</h3>
					<p class="text">{@html questText(tr?.progress ?? q.progress)}</p>
				</section>
			{/if}
			{#if tr?.completion ?? q.completion}
				<section class="panel">
					<h3>Completion</h3>
					<p class="text">{@html questText(tr?.completion ?? q.completion)}</p>
				</section>
			{/if}

			{#if q.rewards}
				{@const r = q.rewards}
				<section class="panel">
					<h3>Rewards</h3>
					{#each r.items ?? [] as group (group.kind)}
						<p class="muted">
							{group.kind === 'choice' ? 'You will be able to choose one of these rewards:' : 'You will receive:'}
						</p>
						<ul class="rewards">
							{#each group.items as item (item.id)}
								<li>
									<EntityLink ref={item} />{#if item.count && item.count > 1}<span class="muted">
											×{item.count}</span
										>{/if}
								</li>
							{/each}
						</ul>
					{/each}
					<dl class="facts">
						{#if r.money}<dt>Money</dt><dd><Money copper={r.money} /></dd>{/if}
						{#if r.xp}<dt>Experience</dt><dd>{r.xp.toLocaleString('en')} XP</dd>{/if}
						{#if r.moneyMaxLevel}<dt>At max level</dt><dd><Money copper={r.moneyMaxLevel} /></dd>{/if}
						{#if r.spell}
							<dt>Spell</dt>
							<dd>{r.spell.name ?? `#${r.spell.id}`}{#if r.spell.description}<div class="muted">{r.spell.description}</div>{/if}</dd>
						{/if}
						{#if r.reputation?.length}
							<dt>Reputation</dt>
							<dd>
								{#each r.reputation as rep (rep.id)}
									<div>{(rep.value ?? 0) > 0 ? '+' : ''}{rep.value} {rep.name}</div>
								{/each}
							</dd>
						{/if}
					</dl>
				</section>
			{/if}
		</div>

		<aside>
			<section class="panel">
				<h3>Quick facts</h3>
				<dl class="facts">
					{#if q.level}<dt>Level</dt><dd>{q.level}</dd>{/if}
					{#if q.reqLevel}<dt>Requires level</dt><dd>{q.reqLevel}{#if q.maxLevel} – {q.maxLevel}{/if}</dd>{/if}
					<dt>Side</dt><dd class="side-{q.side}">{SIDE_LABELS[q.side]}</dd>
					{#if q.races}<dt>Races</dt><dd>{q.races.join(', ')}</dd>{/if}
					{#if q.classes}<dt>Classes</dt><dd>{q.classes.join(', ')}</dd>{/if}
					{#if q.startedBy.length}
						<dt>Start</dt>
						<dd>{#each q.startedBy as s (`${s.t}:${s.id}`)}<div><EntityLink ref={s} /></div>{/each}</dd>
					{/if}
					{#if q.finishedBy.length}
						<dt>End</dt>
						<dd>{#each q.finishedBy as s (`${s.t}:${s.id}`)}<div><EntityLink ref={s} /></div>{/each}</dd>
					{/if}
					{#if q.suggestedPlayers}<dt>Group size</dt><dd>{q.suggestedPlayers}</dd>{/if}
					{#if q.timeLimit}<dt>Time limit</dt><dd>{duration(q.timeLimit)}</dd>{/if}
					{#if q.requirements?.skill}
						<dt>Skill</dt><dd>{q.requirements.skill.name} ({q.requirements.skill.value})</dd>
					{/if}
					{#if q.requirements?.minRep}
						<dt>Reputation</dt><dd>{q.requirements.minRep.name} ≥ {q.requirements.minRep.value}</dd>
					{/if}
					{#if q.requirements?.maxRep}
						<dt>Reputation</dt><dd>{q.requirements.maxRep.name} &lt; {q.requirements.maxRep.value}</dd>
					{/if}
					{#if q.requirements?.spell}
						<dt>Spell</dt><dd>{q.requirements.spell.lacking ? 'Must not know' : 'Must know'} {q.requirements.spell.name ?? q.requirements.spell.id}</dd>
					{/if}
					{#if q.requirements?.money}<dt>Costs</dt><dd><Money copper={q.requirements.money} /></dd>{/if}
					<dt>ID</dt><dd>{q.id}</dd>
					{#if q.uiMapId}<dt>UiMapId</dt><dd>{q.uiMapId}</dd>{/if}
					<dt>Sources</dt><dd>{q.sources.map((s) => (({ questie: 'QuestieDB', vmangos: 'VMangos', cache: 'WoW client cache' }) as Record<string, string>)[s] ?? s).join(', ')}</dd>
				</dl>
			</section>

			{#if q.questline}
				<a class="panel questline-card" href="#/{flavor}/questline/{q.questline.id}/{q.id}">
					<span class="ql-title">Show questline</span>
					<span class="muted">{q.questline.size} quests · opens the full chain with this quest highlighted</span>
				</a>
			{/if}

			{#if q.chain}
				{@const c = q.chain}
				<section class="panel">
					<h3>Quest chain</h3>
					<dl class="facts chain">
						{#if c.prev}<dt>Previous</dt><dd>{#each c.prev as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.preSingle}<dt>Requires one of</dt><dd>{#each c.preSingle as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.preGroup}<dt>Requires all of</dt><dd>{#each c.preGroup as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.next}<dt>Next</dt><dd><EntityLink ref={c.next} showLevel /></dd>{/if}
						{#if c.parent}<dt>Part of</dt><dd><EntityLink ref={c.parent} showLevel /></dd>{/if}
						{#if c.children}<dt>Sub-quests</dt><dd>{#each c.children as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.breadcrumbFor}<dt>Leads to</dt><dd><EntityLink ref={c.breadcrumbFor} showLevel /></dd>{/if}
						{#if c.breadcrumbs}<dt>Breadcrumbs</dt><dd>{#each c.breadcrumbs as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.groupWith}<dt>Shares a group with</dt><dd>{#each c.groupWith as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
						{#if c.exclusive}<dt>Excludes</dt><dd>{#each c.exclusive as r (r.id)}<div><EntityLink ref={r} showLevel /></div>{/each}</dd>{/if}
					</dl>
				</section>
			{/if}
		</aside>
	</div>
{/if}

<style>
	.subtitle {
		margin: 0 0 1rem;
	}
	.objectives {
		list-style: none;
		padding: 0;
		margin: 0.5rem 0 0;
	}
	.objectives li {
		padding: 0.25rem 0;
	}
	.dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		margin-right: 0.3rem;
		border: 1px solid #0006;
	}
	.sub {
		font-size: 0.85rem;
		margin-left: 1.2rem;
		color: var(--muted);
	}
	.rewards {
		list-style: none;
		padding: 0;
		margin: 0 0 0.6rem;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 0.2rem 1rem;
	}
	.questline-card {
		display: block;
		background: linear-gradient(180deg, #3d3220, #251d12);
		border-color: #000;
		color: #f0c53e;
		font-family: Georgia, serif;
	}
	.questline-card:hover {
		text-decoration: none;
		box-shadow: 0 0 0 1px #f0c53e inset;
	}
	.questline-card .ql-title {
		display: block;
		font-size: 1.05rem;
	}
	.questline-card .muted {
		color: #b9a77f;
		font-family: system-ui, sans-serif;
		font-size: 0.8rem;
	}
	.chain dt {
		white-space: nowrap;
	}
</style>
