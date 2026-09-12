<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type components } from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Settings, RefreshCw, Layers } from '@lucide/svelte';

	type SystemConfig = components['schemas']['SystemConfigRead'];

	let configs = $state<SystemConfig[]>([]);
	let loading = $state(true);

	async function loadConfigs() {
		loading = true;
		try {
			const res = await api.GET('/api/v1/system_configs', {});
			if (res.data?.items) {
				configs = res.data.items;
			}
		} catch {
			toast.error('Failed to load system configs');
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadConfigs();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">System Configurations</h1>
			<p class="text-sm text-muted-foreground">
				Global parameters, environment settings, and connector configurations
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadConfigs} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
		</div>
	</div>

	<!-- Cards Grid -->
	{#if loading}
		<div class="flex h-40 items-center justify-center text-sm text-muted-foreground">
			Loading system configs...
		</div>
	{:else if configs.length === 0}
		<div
			class="flex h-48 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/80 bg-card/40 p-6 text-center text-muted-foreground"
		>
			<Settings class="size-8 text-muted-foreground/40" />
			<span>No system configurations defined</span>
		</div>
	{:else}
		<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
			{#each configs as cfg (cfg.id)}
				<Card class="border-border/80 bg-card/60 backdrop-blur-sm">
					<CardHeader class="pb-3">
						<div class="flex items-center gap-2.5">
							<div
								class="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary"
							>
								<Layers class="size-4" />
							</div>
							<CardTitle class="text-base font-semibold">{cfg.name}</CardTitle>
						</div>
					</CardHeader>
					<CardContent class="space-y-3">
						<div class="rounded-lg bg-muted/50 p-3">
							<pre class="overflow-x-auto font-mono text-xs text-muted-foreground">
								{JSON.stringify(cfg.data, null, 2)}
							</pre>
						</div>
						<div class="flex items-center justify-between text-[11px] text-muted-foreground">
							<span>Updated: {new Date(cfg.updated_at).toLocaleDateString()}</span>
							<span class="font-mono text-[10px] opacity-70">ID: {cfg.id.slice(0, 8)}...</span>
						</div>
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>
