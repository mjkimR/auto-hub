<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type components } from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { FileCode, RefreshCw, Search, Code2 } from '@lucide/svelte';

	type TaskSpec = components['schemas']['TaskSpecResponse'];

	let specs = $state<TaskSpec[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');

	let filteredSpecs = $derived(
		specs.filter(
			(s) =>
				s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				s.description.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	async function loadSpecs() {
		loading = true;
		try {
			const res = await api.GET('/api/v1/tasks/specs');
			if (res.data && Array.isArray(res.data)) {
				specs = res.data;
			}
		} catch {
			toast.error('Failed to load task specs');
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadSpecs();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Worker Task Specs</h1>
			<p class="text-sm text-muted-foreground">
				Registered executable tasks decorated with @task in backend workers
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadSpecs} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
		</div>
	</div>

	<!-- Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Search task specifications..."
				bind:value={searchQuery}
				class="h-10 pl-9"
			/>
		</div>
	</div>

	<!-- Cards Grid -->
	{#if loading}
		<div class="flex h-40 items-center justify-center text-sm text-muted-foreground">
			Loading task specifications...
		</div>
	{:else if filteredSpecs.length === 0}
		<div
			class="flex h-48 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/80 bg-card/40 p-6 text-center text-muted-foreground"
		>
			<FileCode class="size-8 text-muted-foreground/40" />
			<span>No task specifications registered</span>
		</div>
	{:else}
		<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
			{#each filteredSpecs as spec (spec.name)}
				<Card class="border-border/80 bg-card/60 backdrop-blur-sm">
					<CardHeader class="pb-3">
						<div class="flex items-start justify-between gap-2">
							<div class="flex items-center gap-2">
								<div
									class="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary"
								>
									<Code2 class="size-4" />
								</div>
								<div>
									<CardTitle class="font-mono text-sm font-semibold">{spec.name}</CardTitle>
								</div>
							</div>
							<Badge variant="secondary" class="font-mono text-[10px]">task</Badge>
						</div>
					</CardHeader>
					<CardContent class="space-y-3">
						<p class="text-xs leading-relaxed text-muted-foreground">
							{spec.description || 'No description provided.'}
						</p>

						{#if spec.payload_schema}
							<div class="rounded-lg bg-muted/50 p-3">
								<div
									class="mb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase"
								>
									Payload Schema
								</div>
								<pre class="overflow-x-auto font-mono text-[11px] text-muted-foreground">
									{JSON.stringify(spec.payload_schema, null, 2)}
								</pre>
							</div>
						{/if}
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>
