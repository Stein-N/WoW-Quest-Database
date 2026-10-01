import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Fully static single-page build. Hash routing (#/classic/quest/2) needs no server
			// rewrites, so the same output runs on GitHub Pages and on any plain web server.
			adapter: adapter(),
			router: { type: 'hash' },
			paths: { relative: true }
		})
	]
});
