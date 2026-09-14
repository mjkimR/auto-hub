<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type components } from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import {
		Table,
		TableHeader,
		TableBody,
		TableRow,
		TableHead,
		TableCell
	} from '$lib/components/ui/table';
	import {
		History,
		RefreshCw,
		Search,
		CheckCircle2,
		XCircle,
		Clock,
		AlertTriangle
	} from '@lucide/svelte';

	type ScheduleJob = components['schemas']['ScheduleJobRead'];

	let jobs = $state<ScheduleJob[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');

	let filteredJobs = $derived(
		jobs.filter(
			(j) =>
				j.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				j.status.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	async function loadJobs() {
		loading = true;
		try {
			const res = await api.GET('/api/v1/schedule_jobs', {});
			if (res.data?.items) {
				jobs = res.data.items;
			}
		} catch {
			toast.error('Failed to load schedule jobs');
		} finally {
			loading = false;
		}
	}

	function getStatusVariant(status: string) {
		switch (status) {
			case 'success':
				return {
					class: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
					icon: CheckCircle2
				};
			case 'failure':
				return { class: 'bg-destructive/15 text-destructive', icon: XCircle };
			case 'pending':
				return { class: 'bg-amber-500/15 text-amber-600 dark:text-amber-400', icon: Clock };
			default:
				return { class: 'bg-secondary text-secondary-foreground', icon: AlertTriangle };
		}
	}

	onMount(() => {
		loadJobs();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Execution History</h1>
			<p class="text-sm text-muted-foreground">Execution audit logs and real-time job run states</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadJobs} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
		</div>
	</div>

	<!-- Controls & Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Filter jobs by name or status..."
				bind:value={searchQuery}
				class="h-10 pl-9"
			/>
		</div>
	</div>

	<!-- Table Container -->
	<div
		class="overflow-hidden rounded-xl border border-border/80 bg-card/60 shadow-sm backdrop-blur-sm"
	>
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead class="w-[200px]">Job Name</TableHead>
					<TableHead class="w-[140px]">Status</TableHead>
					<TableHead class="w-[180px]">Started At</TableHead>
					<TableHead class="w-[180px]">Finished At</TableHead>
					<TableHead>Dispatcher Run ID</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading}
					<TableRow>
						<TableCell colspan={5} class="h-32 text-center text-muted-foreground">
							Loading job runs...
						</TableCell>
					</TableRow>
				{:else if filteredJobs.length === 0}
					<TableRow>
						<TableCell colspan={5} class="h-32 text-center text-muted-foreground">
							<div class="flex flex-col items-center justify-center gap-2">
								<History class="size-8 text-muted-foreground/40" />
								<span>No execution logs recorded</span>
							</div>
						</TableCell>
					</TableRow>
				{:else}
					{#each filteredJobs as job (job.id)}
						{@const st = getStatusVariant(job.status)}
						<TableRow class="transition-colors hover:bg-muted/40">
							<TableCell class="font-semibold text-foreground">
								{job.name}
							</TableCell>
							<TableCell>
								<span
									class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium {st.class}"
								>
									<st.icon class="size-3.5" />
									<span class="capitalize">{job.status}</span>
								</span>
							</TableCell>
							<TableCell class="font-mono text-xs text-muted-foreground">
								{new Date(job.started_at).toLocaleString()}
							</TableCell>
							<TableCell class="font-mono text-xs text-muted-foreground">
								{job.finished_at ? new Date(job.finished_at).toLocaleString() : '—'}
							</TableCell>
							<TableCell class="font-mono text-xs text-muted-foreground">
								{job.dispatcher_run_id || 'manual'}
							</TableCell>
						</TableRow>
					{/each}
				{/if}
			</TableBody>
		</Table>
	</div>
</div>
