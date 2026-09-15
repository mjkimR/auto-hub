import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { toast } from 'svelte-sonner';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import AICatalogsView from './AICatalogsView.svelte';

const { api } = vi.hoisted(() => ({ api: { GET: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() } }));

vi.mock('$lib/api', () => ({ api }));
vi.mock('svelte-sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const base = {
	enabled: true,
	availability_state: 'normal',
	available_at: null,
	availability_source: null,
	availability_note: null,
	configured_concurrency: 3,
	effective_concurrency: 3,
	active_dispatch_count: 0,
	held_run_count: 0,
	open_session_count: 0,
	connector_id: null,
	policy_config: {},
	policy_state: {}
};
const codex = {
	...base,
	id: 'c1',
	key: 'personal-codex',
	name: 'Personal Codex',
	kind: 'codex',
	adapter: 'codex-github-mention',
	connector_provider: null,
	pipeline_delivery: true
};
const jules = {
	...base,
	id: 'j1',
	key: 'personal-jules',
	name: 'Personal Jules',
	kind: 'jules',
	adapter: 'jules-api',
	connector_provider: 'jules',
	pipeline_delivery: false
};
const connectors = [
	{ id: 'k1', name: 'Jules key', provider: 'jules', enabled: true },
	{ id: 'g1', name: 'GitHub token', provider: 'github', enabled: true }
];
const sessions = [
	{
		id: 's1',
		title: 'Weekly hygiene report [hub-session:abc]',
		state: 'in_progress',
		url: 'https://jules.google/session/1',
		pull_request_url: null,
		failure_detail: null,
		created_at: '2026-09-15T00:00:00Z'
	}
];

beforeEach(() => {
	vi.clearAllMocks();
	api.GET.mockImplementation((path: string) => {
		if (path === '/api/v1/connectors') return Promise.resolve({ data: { items: connectors } });
		if (path === '/api/v1/ai-catalogs/{catalog_key}/sessions')
			return Promise.resolve({ data: { items: sessions, total_count: 45 } });
		return Promise.resolve({ data: { items: [codex, jules] } });
	});
	api.PUT.mockResolvedValue({ data: jules });
});

afterEach(() => {
	cleanup();
	// A dialog closed by the previous test can leave the body inert until its exit animation would end.
	document.body.style.removeProperty('pointer-events');
});

test('shows each kind its own policy editor and session controls only where the kind has them', async () => {
	render(AICatalogsView);

	await screen.findByText('Personal Jules');
	expect(screen.getAllByRole('button', { name: 'Refresh policy' })).toHaveLength(1);
	expect(screen.getAllByRole('button', { name: 'Quota policy' })).toHaveLength(1);
	expect(screen.getAllByRole('button', { name: 'Connector' })).toHaveLength(1);
	expect(screen.getAllByRole('button', { name: 'Sessions' })).toHaveLength(1);
	expect(screen.getByText(/Daily quota: not configured/)).toBeTruthy();
	expect(screen.getByText(/Connector: not assigned/)).toBeTruthy();
	expect(screen.getByText(/0 open session\(s\)/)).toBeTruthy();
});

test('saves a calendar daily quota for a Jules catalog', async () => {
	const user = userEvent.setup();
	render(AICatalogsView);
	await screen.findByText('Personal Jules');

	await user.click(screen.getByRole('button', { name: 'Quota policy' }));
	// Edit the multi-character limit last: the dialog moves focus once while it opens.
	await user.selectOptions(screen.getByLabelText('Daily window'), 'calendar');
	await user.clear(screen.getByLabelText('Reset timezone'));
	await user.type(screen.getByLabelText('Reset timezone'), 'America/Los_Angeles');
	await user.clear(screen.getByLabelText('Daily task limit'));
	await user.type(screen.getByLabelText('Daily task limit'), '250');
	await user.click(screen.getByRole('button', { name: 'Save quota policy' }));

	await waitFor(() =>
		expect(api.PUT).toHaveBeenCalledWith('/api/v1/ai-catalogs/{catalog_key}/policy-config', {
			params: { path: { catalog_key: 'personal-jules' } },
			body: {
				policy_config: {
					daily_task_limit: 250,
					window: 'calendar',
					timezone: 'America/Los_Angeles'
				}
			}
		})
	);
});

test('rejects an unknown calendar timezone before saving', async () => {
	const user = userEvent.setup();
	render(AICatalogsView);
	await screen.findByText('Personal Jules');

	await user.click(screen.getByRole('button', { name: 'Quota policy' }));
	await user.selectOptions(screen.getByLabelText('Daily window'), 'calendar');
	await user.clear(screen.getByLabelText('Reset timezone'));
	await user.type(screen.getByLabelText('Reset timezone'), 'Mars/Olympus');
	await user.click(screen.getByRole('button', { name: 'Save quota policy' }));

	await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Unknown timezone: Mars/Olympus'));
	expect(api.PUT).not.toHaveBeenCalled();
});

test('saves the Codex refresh policy as policy config', async () => {
	const user = userEvent.setup();
	render(AICatalogsView);
	await screen.findByText('Personal Codex');

	await user.click(screen.getByRole('button', { name: 'Refresh policy' }));
	await user.clear(screen.getByLabelText('Short cycle (hours)'));
	await user.type(screen.getByLabelText('Short cycle (hours)'), '4');
	await user.click(screen.getByRole('button', { name: 'Save policy' }));

	await waitFor(() =>
		expect(api.PUT).toHaveBeenCalledWith('/api/v1/ai-catalogs/{catalog_key}/policy-config', {
			params: { path: { catalog_key: 'personal-codex' } },
			body: {
				policy_config: {
					short_refresh_enabled: true,
					short_refresh_cycle_minutes: 240,
					long_refresh_cycle_minutes: 10080,
					probe_window_minutes: 10
				}
			}
		})
	);
});

test('assigns only a connector of the catalog provider', async () => {
	const user = userEvent.setup();
	render(AICatalogsView);
	await screen.findByText('Personal Jules');

	await user.click(screen.getByRole('button', { name: 'Connector' }));
	const select = screen.getByLabelText('Provider connector');
	expect(screen.queryByRole('option', { name: 'GitHub token' })).toBeNull();
	await user.selectOptions(select, 'k1');
	await user.click(screen.getByRole('button', { name: 'Save connector' }));

	await waitFor(() =>
		expect(api.PUT).toHaveBeenCalledWith('/api/v1/ai-catalogs/{catalog_key}/connector', {
			params: { path: { catalog_key: 'personal-jules' } },
			body: { connector_id: 'k1' }
		})
	);
});

test('pages through sessions and hides their reconciliation marker', async () => {
	const user = userEvent.setup();
	render(AICatalogsView);
	await screen.findByText('Personal Jules');

	await user.click(screen.getByRole('button', { name: 'Sessions' }));

	expect(await screen.findByText('Weekly hygiene report')).toBeTruthy();
	expect(screen.getByText('in progress')).toBeTruthy();
	expect(screen.getByText('1–1 of 45')).toBeTruthy();
	expect(api.GET).toHaveBeenCalledWith('/api/v1/ai-catalogs/{catalog_key}/sessions', {
		params: { path: { catalog_key: 'personal-jules' }, query: { offset: 0, limit: 20 } }
	});
	expect(screen.getByRole('button', { name: 'Previous' })).toHaveProperty('disabled', true);

	await user.click(screen.getByRole('button', { name: 'Next' }));

	await waitFor(() =>
		expect(api.GET).toHaveBeenCalledWith('/api/v1/ai-catalogs/{catalog_key}/sessions', {
			params: { path: { catalog_key: 'personal-jules' }, query: { offset: 20, limit: 20 } }
		})
	);
});
