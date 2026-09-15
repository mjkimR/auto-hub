<script lang="ts">
	import { onMount } from 'svelte';
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
	import { AICatalogsState, type AICatalog } from './ai-catalogs.svelte';
	import { catalogKinds } from './catalog-kinds';
	import CatalogConnectorDialog from './CatalogConnectorDialog.svelte';
	import CatalogSessionsDialog from './CatalogSessionsDialog.svelte';

	type CatalogDialog = 'policy' | 'connector' | 'sessions';

	const catalogs = new AICatalogsState();
	let selectedKey = $state<string | null>(null);
	let availableAt = $state('');
	let note = $state('');
	let dialogOpen = $state(false);
	let active = $state<{ dialog: CatalogDialog; catalog: AICatalog } | null>(null);

	const PolicyDialog = $derived(
		active?.dialog === 'policy' ? catalogKinds[active.catalog.kind]?.policyDialog : undefined
	);

	function openAvailability(key: string) {
		selectedKey = key;
		availableAt = '';
		note = '';
		dialogOpen = true;
	}

	function openDialog(dialog: CatalogDialog, catalog: AICatalog) {
		active = { dialog, catalog };
	}

	function closeDialog() {
		active = null;
	}

	async function saveAvailability(event: SubmitEvent) {
		event.preventDefault();
		if (selectedKey && (await catalogs.setAvailability(selectedKey, availableAt, note)))
			dialogOpen = false;
	}

	function workSummary(catalog: AICatalog) {
		const runs = `${catalog.held_run_count} queued, dispatching, or implementing run(s)`;
		return catalog.connector_provider
			? `${runs} · ${catalog.open_session_count} open session(s)`
			: runs;
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
				{@const kindUi = catalogKinds[catalog.kind]}
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
								Source: {catalog.availability_source ?? 'not set'} · {workSummary(catalog)}
							</p>
							<p class="mt-1 text-xs text-muted-foreground">
								Concurrency: {catalog.active_dispatch_count} in use / {catalog.effective_concurrency}
								allowed ({catalog.configured_concurrency}
								configured){catalog.availability_state === 'probe' ? ' · recovery probe' : ''}
							</p>
							{#if kindUi?.summary}
								<p class="mt-1 text-xs text-muted-foreground">{kindUi.summary(catalog)}</p>
							{/if}
							{#if catalog.connector_provider}
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
							{#if kindUi}
								<Button
									size="sm"
									variant="outline"
									onclick={() => openDialog('policy', catalog)}
									disabled={catalogs.saving}>{kindUi.policyLabel}</Button
								>
							{/if}
							{#if catalog.connector_provider}
								<Button
									size="sm"
									variant="outline"
									onclick={() => openDialog('connector', catalog)}
									disabled={catalogs.saving}>Connector</Button
								>
								<Button size="sm" variant="outline" onclick={() => openDialog('sessions', catalog)}
									>Sessions</Button
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

{#if active && PolicyDialog}
	<PolicyDialog catalog={active.catalog} {catalogs} onclose={closeDialog} />
{:else if active?.dialog === 'connector'}
	<CatalogConnectorDialog catalog={active.catalog} {catalogs} onclose={closeDialog} />
{:else if active?.dialog === 'sessions'}
	<CatalogSessionsDialog catalog={active.catalog} {catalogs} onclose={closeDialog} />
{/if}
