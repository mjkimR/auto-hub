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
	import { ExecutionProvidersState } from './execution-providers.svelte';

	const providers = new ExecutionProvidersState();
	let selectedKey = $state<string | null>(null);
	let availableAt = $state('');
	let note = $state('');
	let dialogOpen = $state(false);

	function openAvailability(key: string) {
		selectedKey = key;
		availableAt = '';
		note = '';
		dialogOpen = true;
	}

	async function saveAvailability(event: SubmitEvent) {
		event.preventDefault();
		if (selectedKey && (await providers.setAvailability(selectedKey, availableAt, note)))
			dialogOpen = false;
	}

	function stateLabel(value: string) {
		return value.replace('_', ' ');
	}

	onMount(() => providers.load());
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
			onclick={() => providers.load()}
			disabled={providers.loading}
			class="gap-2"
		>
			<RefreshCw class="size-4 {providers.loading ? 'animate-spin' : ''}" /> Refresh
		</Button>
	</div>

	{#if providers.loading && providers.items.length === 0}
		<div class="flex h-40 items-center justify-center text-sm text-muted-foreground">
			Loading providers…
		</div>
	{:else}
		<div class="grid gap-5 lg:grid-cols-2">
			{#each providers.items as provider (provider.id)}
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
									<CardTitle class="text-base">{provider.name}</CardTitle>
									<p class="mt-1 text-xs text-muted-foreground">
										{provider.kind} · {provider.adapter}
									</p>
								</div>
							</div>
							<Badge variant={provider.availability_state === 'normal' ? 'default' : 'secondary'}
								>{stateLabel(provider.availability_state)}</Badge
							>
						</div>
					</CardHeader>
					<CardContent class="space-y-4 text-sm">
						<div class="rounded-lg bg-muted/50 p-3">
							<div class="flex items-center gap-2 font-medium">
								<Clock3 class="size-4" />
								{provider.available_at
									? `Available ${new Date(provider.available_at).toLocaleString()}`
									: 'Available now'}
							</div>
							<p class="mt-1 text-xs text-muted-foreground">
								Source: {provider.availability_source ?? 'not set'} · {provider.held_run_count} active
								run(s) affected
							</p>
							<p class="mt-1 text-xs text-muted-foreground">
								Concurrency: {provider.effective_concurrency} active now / {provider.configured_concurrency}
								configured{provider.availability_state === 'probe' ? ' (recovery probe)' : ''}
							</p>
							{#if provider.availability_note}<p class="mt-2 text-xs text-muted-foreground">
									{provider.availability_note}
								</p>{/if}
						</div>
						<div class="flex flex-wrap gap-2">
							<Button
								size="sm"
								onclick={() => openAvailability(provider.key)}
								disabled={providers.saving}>Set refresh time</Button
							>
							{#if provider.availability_state === 'quota_blocked'}<Button
									size="sm"
									variant="outline"
									onclick={() => providers.clearAvailability(provider.key)}
									disabled={providers.saving}>Clear hold</Button
								>{/if}
							<Button
								size="sm"
								variant="ghost"
								onclick={() => providers.setEnabled(provider.key, !provider.enabled)}
								disabled={providers.saving}>{provider.enabled ? 'Disable' : 'Enable'}</Button
							>
						</div>
						{#if !provider.enabled}<p class="flex items-center gap-1 text-xs text-destructive">
								<ShieldAlert class="size-3" /> Dispatch is disabled for this provider.
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
				><Button type="submit" disabled={providers.saving}>Save global hold</Button></DialogFooter
			>
		</form>
	</DialogContent>
</Dialog>
