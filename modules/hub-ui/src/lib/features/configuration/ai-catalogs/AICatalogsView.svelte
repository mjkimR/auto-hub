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
	import { AICatalogsState } from './ai-catalogs.svelte';

	const catalogs = new AICatalogsState();
	let selectedKey = $state<string | null>(null);
	let availableAt = $state('');
	let note = $state('');
	let dialogOpen = $state(false);
	let policyKey = $state<string | null>(null);
	let shortRefreshEnabled = $state(true);
	let shortRefreshHours = $state('5');
	let longRefreshDays = $state('7');
	let policyDialogOpen = $state(false);

	function openAvailability(key: string) {
		selectedKey = key;
		availableAt = '';
		note = '';
		dialogOpen = true;
	}

	function openRefreshPolicy(catalog: (typeof catalogs.items)[number]) {
		policyKey = catalog.key;
		shortRefreshEnabled = catalog.short_refresh_enabled;
		shortRefreshHours = String(catalog.short_refresh_cycle_minutes / 60);
		longRefreshDays = String(catalog.long_refresh_cycle_minutes / (60 * 24));
		policyDialogOpen = true;
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
		if (
			await catalogs.updateRefreshPolicy(
				policyKey,
				shortRefreshEnabled,
				Math.round(shortHours * 60),
				Math.round(longDays * 24 * 60)
			)
		)
			policyDialogOpen = false;
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
				Each catalog is a global AI gateway: it owns quota holds, recovery probes, and concurrency.
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
								Source: {catalog.availability_source ?? 'not set'} · {catalog.held_run_count} active run(s)
								affected
							</p>
							<p class="mt-1 text-xs text-muted-foreground">
								Concurrency: {catalog.effective_concurrency} active now / {catalog.configured_concurrency}
								configured{catalog.availability_state === 'probe' ? ' (recovery probe)' : ''}
							</p>
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
							<Button
								size="sm"
								variant="outline"
								onclick={() => openRefreshPolicy(catalog)}
								disabled={catalogs.saving}>Refresh policy</Button
							>
							{#if catalog.availability_state === 'quota_blocked'}<Button
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
				>This global hold affects every pipeline run assigned to this catalog. Enter the reset time
				in your local timezone.</DialogDescription
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
				A quota block waits from the most recent catalog refresh. Each cycle includes a fixed
				10-minute safety jitter; after two failed short cycles, the long cycle is used.
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
