<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type components } from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Table,
		TableHeader,
		TableBody,
		TableRow,
		TableHead,
		TableCell
	} from '$lib/components/ui/table';
	import {
		Dialog,
		DialogContent,
		DialogHeader,
		DialogTitle,
		DialogFooter,
		DialogDescription
	} from '$lib/components/ui/dialog';
	import {
		Workflow,
		RefreshCw,
		Search,
		GitPullRequest,
		GitBranch,
		Clock,
		AlertCircle,
		CheckCircle2,
		PauseCircle,
		ExternalLink,
		Layers,
		History,
		Key,
		ShieldCheck
	} from '@lucide/svelte';

	type PipelineRun = components['schemas']['PipelineRunRead'];
	type ExecutionAttempt = components['schemas']['ExecutionAttemptRead'];
	type Project = components['schemas']['ProjectRead'];
	type RunState = components['schemas']['PipelineRunState'];

	let runs = $state<PipelineRun[]>([]);
	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let selectedProjectId = $state<string>('');
	let selectedState = $state<string>('');

	// Attempt detail dialog
	let isAttemptsOpen = $state(false);
	let loadingAttempts = $state(false);
	let selectedRun = $state<PipelineRun | null>(null);
	let attempts = $state<ExecutionAttempt[]>([]);

	let filteredRuns = $derived(
		runs.filter((r) => {
			const matchesProject = !selectedProjectId || r.project_id === selectedProjectId;
			const matchesState = !selectedState || r.state === selectedState;
			const matchesSearch =
				!searchQuery ||
				r.linear_issue_identifier.toLowerCase().includes(searchQuery.toLowerCase()) ||
				(r.linear_issue_snapshot?.title &&
					r.linear_issue_snapshot.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
				r.branch.toLowerCase().includes(searchQuery.toLowerCase());
			return matchesProject && matchesState && matchesSearch;
		})
	);

	function getProjectName(projectId: string): string {
		const found = projects.find((p) => p.id === projectId);
		return found ? found.name : projectId.slice(0, 8);
	}

	async function loadProjects() {
		try {
			const res = await api.GET('/api/v1/projects', {});
			if (res.data?.items) {
				projects = res.data.items;
			}
		} catch {
			// ignore
		}
	}

	async function loadRuns() {
		loading = true;
		try {
			const params: { query?: { project_id?: string; limit: number } } = {
				query: { limit: 50 }
			};
			if (selectedProjectId) {
				params.query!.project_id = selectedProjectId;
			}
			const res = await api.GET('/api/v1/pipeline-runs', params);
			if (res.data?.items) {
				runs = res.data.items;
			}
		} catch {
			toast.error('Failed to load pipeline runs');
		} finally {
			loading = false;
		}
	}

	async function openAttempts(run: PipelineRun) {
		selectedRun = run;
		attempts = [];
		isAttemptsOpen = true;
		loadingAttempts = true;
		try {
			const res = await api.GET('/api/v1/pipeline-runs/{run_id}/attempts', {
				params: { path: { run_id: run.id } }
			});
			if (res.data?.items) {
				attempts = res.data.items;
			}
		} catch {
			toast.error('Failed to load execution attempts');
		} finally {
			loadingAttempts = false;
		}
	}

	function getStateBadgeClass(state: RunState): string {
		switch (state) {
			case 'queued':
				return 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30';
			case 'dispatching':
				return 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30';
			case 'implementing':
				return 'bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30';
			case 'awaiting_ci':
				return 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30';
			case 'completed':
				return 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30';
			case 'failed':
				return 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30';
			case 'paused':
				return 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30';
			case 'canceled':
			default:
				return 'bg-muted text-muted-foreground border-border';
		}
	}

	onMount(() => {
		loadProjects();
		loadRuns();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Pipeline Runs</h1>
			<p class="text-sm text-muted-foreground">
				Durable issue implementation lifecycle, attempt execution history, and CI status
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadRuns} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
		</div>
	</div>

	<!-- Controls & Filters -->
	<div class="flex flex-wrap items-center gap-3">
		<div class="relative min-w-[200px] flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Search issue ID, title, branch..."
				bind:value={searchQuery}
				class="h-10 pl-9"
			/>
		</div>

		<!-- Project selector -->
		<select
			bind:value={selectedProjectId}
			onchange={loadRuns}
			class="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:ring-1 focus:ring-ring"
		>
			<option value="">All Projects</option>
			{#each projects as project (project.id)}
				<option value={project.id}>{project.name}</option>
			{/each}
		</select>

		<!-- State selector -->
		<select
			bind:value={selectedState}
			class="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:ring-1 focus:ring-ring"
		>
			<option value="">All States</option>
			<option value="queued">Queued</option>
			<option value="dispatching">Dispatching</option>
			<option value="implementing">Implementing</option>
			<option value="awaiting_ci">Awaiting CI</option>
			<option value="completed">Completed</option>
			<option value="failed">Failed</option>
			<option value="paused">Paused</option>
			<option value="canceled">Canceled</option>
		</select>
	</div>

	<!-- Runs Table -->
	<div
		class="overflow-hidden rounded-xl border border-border/80 bg-card/60 shadow-xs backdrop-blur-xs"
	>
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead class="w-[180px]">Linear Issue</TableHead>
					<TableHead class="w-[160px]">Project</TableHead>
					<TableHead class="w-[130px]">State</TableHead>
					<TableHead>Branch & Pull Request</TableHead>
					<TableHead class="w-[160px]">Lease Status</TableHead>
					<TableHead class="w-[140px]">Created</TableHead>
					<TableHead class="w-[90px] text-right">Attempts</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading}
					<TableRow>
						<TableCell colspan={7} class="h-32 text-center text-muted-foreground">
							Loading pipeline runs...
						</TableCell>
					</TableRow>
				{:else if filteredRuns.length === 0}
					<TableRow>
						<TableCell colspan={7} class="h-32 text-center text-muted-foreground">
							<div class="flex flex-col items-center justify-center gap-2">
								<Workflow class="size-8 text-muted-foreground/40" />
								<span>No pipeline runs found</span>
							</div>
						</TableCell>
					</TableRow>
				{:else}
					{#each filteredRuns as run (run.id)}
						<TableRow class="transition-colors hover:bg-muted/40">
							<TableCell>
								<div class="space-y-1">
									<div class="flex items-center gap-1.5">
										<Badge
											variant="outline"
											class="border-indigo-500/30 bg-indigo-500/10 font-mono text-xs text-indigo-500"
										>
											{run.linear_issue_identifier}
										</Badge>
										{#if run.linear_issue_snapshot?.url}
											<a
												href={run.linear_issue_snapshot.url}
												target="_blank"
												rel="noreferrer"
												class="text-muted-foreground hover:text-foreground"
												title="Open in Linear"
											>
												<ExternalLink class="size-3" />
											</a>
										{/if}
									</div>
									<div class="line-clamp-1 text-xs font-medium text-foreground">
										{run.linear_issue_snapshot?.title || 'No title'}
									</div>
								</div>
							</TableCell>

							<TableCell>
								<div class="flex flex-col gap-0.5">
									<span class="text-sm font-semibold text-foreground"
										>{getProjectName(run.project_id)}</span
									>
									<span class="font-mono text-[10px] text-muted-foreground"
										>run rev {run.revision}</span
									>
								</div>
							</TableCell>

							<TableCell>
								<Badge
									variant="outline"
									class="gap-1.5 font-medium {getStateBadgeClass(run.state)}"
								>
									{#if run.state === 'implementing' || run.state === 'dispatching'}
										<span class="size-1.5 animate-pulse rounded-full bg-current"></span>
									{:else if run.state === 'completed'}
										<CheckCircle2 class="size-3" />
									{:else if run.state === 'failed'}
										<AlertCircle class="size-3" />
									{:else if run.state === 'paused'}
										<PauseCircle class="size-3" />
									{/if}
									<span class="capitalize">{run.state.replace('_', ' ')}</span>
								</Badge>
							</TableCell>

							<TableCell>
								<div class="space-y-1 font-mono text-xs">
									<div class="flex items-center gap-1 text-muted-foreground">
										<GitBranch class="size-3 shrink-0" />
										<span class="truncate">{run.branch}</span>
									</div>
									{#if run.pull_url}
										<div class="flex items-center gap-1 text-primary">
											<GitPullRequest class="size-3 shrink-0" />
											<a
												href={run.pull_url}
												target="_blank"
												rel="noreferrer"
												class="hover:underline"
											>
												PR #{run.pull_number || ''}
											</a>
										</div>
									{:else}
										<span class="text-[11px] text-muted-foreground/60">No PR yet</span>
									{/if}
								</div>
							</TableCell>

							<TableCell>
								{#if run.lease_owner}
									<div class="space-y-0.5 text-xs">
										<div class="flex items-center gap-1 text-foreground">
											<ShieldCheck class="size-3 text-emerald-500" />
											<span class="truncate">{run.lease_owner}</span>
										</div>
										{#if run.lease_expires_at}
											<div class="font-mono text-[10px] text-muted-foreground">
												expires {new Date(run.lease_expires_at).toLocaleTimeString()}
											</div>
										{/if}
									</div>
								{:else}
									<span class="text-xs text-muted-foreground">Idle (unleased)</span>
								{/if}
							</TableCell>

							<TableCell class="text-xs text-muted-foreground">
								{new Date(run.created_at).toLocaleString()}
							</TableCell>

							<TableCell class="text-right">
								<Button
									variant="ghost"
									size="icon"
									onclick={() => openAttempts(run)}
									class="size-8 text-muted-foreground hover:text-foreground"
									title="View Attempt History"
									aria-label="View Attempt History"
								>
									<History class="size-4" />
								</Button>
							</TableCell>
						</TableRow>
					{/each}
				{/if}
			</TableBody>
		</Table>
	</div>

	<!-- Attempts History Dialog -->
	<Dialog bind:open={isAttemptsOpen}>
		<DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[650px]">
			<DialogHeader>
				<DialogTitle class="flex items-center gap-2">
					<History class="size-5 text-primary" />
					Execution Attempts
				</DialogTitle>
				<DialogDescription>
					Immutable snapshots, correlation keys, and external execution outcomes.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-4 py-2">
				{#if selectedRun}
					<div class="rounded-lg border border-border/80 bg-muted/20 p-3 text-xs">
						<div class="flex items-center justify-between font-semibold text-foreground">
							<span class="flex items-center gap-1.5 font-mono text-indigo-500">
								<Layers class="size-3.5" />
								{selectedRun.linear_issue_identifier}: {selectedRun.linear_issue_snapshot?.title}
							</span>
							<Badge variant="outline" class="font-mono">{selectedRun.state}</Badge>
						</div>
						<div class="mt-2 grid grid-cols-2 gap-2 text-muted-foreground">
							<div>
								Run ID: <span class="font-mono text-foreground"
									>{selectedRun.id.slice(0, 8)}...</span
								>
							</div>
							<div>
								Working Branch: <span class="font-mono text-foreground">{selectedRun.branch}</span>
							</div>
						</div>
					</div>
				{/if}

				{#if loadingAttempts}
					<div class="flex h-32 items-center justify-center text-muted-foreground">
						<RefreshCw class="size-5 animate-spin" />
						<span class="ml-2 text-sm">Loading attempts...</span>
					</div>
				{:else if attempts.length === 0}
					<div
						class="flex flex-col items-center justify-center gap-2 rounded-lg border border-border/70 p-6 text-center text-muted-foreground"
					>
						<Clock class="size-8 text-muted-foreground/40" />
						<span>No execution attempts recorded yet</span>
						<p class="text-xs text-muted-foreground/80">
							An attempt is prepared when the dispatcher acquires a lease for this run.
						</p>
					</div>
				{:else}
					<div class="space-y-3">
						{#each attempts as attempt (attempt.id)}
							<div class="space-y-2.5 rounded-lg border border-border/80 bg-card p-3.5 shadow-xs">
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-2">
										<Badge variant="secondary" class="font-mono text-xs">
											Attempt #{attempt.attempt_number}
										</Badge>
										<span class="text-xs font-semibold text-muted-foreground uppercase">
											{attempt.kind}
										</span>
									</div>
									<Badge variant="outline" class="capitalize">
										{attempt.state}
									</Badge>
								</div>

								<div class="space-y-1 text-xs">
									<div class="flex items-center gap-1.5 text-muted-foreground">
										<Key class="size-3 shrink-0" />
										<span>Idempotency Key:</span>
										<span class="font-mono text-foreground">{attempt.idempotency_key}</span>
									</div>
									<div class="flex items-center gap-1.5 text-muted-foreground">
										<span>Digest:</span>
										<span class="font-mono text-[11px] text-foreground"
											>{attempt.request_digest.slice(0, 16)}...</span
										>
									</div>
									{#if attempt.conversation_url}
										<div class="flex items-center gap-1.5 pt-1 text-primary">
											<ExternalLink class="size-3 shrink-0" />
											<a
												href={attempt.conversation_url}
												target="_blank"
												rel="noreferrer"
												class="hover:underline"
											>
												Codex Cloud Conversation
											</a>
										</div>
									{/if}
									{#if attempt.failure_code || attempt.failure_detail}
										<div
											class="mt-2 rounded-md border border-rose-500/30 bg-rose-500/10 p-2 text-rose-600 dark:text-rose-400"
										>
											<div class="font-semibold">{attempt.failure_code || 'Execution Error'}</div>
											<div class="text-[11px]">{attempt.failure_detail}</div>
										</div>
									{/if}
								</div>

								<div
									class="flex items-center justify-between border-t border-border/50 pt-2 text-[10px] text-muted-foreground"
								>
									<span>Created: {new Date(attempt.created_at).toLocaleString()}</span>
									{#if attempt.finished_at}
										<span>Finished: {new Date(attempt.finished_at).toLocaleTimeString()}</span>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (isAttemptsOpen = false)}>
					Close
				</Button>
			</DialogFooter>
		</DialogContent>
	</Dialog>
</div>
