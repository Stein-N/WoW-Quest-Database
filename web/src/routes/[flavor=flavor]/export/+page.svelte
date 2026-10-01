<script lang="ts">
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { getQuestIndex } from '$lib/data';
	import { FLAVOR_LABELS } from '$lib/format';
	import { exportLua, FIELDS, parseIds, type ExportResult, type ExportType } from '$lib/lua-export';
	import { LOCALES, settings } from '$lib/settings.svelte';

	const flavor = $derived(page.params.flavor!);

	const TYPES: [ExportType, string][] = [
		['quest', 'Quests'],
		['npc', 'NPCs'],
		['object', 'Objects'],
		['item', 'Items'],
		['questline', 'Questlines']
	];

	let type = $state<ExportType>('quest');
	let selected = $state<Record<string, boolean>>({});
	let ids = $state('');
	let zone = $state('');
	let locale = $state(settings.locale);
	let refs = $state<'id' | 'full'>('id');
	let style = $state<'addon' | 'return'>('addon');
	let varName = $state('questData');
	let varTouched = $state(false);

	let running = $state(false);
	let progress = $state<[number, number]>([0, 0]);
	let error = $state('');
	let result = $state<ExportResult | null>(null);

	const fields = $derived(FIELDS[type]);
	const chosen = $derived(fields.filter((f) => selected[f]));
	const idError = $derived.by(() => {
		try {
			parseIds(ids);
			return '';
		} catch (e) {
			return (e as Error).message;
		}
	});

	// Default table name follows the type until the user edits it.
	$effect(() => {
		if (!varTouched) varName = `${type}Data`;
	});
	$effect(() => {
		void type;
		selected = {};
		result = null;
	});

	async function zoneOptions(flavor: string) {
		const rows = await getQuestIndex(flavor);
		const used = new Set(rows.map((r) => r[5]).filter((z) => z > 0));
		return [...used].map((id) => ({ id, name: site.zoneName(id) })).sort((a, b) => a.name.localeCompare(b.name));
	}

	async function run() {
		running = true;
		error = '';
		result = null;
		progress = [0, 0];
		try {
			result = await exportLua(
				{
					flavor,
					type,
					fields: chosen,
					ids,
					zone: zone === '' ? null : Number(zone),
					locale,
					refs,
					style,
					varName
				},
				(done, total) => (progress = [done, total])
			);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			running = false;
		}
	}

	function download() {
		if (!result) return;
		const url = URL.createObjectURL(new Blob([result.text], { type: 'text/x-lua;charset=utf-8' }));
		const a = document.createElement('a');
		a.href = url;
		a.download = result.fileName;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	let copied = $state(false);
	async function copy() {
		if (!result) return;
		await navigator.clipboard.writeText(result.text);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}

	const preview = $derived(result ? result.text.split('\n').slice(0, 40).map((l) => (l.length > 400 ? `${l.slice(0, 400)} …` : l)).join('\n') : '');
	const size = $derived(result ? new Blob([result.text]).size : 0);
</script>

<svelte:head><title>Lua export – WoW Quest Database</title></svelte:head>

<h1>Lua export</h1>
<p class="muted">
	Export {FLAVOR_LABELS[flavor]} data as a Lua table, e.g. for an addon. Same output as
	<code>etl/export_lua.py</code>.
</p>

<div class="grid">
	<form
		class="panel form"
		onsubmit={(e) => {
			e.preventDefault();
			run();
		}}
	>
		<label class="row">
			<span>Data</span>
			<select bind:value={type}>
				{#each TYPES as [id, label] (id)}<option value={id}>{label}</option>{/each}
			</select>
		</label>

		<fieldset>
			<legend>
				Fields
				<span class="muted">({chosen.length ? `${chosen.length} selected` : 'all'})</span>
				<button type="button" class="linkish" onclick={() => (selected = {})}>all</button>
			</legend>
			<div class="fields">
				{#each fields as f (f)}
					<label><input type="checkbox" bind:checked={selected[f]} /> {f}</label>
				{/each}
			</div>
			<p class="hint muted">Nothing ticked exports every field.</p>
		</fieldset>

		<label class="row">
			<span>IDs</span>
			<input type="search" placeholder="all, or e.g. 2,33,100-200" bind:value={ids} />
		</label>
		{#if idError}<p class="err">{idError}</p>{/if}

			<label class="row">
				<span>Zone</span>
				{#await zoneOptions(flavor) then zones}
					<select bind:value={zone}>
						<option value="">All zones</option>
						{#each zones as z (z.id)}<option value={String(z.id)}>{z.name}</option>{/each}
					</select>
				{/await}
			</label>

		<label class="row">
			<span>Language</span>
			<select bind:value={locale}>
				{#each Object.entries(LOCALES) as [code, label] (code)}<option value={code}>{label}</option>{/each}
			</select>
		</label>

		<div class="row">
			<span>References</span>
			<div class="opts">
				<label><input type="radio" bind:group={refs} value="id" /> IDs only</label>
				<label><input type="radio" bind:group={refs} value="full" /> with type &amp; name</label>
			</div>
		</div>

		<div class="row">
			<span>Format</span>
			<div class="opts">
				<label><input type="radio" bind:group={style} value="addon" /> <code>addon.{varName} = {'{…}'}</code></label>
				<label><input type="radio" bind:group={style} value="return" /> <code>return {'{…}'}</code></label>
			</div>
		</div>

		{#if style === 'addon'}
			<label class="row">
				<span>Table name</span>
				<input type="search" bind:value={varName} oninput={() => (varTouched = true)} />
			</label>
		{/if}

		<div class="actions">
			<button class="primary" type="submit" disabled={running || !!idError}>
				{running ? 'Exporting…' : 'Generate Lua'}
			</button>
			{#if running && progress[1] > 1}
				<progress max={progress[1]} value={progress[0]}></progress>
				<span class="muted">{progress[0]} / {progress[1]} files</span>
			{/if}
		</div>
		{#if error}<p class="err">{error}</p>{/if}
	</form>

	<aside>
		{#if result}
			<section class="panel">
				<h3>{result.fileName}</h3>
				<p class="muted">{result.count.toLocaleString('en')} entries · {(size / 1024).toFixed(size > 1024 * 100 ? 0 : 1)} KB</p>
				<div class="actions">
					<button class="primary" onclick={download}>Download</button>
					<button onclick={copy}>{copied ? 'Copied' : 'Copy'}</button>
				</div>
			</section>
		{:else}
			<section class="panel muted">
				Pick what to export and press <em>Generate Lua</em>. Large exports (all items or NPCs) load
				a few hundred data files and produce files of around 10 MB.
			</section>
		{/if}
	</aside>
</div>

{#if result}
	<h2>Preview <span class="count">first 40 lines</span></h2>
	<pre class="preview">{preview}</pre>
{/if}

<style>
	.form {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}
	.row {
		display: grid;
		grid-template-columns: 7.5rem 1fr;
		align-items: center;
		gap: 0.5rem;
	}
	.row > span {
		color: var(--muted);
	}
	.opts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
	}
	fieldset {
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.5rem 0.75rem;
		margin: 0;
	}
	legend {
		padding: 0 0.3rem;
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
		gap: 0.15rem 0.75rem;
		font-size: 0.88rem;
	}
	.fields label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hint {
		font-size: 0.8rem;
		margin: 0.4rem 0 0;
	}
	.actions {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		flex-wrap: wrap;
	}
	button.primary,
	.actions button {
		background: var(--panel);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.4rem 0.9rem;
		cursor: pointer;
	}
	button.primary {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--bg);
		font-weight: 600;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.err {
		color: var(--horde);
		margin: 0;
	}
	.preview {
		background: var(--panel);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.75rem;
		overflow: auto;
		max-height: 60vh;
		font-size: 0.8rem;
		line-height: 1.4;
	}
	code {
		font-size: 0.85em;
	}
</style>
