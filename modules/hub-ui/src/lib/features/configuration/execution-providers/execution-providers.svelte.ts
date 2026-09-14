import { api, type components } from '$lib/api';
import { SvelteDate } from 'svelte/reactivity';
import { toast } from 'svelte-sonner';

type Provider = components['schemas']['ExecutionProviderRead'];

function detail(error: unknown, fallback: string): string {
	return (error as { detail?: string } | undefined)?.detail ?? fallback;
}

export class ExecutionProvidersState {
	items = $state<Provider[]>([]);
	loading = $state(false);
	saving = $state(false);

	async load() {
		this.loading = true;
		try {
			const res = await api.GET('/api/v1/execution-providers');
			this.items = res.data?.items ?? [];
		} catch {
			toast.error('Failed to load execution providers');
		} finally {
			this.loading = false;
		}
	}

	async setAvailability(key: string, availableAt: string, note: string) {
		const instant = new SvelteDate(availableAt);
		if (Number.isNaN(instant.getTime()) || instant.getTime() <= Date.now()) {
			toast.error('Enter a future local date and time');
			return false;
		}
		this.saving = true;
		try {
			const res = await api.PUT('/api/v1/execution-providers/{provider_key}/availability', {
				params: { path: { provider_key: key } },
				body: { available_at: instant.toISOString(), note: note.trim() || null, source: 'manual' }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to set provider availability'));
				return false;
			}
			toast.success('Provider availability updated for every assigned run');
			await this.load();
			return true;
		} finally {
			this.saving = false;
		}
	}

	async clearAvailability(key: string) {
		this.saving = true;
		try {
			const res = await api.DELETE('/api/v1/execution-providers/{provider_key}/availability', {
				params: { path: { provider_key: key } }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to clear provider availability'));
				return;
			}
			toast.success('Provider is available for dispatch');
			await this.load();
		} finally {
			this.saving = false;
		}
	}

	async setEnabled(key: string, enabled: boolean) {
		this.saving = true;
		try {
			const res = await api.PUT('/api/v1/execution-providers/{provider_key}/enabled', {
				params: { path: { provider_key: key } },
				body: { enabled }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to update provider'));
				return;
			}
			toast.success(enabled ? 'Provider enabled' : 'Provider disabled');
			await this.load();
		} finally {
			this.saving = false;
		}
	}
}
