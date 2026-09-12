// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	interface ImportMetaEnv {
		readonly VITE_API_BASE_URL?: string;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
