<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api, type components } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import {
		FolderKanban,
		CalendarClock,
		History,
		Activity,
		CheckCircle2,
		AlertCircle,
		RefreshCw,
		Workflow,
		KeyRound,
		GitBranch,
		ArrowRight,
		Radio
	} from '@lucide/svelte';

	type PipelineRun = components['schemas']['PipelineRunRead'];
	type ScheduleJob = components['schemas']['ScheduleJobRead'];
	type Connector = components['schemas']['ConnectorRead'];
	type Project = components['schemas']['ProjectRead'];
	type RunState = components['schemas']['PipelineRunState'];

	let loading = $state(true);
	let healthStatus = $state<'online' | 'offline' | 'checking'>('checking');
	let dbStatus = $state<'connected' | 'error' | 'unknown'>('unknown');

	// Metrics
	let projectCount = $state(0);
	let scheduleCount = $state(0);
	let jobCount = $state(0);
	let taskSpecCount = $state(0);

	// Pipeline runs metrics
	let totalRuns = $state(0);
	let activeRuns = $state(0);
	let awaitingCiRuns = $state(0);
	let completedRuns = $state(0);
	let failedRuns = $state(0);

	// Connectors metrics
	let connectorCount = $state(0);
	let activeConnectors = $state(0);

	// Activity feeds
	let recentRuns = $state<PipelineRun[]>([]);
	let recentJobs = $state<ScheduleJob[]>([]);
	let projectsMap = $state<Record<string, string>>({});

	// Auto-refresh state
	let refreshIntervalSec = $state<number>(15); // Default 15s
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let lastRefreshedAt = $state<Date>(new Date());

	async function loadDashboardData(silent = false) {
		if (!silent) loading = true;
		try {
			// Health checks
			const [healthRes, deepRes] = await Promise.allSettled([
				api.GET('/api/health'),
				api.GET('/api/health/deep')
			]);

			if (healthRes.status === 'fulfilled' && healthRes.value.data) {
				const data = healthRes.value.data as { status?: string };
				healthStatus = data.status === 'ok' ? 'online' : 'offline';
			} else {
				healthStatus = 'offline';
			}

			if (deepRes.status === 'fulfilled' && deepRes.value.data) {
				const data = deepRes.value.data as { status?: string };
				dbStatus = data.status === 'ok' ? 'connected' : 'error';
			} else {
				dbStatus = 'error';
			}

			// Core Entities & Metrics
			const [projectsRes, schedulesRes, jobsRes, specsRes, runsRes, connectorsRes] =
				await Promise.allSettled([
					api.GET('/api/v1/projects', { params: { query: { limit: 100 } } }),
					api.GET('/api/v1/schedule_configs', { params: { query: { limit: 100 } } }),
					api.GET('/api/v1/schedule_jobs', { params: { query: { limit: 6 } } }),
					api.GET('/api/v1/tasks/specs'),
					api.GET('/api/v1/pipeline-runs', { params: { query: { limit: 50 } } }),
					api.GET('/api/v1/connectors', { params: { query: { limit: 100 } } })
				]);

			if (projectsRes.status === 'fulfilled' && projectsRes.value.data) {
				const data = projectsRes.value.data;
				projectCount = data.total_count ?? data.items.length;
				const map: Record<string, string> = {};
				data.items.forEach((p: Project) => {
					map[p.id] = p.name;
				});
				projectsMap = map;
			}

			if (schedulesRes.status === 'fulfilled' && schedulesRes.value.data) {
				const data = schedulesRes.value.data;
				scheduleCount = data.total_count ?? data.items.length;
			}

			if (jobsRes.status === 'fulfilled' && jobsRes.value.data) {
				const data = jobsRes.value.data;
				jobCount = data.total_count ?? data.items.length;
				recentJobs = data.items.slice(0, 5);
			}

			if (specsRes.status === 'fulfilled' && Array.isArray(specsRes.value.data)) {
				taskSpecCount = specsRes.value.data.length;
			}

			if (runsRes.status === 'fulfilled' && runsRes.value.data) {
				const data = runsRes.value.data;
				totalRuns = data.total_count ?? data.items.length;
				recentRuns = data.items.slice(0, 5);

				// Breakdown counts
				activeRuns = data.items.filter((r: PipelineRun) =>
					['queued', 'dispatching', 'implementing'].includes(r.state)
				).length;
				awaitingCiRuns = data.items.filter((r: PipelineRun) => r.state === 'awaiting_ci').length;
				completedRuns = data.items.filter((r: PipelineRun) => r.state === 'completed').length;
				failedRuns = data.items.filter((r: PipelineRun) =>
					['failed', 'paused'].includes(r.state)
				).length;
			}

			if (connectorsRes.status === 'fulfilled' && connectorsRes.value.data) {
				const data = connectorsRes.value.data;
				connectorCount = data.total_count ?? data.items.length;
				activeConnectors = data.items.filter((c: Connector) => c.enabled).length;
			}

			lastRefreshedAt = new Date();
		} catch {
			healthStatus = 'offline';
		} finally {
			if (!silent) loading = false;
		}
	}

	function setupAutoRefresh(seconds: number) {
		if (refreshTimer) {
			clearInterval(refreshTimer);
			refreshTimer = null;
		}
		refreshIntervalSec = seconds;
		if (seconds > 0) {
			refreshTimer = setInterval(() => {
				loadDashboardData(true);
			}, seconds * 1000);
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
		loadDashboardData();
		setupAutoRefresh(refreshIntervalSec);
	});

	onDestroy(() => {
		if (refreshTimer) {
			clearInterval(refreshTimer);
		}
	});
</script>

<div class="space-y-6">
	<!-- Header with Live Refresh Indicator -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">System Overview</h1>
			<p class="text-sm text-muted-foreground">
				Real-time orchestrator statistics, lifecycle pipeline status, and health metrics
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-3">
			<!-- Auto-Refresh Controls -->
			<div
				class="flex items-center gap-1.5 rounded-lg border border-border bg-card/60 px-2.5 py-1 text-xs backdrop-blur-xs"
			>
				<div class="flex items-center gap-1.5 font-medium text-muted-foreground">
					<Radio
						class="size-3.5 {refreshIntervalSec > 0
							? 'animate-pulse text-emerald-500'
							: 'text-muted-foreground'}"
					/>
					<span>Sync:</span>
				</div>
				<button
					type="button"
					onclick={() => setupAutoRefresh(0)}
					class="rounded px-1.5 py-0.5 font-mono transition-colors {refreshIntervalSec === 0
						? 'bg-primary font-semibold text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'}"
				>
					Off
				</button>
				<button
					type="button"
					onclick={() => setupAutoRefresh(5)}
					class="rounded px-1.5 py-0.5 font-mono transition-colors {refreshIntervalSec === 5
						? 'bg-primary font-semibold text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'}"
				>
					5s
				</button>
				<button
					type="button"
					onclick={() => setupAutoRefresh(15)}
					class="rounded px-1.5 py-0.5 font-mono transition-colors {refreshIntervalSec === 15
						? 'bg-primary font-semibold text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'}"
				>
					15s
				</button>
				<button
					type="button"
					onclick={() => setupAutoRefresh(30)}
					class="rounded px-1.5 py-0.5 font-mono transition-colors {refreshIntervalSec === 30
						? 'bg-primary font-semibold text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'}"
				>
					30s
				</button>
				<span class="pl-1 font-mono text-[10px] text-muted-foreground/70">
					{lastRefreshedAt.toLocaleTimeString([], {
						hour: '2-digit',
						minute: '2-digit',
						second: '2-digit'
					})}
				</span>
			</div>

			<Button
				variant="outline"
				size="sm"
				onclick={() => loadDashboardData(false)}
				disabled={loading}
				class="gap-2"
			>
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
		</div>
	</div>

	<!-- Status & Health Banner -->
	<div class="grid gap-4 sm:grid-cols-2">
		<div
			class="flex items-center justify-between rounded-xl border border-border/80 bg-card/60 p-4 backdrop-blur-xs"
		>
			<div class="flex items-center gap-3">
				<div class="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<Activity class="size-5" />
				</div>
				<div>
					<p class="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
						API Health
					</p>
					<p class="text-sm font-medium">FastAPI Dispatcher Core</p>
				</div>
			</div>
			{#if healthStatus === 'online'}
				<Badge
					variant="default"
					class="gap-1.5 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
				>
					<CheckCircle2 class="size-3.5" />
					Operational
				</Badge>
			{:else}
				<Badge variant="destructive" class="gap-1.5">
					<AlertCircle class="size-3.5" />
					Unavailable
				</Badge>
			{/if}
		</div>

		<div
			class="flex items-center justify-between rounded-xl border border-border/80 bg-card/60 p-4 backdrop-blur-xs"
		>
			<div class="flex items-center gap-3">
				<div class="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
					<CheckCircle2 class="size-5" />
				</div>
				<div>
					<p class="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
						Database Connection
					</p>
					<p class="text-sm font-medium">PostgreSQL / SQLite Engine</p>
				</div>
			</div>
			{#if dbStatus === 'connected'}
				<Badge
					variant="default"
					class="gap-1.5 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
				>
					<CheckCircle2 class="size-3.5" />
					Connected
				</Badge>
			{:else}
				<Badge variant="destructive" class="gap-1.5">
					<AlertCircle class="size-3.5" />
					Disconnected
				</Badge>
			{/if}
		</div>
	</div>

	<!-- Pipeline Runs Observability Card (High-Impact Hero Banner) -->
	<Card
		class="overflow-hidden border-primary/20 bg-linear-to-br from-card via-card to-primary/5 shadow-sm"
	>
		<CardHeader class="pb-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<Workflow class="size-5 text-primary" />
					<CardTitle class="text-base font-semibold">Pipeline Runs Orchestration</CardTitle>
				</div>
				<Button
					variant="ghost"
					size="sm"
					onclick={() => (session.activeTab = 'pipeline-runs')}
					class="gap-1.5 text-xs text-primary hover:text-primary"
				>
					View All Runs
					<ArrowRight class="size-3.5" />
				</Button>
			</div>
		</CardHeader>
		<CardContent>
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-5">
				<div class="rounded-lg border border-border/70 bg-background/50 p-3">
					<div class="text-xs font-semibold text-muted-foreground uppercase">Total Runs</div>
					<div class="mt-1 text-2xl font-bold">{totalRuns}</div>
					<p class="mt-0.5 text-[11px] text-muted-foreground">All time lifecycle</p>
				</div>
				<div class="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-3">
					<div class="text-xs font-semibold text-indigo-600 uppercase dark:text-indigo-400">
						Active Work
					</div>
					<div class="mt-1 text-2xl font-bold text-indigo-600 dark:text-indigo-400">
						{activeRuns}
					</div>
					<p class="mt-0.5 text-[11px] text-muted-foreground">Dispatch / Implementing</p>
				</div>
				<div class="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
					<div class="text-xs font-semibold text-amber-600 uppercase dark:text-amber-400">
						Awaiting CI
					</div>
					<div class="mt-1 text-2xl font-bold text-amber-600 dark:text-amber-400">
						{awaitingCiRuns}
					</div>
					<p class="mt-0.5 text-[11px] text-muted-foreground">PR verification check</p>
				</div>
				<div class="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
					<div class="text-xs font-semibold text-emerald-600 uppercase dark:text-emerald-400">
						Completed
					</div>
					<div class="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
						{completedRuns}
					</div>
					<p class="mt-0.5 text-[11px] text-muted-foreground">Passed CI verification</p>
				</div>
				<div class="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3">
					<div class="text-xs font-semibold text-rose-600 uppercase dark:text-rose-400">
						Failed / Paused
					</div>
					<div class="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">{failedRuns}</div>
					<p class="mt-0.5 text-[11px] text-muted-foreground">Needs investigation</p>
				</div>
			</div>
		</CardContent>
	</Card>

	<!-- Core Metrics Grid -->
	<div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
		<!-- Projects Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'projects')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Managed Projects</CardTitle>
				<FolderKanban class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{projectCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">Connected repositories & Linear workspaces</p>
			</CardContent>
		</Card>

		<!-- Connectors Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'connectors')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Integrations</CardTitle>
				<KeyRound class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{connectorCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">
					{activeConnectors} active credentials (GitHub & Linear)
				</p>
			</CardContent>
		</Card>

		<!-- Schedules Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'configs')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Schedule Configs</CardTitle>
				<CalendarClock class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{scheduleCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">Automated cron & interval triggers</p>
			</CardContent>
		</Card>

		<!-- Jobs Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'jobs')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Job History</CardTitle>
				<History class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{jobCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">{taskSpecCount} available worker tasks</p>
			</CardContent>
		</Card>
	</div>

	<!-- Activity Streams (Side by Side) -->
	<div class="grid gap-6 lg:grid-cols-2">
		<!-- Recent Pipeline Runs -->
		<div class="rounded-xl border border-border/80 bg-card/60 p-5 backdrop-blur-xs">
			<div class="flex items-center justify-between pb-3">
				<div class="flex items-center gap-2">
					<Workflow class="size-4 text-primary" />
					<h2 class="text-sm font-semibold tracking-tight">Recent Pipeline Runs</h2>
				</div>
				<Button
					variant="ghost"
					size="sm"
					onclick={() => (session.activeTab = 'pipeline-runs')}
					class="text-xs text-muted-foreground hover:text-foreground"
				>
					View All
				</Button>
			</div>

			{#if recentRuns.length === 0}
				<div class="py-8 text-center text-xs text-muted-foreground">
					No pipeline runs dispatched yet.
				</div>
			{:else}
				<div class="divide-y divide-border/60">
					{#each recentRuns as run (run.id)}
						<div class="flex items-center justify-between py-2.5 text-xs">
							<div class="min-w-0 flex-1 pr-3">
								<div class="flex items-center gap-2">
									<span class="font-bold text-foreground">{run.linear_issue_identifier}</span>
									<span class="truncate text-muted-foreground">
										{run.linear_issue_snapshot?.title || projectsMap[run.project_id] || ''}
									</span>
								</div>
								<div
									class="mt-0.5 flex items-center gap-2 font-mono text-[11px] text-muted-foreground"
								>
									<div class="flex items-center gap-1">
										<GitBranch class="size-3" />
										<span class="max-w-[140px] truncate">{run.branch}</span>
									</div>
									{#if run.pull_number}
										<span class="font-medium text-primary">PR #{run.pull_number}</span>
									{/if}
								</div>
							</div>
							<div class="flex items-center gap-2">
								<Badge
									variant="outline"
									class="text-[10px] capitalize {getStateBadgeClass(run.state)}"
								>
									{run.state.replace('_', ' ')}
								</Badge>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Recent Scheduled Job Executions -->
		<div class="rounded-xl border border-border/80 bg-card/60 p-5 backdrop-blur-xs">
			<div class="flex items-center justify-between pb-3">
				<div class="flex items-center gap-2">
					<History class="size-4 text-primary" />
					<h2 class="text-sm font-semibold tracking-tight">Recent Schedule Executions</h2>
				</div>
				<Button
					variant="ghost"
					size="sm"
					onclick={() => (session.activeTab = 'jobs')}
					class="text-xs text-muted-foreground hover:text-foreground"
				>
					View All
				</Button>
			</div>

			{#if recentJobs.length === 0}
				<div class="py-8 text-center text-xs text-muted-foreground">
					No schedule jobs executed yet.
				</div>
			{:else}
				<div class="divide-y divide-border/60">
					{#each recentJobs as job (job.id)}
						<div class="flex items-center justify-between py-2.5 text-xs">
							<div class="min-w-0 flex-1 pr-3">
								<div class="font-medium text-foreground">
									{job.name}
								</div>
								<div class="mt-0.5 font-mono text-[11px] text-muted-foreground">
									run: {job.dispatcher_run_id || 'manual'}
								</div>
							</div>
							<div class="flex items-center gap-2">
								{#if job.status === 'success'}
									<Badge
										variant="default"
										class="bg-emerald-500/15 text-[10px] text-emerald-600 dark:text-emerald-400"
									>
										Success
									</Badge>
								{:else if job.status === 'failure'}
									<Badge variant="destructive" class="text-[10px]">Failure</Badge>
								{:else}
									<Badge variant="outline" class="text-[10px] capitalize">
										{job.status}
									</Badge>
								{/if}
								<span class="font-mono text-[10px] text-muted-foreground">
									{new Date(job.created_at).toLocaleTimeString([], {
										hour: '2-digit',
										minute: '2-digit'
									})}
								</span>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<!-- Quick Launch Operations -->
	<div class="rounded-xl border border-border/80 bg-card/60 p-6 backdrop-blur-xs">
		<h2 class="text-lg font-semibold tracking-tight">Quick Operations</h2>
		<p class="mb-4 text-sm text-muted-foreground">
			Direct shortcuts to frequent orchestrator actions
		</p>
		<div class="flex flex-wrap gap-3">
			<Button onclick={() => (session.activeTab = 'pipeline-runs')} class="gap-2">
				<Workflow class="size-4" />
				Pipeline Runs
			</Button>
			<Button variant="secondary" onclick={() => (session.activeTab = 'projects')} class="gap-2">
				<FolderKanban class="size-4" />
				Manage Projects
			</Button>
			<Button variant="secondary" onclick={() => (session.activeTab = 'connectors')} class="gap-2">
				<KeyRound class="size-4" />
				Manage Connectors
			</Button>
			<Button variant="secondary" onclick={() => (session.activeTab = 'configs')} class="gap-2">
				<CalendarClock class="size-4" />
				View Schedules
			</Button>
			<Button variant="outline" onclick={() => (session.activeTab = 'jobs')} class="gap-2">
				<History class="size-4" />
				Job History
			</Button>
		</div>
	</div>
</div>
