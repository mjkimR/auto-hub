import { api, type components } from '$lib/api';
import { SvelteDate } from 'svelte/reactivity';
import { toast } from 'svelte-sonner';

type AICatalog = components['schemas']['AICatalogRead'];

function detail(error: unknown, fallback: string): string {
	return (error as { detail?: string } | undefined)?.detail ?? fallback;
}

export class AICatalogsState {
	items = $state<AICatalog[]>([]);
	loading = $state(false);
	saving = $state(false);

	async load() {
		this.loading = true;
		try {
			const res = await api.GET('/api/v1/ai-catalogs');
			this.items = res.data?.items ?? [];
		} catch {
			toast.error('Failed to load AI catalogs');
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
			const res = await api.PUT('/api/v1/ai-catalogs/{catalog_key}/availability', {
				params: { path: { catalog_key: key } },
				body: { available_at: instant.toISOString(), note: note.trim() || null, source: 'manual' }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to set AI catalog availability'));
				return false;
			}
			toast.success('AI catalog availability updated for every assigned run');
			await this.load();
			return true;
		} finally {
			this.saving = false;
		}
	}

	async clearAvailability(key: string) {
		this.saving = true;
		try {
			const res = await api.DELETE('/api/v1/ai-catalogs/{catalog_key}/availability', {
				params: { path: { catalog_key: key } }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to clear AI catalog availability'));
				return;
			}
			toast.success('AI catalog is available for dispatch');
			await this.load();
		} finally {
			this.saving = false;
		}
	}

	async setEnabled(key: string, enabled: boolean) {
		this.saving = true;
		try {
			const res = await api.PUT('/api/v1/ai-catalogs/{catalog_key}/enabled', {
				params: { path: { catalog_key: key } },
				body: { enabled }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to update AI catalog'));
				return;
			}
			toast.success(enabled ? 'AI catalog enabled' : 'AI catalog disabled');
			await this.load();
		} finally {
			this.saving = false;
		}
	}
}
