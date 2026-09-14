import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

const backend = process.env.AUTO_HUB_SERVER ?? 'http://127.0.0.1:8389';

export default defineConfig({
	resolve: {
		conditions: ['browser']
	},
	test: {
		environment: 'jsdom'
	},
	server: {
		proxy: {
			'^/api': backend,
			'^/docs': backend,
			'^/openapi.json': backend
		}
	},
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for project files
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({ fallback: 'index.html' })
		})
	]
});
