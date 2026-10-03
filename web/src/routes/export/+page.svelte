<script lang="ts">
	import { untrack } from 'svelte';
	import { FLAVOR, site } from '$lib/context.svelte';
	import { getQuestIndex } from '$lib/data';
	import { FLAVOR_LABELS } from '$lib/format';
	import { exportLua, FIELD_DOCS, FIELDS, parseIds, TEXT_FIELDS, textVarFor, type ExportFile, type ExportType } from '$lib/lua-export';
	import { LOCALES, settings } from '$lib/settings.svelte';
	import { createZip } from '$lib/zip';
	import { param, syncUrl, urlParams } from '$lib/url-state';

	const flavor = FLAVOR;

	const TYPES: [ExportType, string][] = [
		['quest', 'Quests'],
		['npc', 'NPCs'],
		['object', 'Objects'],
		['item', 'Items'],
		['questline', 'Questlines']
	];

	// Options are kept in the URL, e.g. #/forever/export?type=item&fields=quality,stats&l10n=none&locale=all
	// (fields = data fields, l10n = localization fields; missing = all, "none" = none)
	const p = urlParams();
	const urlType = TYPES.find(([id]) => id === p.get('type'))?.[0];
	let type = $state<ExportType>(urlType ?? 'quest');

	const dataFieldsOf = (t: ExportType) => FIELDS[t].filter((f) => !TEXT_FIELDS[t].includes(f));
	const pick = (all: string[], spec: string | null): Record<string, boolean> => {
		const wanted = spec === null ? all : spec === 'none' ? [] : spec.split(',');
		return Object.fromEntries(all.map((f) => [f, wanted.includes(f)]));
	};
	let dataSel = $state(pick(dataFieldsOf(urlType ?? 'quest'), p.get('fields')));
	let textSel = $state(pick(TEXT_FIELDS[urlType ?? 'quest'], p.get('l10n')));
	let ids = $state(param.str(p, 'ids'));
	let zone = $state(param.str(p, 'zone'));
	const urlLocale = p.get('locale');
	let locale = $state(urlLocale && (urlLocale === 'all' || urlLocale in LOCALES) ? urlLocale : settings.locale);
	let varName = $state(param.str(p, 'var', `${urlType ?? 'quest'}Data`));
	let varTouched = $state(p.has('var'));

	let running = $state(false);
	let progress = $state<[number, number]>([0, 0]);
	let error = $state('');
	let files = $state<ExportFile[] | null>(null);
	let previewIndex = $state(0);

	const dataFields = $derived(dataFieldsOf(type));
	const textFields = $derived(TEXT_FIELDS[type]);
	const dataChosen = $derived(dataFields.filter((f) => dataSel[f]));
	const textChosen = $derived(textFields.filter((f) => textSel[f]));
	const allChosen = $derived(dataChosen.length === dataFields.length && textChosen.length === textFields.length);
	/** fields passed to the export; [] means every field */
	const chosen = $derived(allChosen ? [] : [...dataChosen, ...textChosen]);
	const nothingChosen = $derived(!dataChosen.length && !textChosen.length);
	const urlList = (picked: string[], all: string[]) =>
		picked.length === all.length ? null : picked.length ? picked.join(',') : 'none';
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
	let lastType = untrack(() => type);
	$effect(() => {
		if (type !== lastType) {
			lastType = type;
			dataSel = pick(dataFieldsOf(type), null);
			textSel = pick(TEXT_FIELDS[type], null);
			files = null;
		}
	});
	$effect(() => {
		syncUrl(
			{
				type,
				fields: urlList(dataChosen, dataFields),
				l10n: urlList(textChosen, textFields),
				ids: ids.trim(),
				zone,
				locale,
				var: varTouched ? varName : null
			},
			{ type: 'quest' }
		);
	});

	async function zoneOptions(flavor: string) {
		const rows = await getQuestIndex(flavor);
		const used = new Set(rows.map((r) => r[5]).filter((z) => z > 0));
		return [...used].map((id) => ({ id, name: site.zoneName(id) })).sort((a, b) => a.name.localeCompare(b.name));
	}

	async function run() {
		running = true;
		error = '';
		files = null;
		progress = [0, 0];
		try {
			previewIndex = 0;
			files = await exportLua(
				{
					flavor,
					type,
					fields: chosen,
					ids,
					zone: zone === '' ? null : Number(zone),
					locale,
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

	function download(file: ExportFile) {
		const url = URL.createObjectURL(new Blob([file.text], { type: 'text/x-lua;charset=utf-8' }));
		const a = document.createElement('a');
		a.href = url;
		a.download = file.fileName;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	function downloadZip() {
		if (!files) return;
		const zip = createZip(files.map((f) => ({ name: f.fileName, text: f.text })));
		const url = URL.createObjectURL(zip);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${varName}-${flavor}${locale === 'all' ? '-all-languages' : ''}.zip`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	let copied = $state('');
	async function copy(file: ExportFile) {
		await navigator.clipboard.writeText(file.text);
		copied = file.fileName;
		setTimeout(() => (copied = ''), 1500);
	}

	const sizeOf = (file: ExportFile) => {
		const bytes = new Blob([file.text]).size;
		return bytes > 1024 * 100 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024).toFixed(1)} KB`;
	};
	const shown = $derived(files?.[previewIndex] ?? files?.[0]);
	const preview = $derived(
		shown ? shown.text.split('\n').slice(0, 40).map((l) => (l.length > 400 ? `${l.slice(0, 400)} …` : l)).join('\n') : ''
	);
	// one floating tooltip for the field explanations, kept inside the viewport
	let tip = $state<{ text: string; x: number; y: number; below: boolean } | null>(null);
	function showTip(e: Event, text: string) {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const below = r.top < 110;
		tip = { text, x: r.left + r.width / 2, y: below ? r.bottom + 6 : r.top - 6, below };
	}
	const hideTip = () => (tip = null);

	const setAll = (sel: Record<string, boolean>, value: boolean) => {
		for (const k of Object.keys(sel)) sel[k] = value;
	};
</script>

{#snippet info(field: string)}
	{#if FIELD_DOCS[type][field]}
		<button
			type="button"
			class="info"
			aria-label="About {field}: {FIELD_DOCS[type][field]}"
			onmouseenter={(e) => showTip(e, FIELD_DOCS[type][field])}
			onmouseleave={hideTip}
			onfocus={(e) => showTip(e, FIELD_DOCS[type][field])}
			onblur={hideTip}
			onclick={(e) => (tip ? hideTip() : showTip(e, FIELD_DOCS[type][field]))}>ⓘ</button
		>
	{/if}
{/snippet}

<svelte:head><title>Lua export – Forever Database</title></svelte:head>
<svelte:window onscroll={hideTip} />

{#if tip}
	<div
		class="tooltip"
		role="tooltip"
		style="--x:{tip.x}px; top:{tip.y}px; transform: translateY({tip.below ? '0' : '-100%'})"
	>
		{tip.text}
	</div>
{/if}

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
		<fieldset>
			<legend>Selection</legend>
			<label class="row">
				<span>Data</span>
				<select bind:value={type}>
					{#each TYPES as [id, label] (id)}<option value={id}>{label}</option>{/each}
				</select>
			</label>
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
		</fieldset>

		<fieldset>
			<legend>
				Data file <code>{varName}.lua</code>
				<span class="muted">({dataChosen.length} of {dataFields.length} fields)</span>
			</legend>
			<div class="pickers">
				<button type="button" class="linkish" onclick={() => setAll(dataSel, true)}>All</button>
				<button type="button" class="linkish" onclick={() => setAll(dataSel, false)}>None</button>
			</div>
			<div class="fields">
				{#each dataFields as f (f)}
					<div class="field">
						<label><input type="checkbox" bind:checked={dataSel[f]} /> {f}</label>
						{@render info(f)}
					</div>
				{/each}
			</div>
			<label class="row">
				<span>Table name</span>
				<input type="search" bind:value={varName} oninput={() => (varTouched = true)} />
			</label>
			{#if !dataChosen.length && textChosen.length}
				<p class="hint muted">No data fields selected: only the localization files are exported.</p>
			{/if}
		</fieldset>

		{#if textFields.length}
			<fieldset>
				<legend>
					Localization files <code>{textVarFor(varName)}.{locale === 'all' ? '<language>' : locale}.lua</code>
					<span class="muted">({textChosen.length} of {textFields.length} fields)</span>
				</legend>
				<div class="pickers">
					<button type="button" class="linkish" onclick={() => setAll(textSel, true)}>All</button>
					<button type="button" class="linkish" onclick={() => setAll(textSel, false)}>None</button>
				</div>
				<div class="fields">
					{#each textFields as f (f)}
						<div class="field">
							<label><input type="checkbox" bind:checked={textSel[f]} /> {f}</label>
							{@render info(f)}
						</div>
					{/each}
				</div>
				<label class="row">
					<span>Language</span>
					<select bind:value={locale} disabled={!textChosen.length}>
						{#each Object.entries(LOCALES) as [code, label] (code)}<option value={code}>{label}</option>{/each}
						<option value="all">All languages (one file each)</option>
					</select>
				</label>
				<p class="hint muted">
					{#if textChosen.length}
						Texts go to their own file per language, keyed by the same IDs as the data file. <code>{textVarFor(varName)}.enUS.lua</code> creates the table and is always included as
						the fallback: load it first; other languages only replace the entries they translate and run
						only in a client of that language (<code>GetLocale()</code>).
					{:else}
						No localization fields selected: no localization files are exported.
					{/if}
				</p>
			</fieldset>
		{/if}

		<div class="actions">
			<button class="primary" type="submit" disabled={running || !!idError || nothingChosen}>
				{running ? 'Exporting…' : 'Generate Lua'}
			</button>
			{#if running && progress[1] > 1}
				<progress max={progress[1]} value={progress[0]}></progress>
				<span class="muted">{progress[0]} / {progress[1]} files</span>
			{/if}
		</div>
		{#if nothingChosen}<p class="err">Select at least one data or localization field.</p>{/if}
		{#if error}<p class="err">{error}</p>{/if}
	</form>

	<aside>
		{#if files}
			<section class="panel">
				{#each files as file (file.fileName)}
					<div class="file">
						<h3>{file.fileName}</h3>
						<p class="muted">{file.count.toLocaleString('en')} entries · {sizeOf(file)}</p>
						<div class="actions">
							<button onclick={() => download(file)}>Download</button>
							<button onclick={() => copy(file)}>{copied === file.fileName ? 'Copied' : 'Copy'}</button>
						</div>
					</div>
				{/each}
				{#if files.length > 1}
					<div class="actions"><button class="primary" onclick={downloadZip}>Download all (.zip)</button></div>
				{/if}
			</section>
		{:else}
			<section class="panel muted">
				Pick what to export and press <em>Generate Lua</em>. Large exports (all items or NPCs) load
				a few hundred data files and produce files of around 10 MB.
			</section>
		{/if}
	</aside>
</div>

{#if files && shown}
	<h2>Preview <span class="count">first 40 lines</span></h2>
	{#if files.length > 1}
		<div class="actions tabs">
			{#each files as file, i (file.fileName)}
				<button class:active={shown === file} onclick={() => (previewIndex = i)}>{file.fileName}</button>
			{/each}
		</div>
	{/if}
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
	.field {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-width: 0;
	}
	.field label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.info {
		position: relative;
		background: none;
		border: none;
		padding: 0 0.15rem;
		color: var(--muted);
		cursor: help;
		font-size: 0.85rem;
		line-height: 1;
	}
	.info:hover,
	.info:focus-visible {
		color: var(--accent);
	}
	.tooltip {
		position: fixed;
		/* centred on the icon, but never closer than 8px to the viewport edges */
		left: clamp(8px, calc(var(--x) - 9rem), calc(100vw - 18rem - 8px));
		width: max-content;
		max-width: min(18rem, calc(100vw - 16px));
		padding: 0.45rem 0.6rem;
		border-radius: 6px;
		background: var(--text);
		color: var(--bg);
		font-size: 0.8rem;
		line-height: 1.35;
		box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
		pointer-events: none;
		z-index: 2000;
	}
	.pickers {
		display: flex;
		gap: 0.8rem;
		margin-bottom: 0.3rem;
		font-size: 0.85rem;
	}
	fieldset {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		/* fieldsets default to min-width: min-content and would widen the page on phones */
		min-width: 0;
	}
	.row > * {
		min-width: 0;
	}
	.row input,
	.row select {
		width: 100%;
	}
	legend {
		max-width: 100%;
		overflow-wrap: anywhere;
	}
	legend code {
		font-size: 0.8em;
		color: var(--muted);
	}
	.file + .file {
		border-top: 1px solid var(--border);
		margin-top: 0.75rem;
		padding-top: 0.75rem;
	}
	.file h3 {
		margin: 0;
		word-break: break-all;
	}
	.file p {
		margin: 0.2rem 0 0.5rem;
	}
	.file + .actions {
		margin-top: 0.9rem;
	}
	.tabs {
		margin-bottom: 0.5rem;
	}
	.tabs button.active {
		border-color: var(--accent);
		color: var(--accent);
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
