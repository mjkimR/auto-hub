<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogFooter,
		DialogHeader,
		DialogTitle
	} from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';
	import { Bot, Clock3, RefreshCw, ShieldAlert } from '@lucide/svelte';
	import {
		AICatalogsState,
		codexWindowConfig,
		dailyQuotaConfig,
		isKnownTimezone,
		type AICatalog,
		type DailyQuotaConfig
	} from './ai-catalogs.svelte';

	const selectClass = 'h-9 rounded-md border border-input bg-transparent px-3 text-sm';

	const catalogs = new AICatalogsState();
	let selectedKey = $state<string | null>(null);
	let availableAt = $state('');
	let note = $state('');
	let dialogOpen = $state(false);
	let policyKey = $state<string | null>(null);
	let shortRefreshEnabled = $state(true);
	let shortRefreshHours = $state('5');
	let longRefreshDays = $state('7');
	let probeWindowMinutes = $state(10);
	let policyDialogOpen = $state(false);
	let quotaKey = $state<string | null>(null);
	let dailyTaskLimit = $state('100');
	let quotaWindow = $state<DailyQuotaConfig['window']>('rolling');
	let quotaTimezone = $state('UTC');
	let quotaDialogOpen = $state(false);
	let connectorKey = $state<string | null>(null);
	let connectorId = $state('');
	let connectorDialogOpen = $state(false);

	const julesConnectors = $derived(catalogs.connectors.filter((item) => item.provider === 'jules'));

	function openAvailability(key: string) {
		selectedKey = key;
		availableAt = '';
		note = '';
		dialogOpen = true;
	}

	function openRefreshPolicy(catalog: AICatalog) {
		const config = codexWindowConfig(catalog);
		policyKey = catalog.key;
		shortRefreshEnabled = config.short_refresh_enabled;
		shortRefreshHours = String(config.short_refresh_cycle_minutes / 60);
		longRefreshDays = String(config.long_refresh_cycle_minutes / (60 * 24));
		probeWindowMinutes = config.probe_window_minutes;
		policyDialogOpen = true;
	}

	function openDailyQuota(catalog: AICatalog) {
		const config = dailyQuotaConfig(catalog);
		quotaKey = catalog.key;
		dailyTaskLimit = String(config?.daily_task_limit ?? 100);
		quotaWindow = config?.window ?? 'rolling';
		quotaTimezone = config?.timezone ?? 'UTC';
		quotaDialogOpen = true;
	}

	function openConnector(catalog: AICatalog) {
		connectorKey = catalog.key;
		connectorId = catalog.connector_id ?? '';
		connectorDialogOpen = true;
	}

	async function saveAvailability(event: SubmitEvent) {
		event.preventDefault();
		if (selectedKey && (await catalogs.setAvailability(selectedKey, availableAt, note)))
			dialogOpen = false;
	}

	async function saveRefreshPolicy(event: SubmitEvent) {
		event.preventDefault();
		const shortHours = Number(shortRefreshHours);
		const longDays = Number(longRefreshDays);
		if (
			!policyKey ||
			!Number.isFinite(shortHours) ||
			shortHours <= 0 ||
			!Number.isFinite(longDays) ||
			longDays <= 0
		) {
			return;
		}
		const config = {
			short_refresh_enabled: shortRefreshEnabled,
			short_refresh_cycle_minutes: Math.round(shortHours * 60),
			long_refresh_cycle_minutes: Math.round(longDays * 24 * 60),
			probe_window_minutes: probeWindowMinutes
		};
		if (await catalogs.updatePolicyConfig(policyKey, config)) policyDialogOpen = false;
	}

	async function saveDailyQuota(event: SubmitEvent) {
		event.preventDefault();
		const limit = Number(dailyTaskLimit);
		if (!quotaKey || !Number.isInteger(limit) || limit < 1) return;
		const timezone = quotaTimezone.trim() || 'UTC';
		if (quotaWindow === 'calendar' && !isKnownTimezone(timezone)) {
			toast.error(`Unknown timezone: ${timezone}`);
			return;
		}
		const config = { daily_task_limit: limit, window: quotaWindow, timezone };
		if (await catalogs.updatePolicyConfig(quotaKey, config)) quotaDialogOpen = false;
	}

	async function saveConnector(event: SubmitEvent) {
		event.preventDefault();
		if (connectorKey && (await catalogs.setConnector(connectorKey, connectorId || null)))
			connectorDialogOpen = false;
	}

	function dailyQuotaSummary(catalog: AICatalog) {
		const config = dailyQuotaConfig(catalog);
		if (!config) return 'Daily quota: not configured — dispatch is blocked until it is set';
		const reset =
			config.window === 'calendar' ? `resets at midnight ${config.timezone}` : 'rolling 24 hours';
		return `Daily quota: ${config.daily_task_limit} tasks · ${reset}`;
	}

	function connectorSummary(catalog: AICatalog) {
		if (!catalog.connector_id) return 'Connector: not assigned — sessions cannot start';
		const connector = catalogs.connectors.find((item) => item.id === catalog.connector_id);
		return `Connector: ${connector?.name ?? 'unknown connector'}`;
	}

	function stateLabel(value: string) {
		return value.replace('_', ' ');
	}

	onMount(() => catalogs.load());
</script>

<div class="space-y-6">
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">AI Catalogs</h1>
			<p class="text-sm text-muted-foreground">
				Each catalog is a global AI gateway: it owns quota holds and concurrency for all of its
				work.
			</p>
		</div>
		<Button
			variant="outline"
			size="sm"
			onclick={() => catalogs.load()}
			disabled={catalogs.loading}
			class="gap-2"
		>
			<RefreshCw class="size-4 {catalogs.loading ? 'animate-spin' : ''}" /> Refresh
		</Button>
	</div>

	{#if catalogs.loading && catalogs.items.length === 0}
		<div class="flex h-40 items-center justify-center text-sm text-muted-foreground">
			Loading AI catalogs…
		</div>
	{:else}
		<div class="grid gap-5 lg:grid-cols-2">
			{#each catalogs.items as catalog (catalog.id)}
				<Card class="border-border/80 bg-card/60">
					<CardHeader class="pb-3">
						<div class="flex items-start justify-between gap-4">
							<div class="flex gap-3">
								<div
									class="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary"
								>
									<Bot class="size-5" />
								</div>
								<div>
									<CardTitle class="text-base">{catalog.name}</CardTitle>
									<p class="mt-1 text-xs text-muted-foreground">
										{catalog.kind} · {catalog.adapter}
									</p>
								</div>
							</div>
							<Badge variant={catalog.availability_state === 'normal' ? 'default' : 'secondary'}
								>{stateLabel(catalog.availability_state)}</Badge
							>
						</div>
					</CardHeader>
					<CardContent class="space-y-4 text-sm">
						<div class="rounded-lg bg-muted/50 p-3">
							<div class="flex items-center gap-2 font-medium">
								<Clock3 class="size-4" />
								{catalog.available_at
									? `Available ${new Date(catalog.available_at).toLocaleString()}`
									: 'Available now'}
							</div>
							<p class="mt-1 text-xs text-muted-foreground">
								Source: {catalog.availability_source ?? 'not set'} · {catalog.held_run_count} queued,
								dispatching, or implementing run(s)
							</p>
							<p class="mt-1 text-xs text-muted-foreground">
								Concurrency: {catalog.active_dispatch_count} in use / {catalog.effective_concurrency}
								allowed ({catalog.configured_concurrency}
								configured){catalog.availability_state === 'probe' ? ' · recovery probe' : ''}
							</p>
							{#if catalog.kind === 'jules'}
								<p class="mt-1 text-xs text-muted-foreground">{dailyQuotaSummary(catalog)}</p>
								<p class="mt-1 text-xs text-muted-foreground">{connectorSummary(catalog)}</p>
							{/if}
							{#if catalog.availability_note}<p class="mt-2 text-xs text-muted-foreground">
									{catalog.availability_note}
								</p>{/if}
						</div>
						<div class="flex flex-wrap gap-2">
							<Button
								size="sm"
								onclick={() => openAvailability(catalog.key)}
								disabled={catalogs.saving}>Set refresh time</Button
							>
							{#if catalog.kind === 'codex'}
								<Button
									size="sm"
									variant="outline"
									onclick={() => openRefreshPolicy(catalog)}
									disabled={catalogs.saving}>Refresh policy</Button
								>
							{:else if catalog.kind === 'jules'}
								<Button
									size="sm"
									variant="outline"
									onclick={() => openDailyQuota(catalog)}
									disabled={catalogs.saving}>Quota policy</Button
								>
								<Button
									size="sm"
									variant="outline"
									onclick={() => openConnector(catalog)}
									disabled={catalogs.saving}>Connector</Button
								>
							{/if}
							{#if catalog.available_at}<Button
									size="sm"
									variant="outline"
									onclick={() => catalogs.clearAvailability(catalog.key)}
									disabled={catalogs.saving}>Clear hold</Button
								>{/if}
							<Button
								size="sm"
								variant="ghost"
								onclick={() => catalogs.setEnabled(catalog.key, !catalog.enabled)}
								disabled={catalogs.saving}>{catalog.enabled ? 'Disable' : 'Enable'}</Button
							>
						</div>
						{#if !catalog.enabled}<p class="flex items-center gap-1 text-xs text-destructive">
								<ShieldAlert class="size-3" /> Dispatch is disabled for this catalog.
							</p>{/if}
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>

<Dialog bind:open={dialogOpen}>
	<DialogContent>
		<DialogHeader
			><DialogTitle>Set catalog refresh time</DialogTitle><DialogDescription
				>This global hold affects all work assigned to this catalog. Enter the reset time in your
				local timezone.</DialogDescription
			></DialogHeader
		>
		<form onsubmit={saveAvailability} class="space-y-4">
			<Input type="datetime-local" bind:value={availableAt} required />
			<Input bind:value={note} maxlength={500} placeholder="Optional operator note" />
			<DialogFooter
				><Button type="button" variant="outline" onclick={() => (dialogOpen = false)}>Cancel</Button
				><Button type="submit" disabled={catalogs.saving}>Save global hold</Button></DialogFooter
			>
		</form>
	</DialogContent>
</Dialog>

<Dialog bind:open={policyDialogOpen}>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Refresh policy</DialogTitle>
			<DialogDescription>
				A quota block waits one cycle from the first task of the current usage window, plus the
				catalog's safety jitter; after two failed short cycles, the long cycle is used.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={saveRefreshPolicy} class="space-y-4">
			<label class="flex items-center gap-2 text-sm font-medium">
				<input type="checkbox" bind:checked={shortRefreshEnabled} />
				Use short refresh cycle
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Short cycle (hours)
				<Input
					type="number"
					min="0.1"
					step="0.1"
					bind:value={shortRefreshHours}
					disabled={!shortRefreshEnabled}
					required
				/>
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Long cycle (days)
				<Input type="number" min="0.1" step="0.1" bind:value={longRefreshDays} required />
			</label>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (policyDialogOpen = false)}
					>Cancel</Button
				>
				<Button type="submit" disabled={catalogs.saving}>Save policy</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>

<Dialog bind:open={quotaDialogOpen}>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Quota policy</DialogTitle>
			<DialogDescription>
				The hub counts every admitted task. When the day's limit is reached it holds the catalog
				until the window has room again, plus the catalog's safety jitter. Concurrency uses the
				configured limit.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={saveDailyQuota} class="space-y-4">
			<label class="grid gap-1 text-sm font-medium">
				Daily task limit
				<Input type="number" min="1" step="1" bind:value={dailyTaskLimit} required />
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Daily window
				<select bind:value={quotaWindow} class={selectClass}>
					<option value="rolling">Rolling 24 hours</option>
					<option value="calendar">Calendar day</option>
				</select>
			</label>
			{#if quotaWindow === 'calendar'}
				<label class="grid gap-1 text-sm font-medium">
					Reset timezone
					<Input
						bind:value={quotaTimezone}
						placeholder="UTC or an IANA name like America/Los_Angeles"
					/>
				</label>
			{/if}
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (quotaDialogOpen = false)}
					>Cancel</Button
				>
				<Button type="submit" disabled={catalogs.saving}>Save quota policy</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>

<Dialog bind:open={connectorDialogOpen}>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Catalog connector</DialogTitle>
			<DialogDescription>
				Sessions on this catalog authenticate with the selected Jules connector's API key.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={saveConnector} class="space-y-4">
			<label class="grid gap-1 text-sm font-medium">
				Jules connector
				<select bind:value={connectorId} class={selectClass}>
					<option value="">No connector</option>
					{#each julesConnectors as connector (connector.id)}
						<option value={connector.id}
							>{connector.name}{connector.enabled ? '' : ' (disabled)'}</option
						>
					{/each}
				</select>
			</label>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (connectorDialogOpen = false)}
					>Cancel</Button
				>
				<Button type="submit" disabled={catalogs.saving}>Save connector</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
