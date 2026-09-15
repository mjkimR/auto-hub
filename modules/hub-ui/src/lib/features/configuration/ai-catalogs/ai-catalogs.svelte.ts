import { api, type components } from '$lib/api';
import { SvelteDate } from 'svelte/reactivity';
import { toast } from 'svelte-sonner';

export type AICatalog = components['schemas']['AICatalogRead'];
export type AICatalogSession = components['schemas']['AICatalogSessionRead'];

export type CatalogConnector = { id: string; name: string; provider: string; enabled: boolean };

export type CodexWindowConfig = {
	short_refresh_enabled: boolean;
	short_refresh_cycle_minutes: number;
	long_refresh_cycle_minutes: number;
	probe_window_minutes: number;
};

export type DailyQuotaConfig = {
	daily_task_limit: number;
	window: 'rolling' | 'calendar';
	timezone: string;
};

const SESSION_MARKER = / \[hub-session:[^\]]+\]$/;

/** A Codex catalog's refresh policy, with the backend defaults filled in for settings it has never saved. */
export function codexWindowConfig(catalog: AICatalog): CodexWindowConfig {
	const config = (catalog.policy_config ?? {}) as Partial<CodexWindowConfig>;
	return {
		short_refresh_enabled: config.short_refresh_enabled ?? true,
		short_refresh_cycle_minutes: config.short_refresh_cycle_minutes ?? 300,
		long_refresh_cycle_minutes: config.long_refresh_cycle_minutes ?? 10080,
		probe_window_minutes: config.probe_window_minutes ?? 10
	};
}

/** The daily quota settings of a catalog whose kind counts tasks per day, or null when none are saved yet. */
export function dailyQuotaConfig(catalog: AICatalog): DailyQuotaConfig | null {
	const config = (catalog.policy_config ?? {}) as Partial<DailyQuotaConfig>;
	if (typeof config.daily_task_limit !== 'number') return null;
	return {
		daily_task_limit: config.daily_task_limit,
		window: config.window === 'calendar' ? 'calendar' : 'rolling',
		timezone: config.timezone ?? 'UTC'
	};
}

export function dailyQuotaSummary(catalog: AICatalog): string {
	const config = dailyQuotaConfig(catalog);
	if (!config) return 'Daily quota: not configured — dispatch is blocked until it is set';
	const reset =
		config.window === 'calendar' ? `resets at midnight ${config.timezone}` : 'rolling 24 hours';
	return `Daily quota: ${config.daily_task_limit} tasks · ${reset}`;
}

/** Session titles carry a hidden reconciliation marker that operators do not need to see. */
export function sessionTitle(title: string): string {
	return title.replace(SESSION_MARKER, '');
}

export function isKnownTimezone(timezone: string): boolean {
	try {
		Intl.DateTimeFormat('en-US', { timeZone: timezone }).resolvedOptions();
		return true;
	} catch {
		return false;
	}
}

function detail(error: unknown, fallback: string): string {
	return (error as { detail?: string } | undefined)?.detail ?? fallback;
}

export class AICatalogsState {
	items = $state<AICatalog[]>([]);
	connectors = $state<CatalogConnector[]>([]);
	loading = $state(false);
	saving = $state(false);

	async load() {
		this.loading = true;
		try {
			const [catalogs, connectors] = await Promise.all([
				api.GET('/api/v1/ai-catalogs'),
				api.GET('/api/v1/connectors', { params: { query: { limit: 100 } } })
			]);
			this.items = catalogs.data?.items ?? [];
			this.connectors = (connectors.data?.items ?? []).map(({ id, name, provider, enabled }) => ({
				id,
				name,
				provider,
				enabled
			}));
		} catch {
			toast.error('Failed to load AI catalogs');
		} finally {
			this.loading = false;
		}
	}

	async loadSessions(
		key: string,
		offset: number,
		limit: number
	): Promise<{ items: AICatalogSession[]; total: number }> {
		try {
			const res = await api.GET('/api/v1/ai-catalogs/{catalog_key}/sessions', {
				params: { path: { catalog_key: key }, query: { offset, limit } }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to load catalog sessions'));
				return { items: [], total: 0 };
			}
			return { items: res.data?.items ?? [], total: res.data?.total_count ?? 0 };
		} catch {
			toast.error('Failed to load catalog sessions');
			return { items: [], total: 0 };
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
			toast.success('AI catalog availability updated for all of its work');
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

	async updatePolicyConfig(key: string, policyConfig: CodexWindowConfig | DailyQuotaConfig) {
		this.saving = true;
		try {
			const res = await api.PUT('/api/v1/ai-catalogs/{catalog_key}/policy-config', {
				params: { path: { catalog_key: key } },
				body: { policy_config: policyConfig }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to update quota policy'));
				return false;
			}
			toast.success('AI catalog quota policy updated');
			await this.load();
			return true;
		} finally {
			this.saving = false;
		}
	}

	async setConnector(key: string, connectorId: string | null) {
		this.saving = true;
		try {
			const res = await api.PUT('/api/v1/ai-catalogs/{catalog_key}/connector', {
				params: { path: { catalog_key: key } },
				body: { connector_id: connectorId }
			});
			if (res.error) {
				toast.error(detail(res.error, 'Failed to update catalog connector'));
				return false;
			}
			toast.success(connectorId ? 'AI catalog connector assigned' : 'AI catalog connector removed');
			await this.load();
			return true;
		} finally {
			this.saving = false;
		}
	}
}
