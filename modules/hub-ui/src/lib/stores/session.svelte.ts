import { API_KEY_STORAGE } from '$lib/config';

function readInitialKey(): string {
	try {
		return (
			globalThis.sessionStorage?.getItem(API_KEY_STORAGE) ||
			globalThis.localStorage?.getItem(API_KEY_STORAGE) ||
			''
		);
	} catch {
		return '';
	}
}

class Session {
	apiKey = $state(readInitialKey());
	isAuthenticated = $derived(this.apiKey.trim().length > 0);
	activeTab = $state<
		| 'dashboard'
		| 'projects'
		| 'pipeline-runs'
		| 'connectors'
		| 'configs'
		| 'jobs'
		| 'system'
		| 'specs'
	>('dashboard');

	setApiKey(key: string) {
		this.apiKey = key;
		try {
			if (key) {
				globalThis.sessionStorage?.setItem(API_KEY_STORAGE, key);
			} else {
				globalThis.sessionStorage?.removeItem(API_KEY_STORAGE);
			}
		} catch {
			// storage blocked
		}
	}

	logout() {
		this.setApiKey('');
	}
}

export const session = new Session();
