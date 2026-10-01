<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { site } from '$lib/context.svelte';
	import { getQuestIndex } from '$lib/data';
	import { FLAVOR_LABELS } from '$lib/format';
	import { exportLua, FIELDS, parseIds, TEXT_FIELDS, textVarFor, type ExportFile, type ExportType } from '$lib/lua-export';
	import { LOCALES, settings } from '$lib/settings.svelte';
	import { createZip } from '$lib/zip';
	import { param, syncUrl, urlParams } from '$lib/url-state';

	const flavor = $derived(page.params.flavor!);

	const TYPES: [ExportType, string][] = [
		['quest', 'Quests'],
		['npc', 'NPCs'],
		['object', 'Objects'],
		['item', 'Items'],
		['questline', 'Questlines']
	];

	// Options are kept in the URL, e.g. #/forever/export?type=item&fields=name,quality&locale=all
	const p = urlParams();
	const urlType = TYPES.find(([id]) => id === p.get('type'))?.[0];
	let type = $state<ExportType>(urlType ?? 'quest');
	let selected = $state<Record<string, boolean>>(
		Object.fromEntries(param.list(p, 'fields').filter((f) => FIELDS[urlType ?? 'quest'].includes(f)).map((f) => [f, true]))
	);
	let ids = $state(param.str(p, 'ids'));
	let zone = $state(param.str(p, 'zone'));
	const urlLocale = p.get('locale');
	let locale = $state(urlLocale && (urlLocale === 'all' || urlLocale in LOCALES) ? urlLocale : settings.locale);
	let refs = $state<'id' | 'full'>(p.get('refs') === 'full' ? 'full' : 'id');
	let style = $state<'addon' | 'return'>(p.get('style') === 'return' ? 'return' : 'addon');
	let varName = $state(param.str(p, 'var', `${urlType ?? 'quest'}Data`));
	let varTouched = $state(p.has('var'));

	let running = $state(false);
	let progress = $state<[number, number]>([0, 0]);
	let error = $state('');
	let files = $state<ExportFile[] | null>(null);
	let previewIndex = $state(0);

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
	let lastType = untrack(() => type);
	$effect(() => {
		if (type !== lastType) {
			lastType = type;
			selected = {};
			files = null;
		}
	});
	$effect(() => {
		syncUrl(
			{
				type,
				fields: chosen.join(','),
				ids: ids.trim(),
				zone,
				locale,
				refs,
				style,
				var: varTouched ? varName : null
			},
			{ type: 'quest', refs: 'id', style: 'addon' }
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
	const textFields = $derived(TEXT_FIELDS[type]);
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
					<label class:textfield={textFields.includes(f)}><input type="checkbox" bind:checked={selected[f]} /> {f}</label>
				{/each}
			</div>
			<p class="hint muted">
				Nothing ticked exports every field.
				{#if textFields.length}<span class="textfield">Italic</span> fields are texts and go to a separate
					<code>{textVarFor(varName)}.{locale === 'all' ? '<language>' : locale}.lua</code>, keyed by the same IDs.{/if}
			</p>
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
				<option value="all">All languages (one texts file each)</option>
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
	.textfield {
		font-style: italic;
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
