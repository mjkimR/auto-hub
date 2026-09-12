<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { session } from '$lib/stores/session.svelte';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import {
		FolderKanban,
		CalendarClock,
		History,
		FileCode,
		Activity,
		CheckCircle2,
		AlertCircle,
		RefreshCw
	} from '@lucide/svelte';

	let loading = $state(true);
	let healthStatus = $state<'online' | 'offline' | 'checking'>('checking');
	let dbStatus = $state<'connected' | 'error' | 'unknown'>('unknown');
	let projectCount = $state(0);
	let scheduleCount = $state(0);
	let jobCount = $state(0);
	let taskSpecCount = $state(0);

	async function loadDashboardData() {
		loading = true;
		try {
			// Health checks
			const healthRes = await api.GET('/api/health');
			const healthData = healthRes.data as { status?: string } | undefined;
			healthStatus = healthData?.status === 'ok' ? 'online' : 'offline';

			const deepRes = await api.GET('/api/health/deep');
			const deepData = deepRes.data as { status?: string } | undefined;
			dbStatus = deepData?.status === 'ok' ? 'connected' : 'error';

			// Metrics
			const [projectsRes, schedulesRes, jobsRes, specsRes] = await Promise.allSettled([
				api.GET('/api/v1/projects', {}),
				api.GET('/api/v1/schedule_configs', {}),
				api.GET('/api/v1/schedule_jobs', {}),
				api.GET('/api/v1/tasks/specs')
			]);

			if (projectsRes.status === 'fulfilled' && projectsRes.value.data) {
				projectCount = projectsRes.value.data.total_count ?? projectsRes.value.data.items.length;
			}
			if (schedulesRes.status === 'fulfilled' && schedulesRes.value.data) {
				scheduleCount = schedulesRes.value.data.total_count ?? schedulesRes.value.data.items.length;
			}
			if (jobsRes.status === 'fulfilled' && jobsRes.value.data) {
				jobCount = jobsRes.value.data.total_count ?? jobsRes.value.data.items.length;
			}
			if (specsRes.status === 'fulfilled' && Array.isArray(specsRes.value.data)) {
				taskSpecCount = specsRes.value.data.length;
			}
		} catch {
			healthStatus = 'offline';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadDashboardData();
	});
</script>

<div class="space-y-6">
	<!-- Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">System Overview</h1>
			<p class="text-sm text-muted-foreground">Real-time monitoring and orchestrator statistics</p>
		</div>
		<div class="flex items-center gap-3">
			<Button
				variant="outline"
				size="sm"
				onclick={loadDashboardData}
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
			class="flex items-center justify-between rounded-xl border border-border/80 bg-card/60 p-4 backdrop-blur-sm"
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
			class="flex items-center justify-between rounded-xl border border-border/80 bg-card/60 p-4 backdrop-blur-sm"
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
				<p class="mt-1 text-xs text-muted-foreground">Active orchestration workspaces</p>
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
				<p class="mt-1 text-xs text-muted-foreground">Configured cron & interval triggers</p>
			</CardContent>
		</Card>

		<!-- Jobs Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'jobs')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Total Executions</CardTitle>
				<History class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{jobCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">Historical job runs tracked</p>
			</CardContent>
		</Card>

		<!-- Tasks Metric -->
		<Card
			class="cursor-pointer transition-all hover:border-primary/40 hover:shadow-md"
			onclick={() => (session.activeTab = 'specs')}
		>
			<CardHeader class="flex flex-row items-center justify-between pb-2">
				<CardTitle class="text-sm font-medium text-muted-foreground">Worker Tasks</CardTitle>
				<FileCode class="size-4 text-muted-foreground" />
			</CardHeader>
			<CardContent>
				<div class="text-3xl font-bold">{taskSpecCount}</div>
				<p class="mt-1 text-xs text-muted-foreground">Discovered worker task definitions</p>
			</CardContent>
		</Card>
	</div>

	<!-- Quick Launch Grid -->
	<div class="rounded-xl border border-border/80 bg-card/60 p-6 backdrop-blur-sm">
		<h2 class="text-lg font-semibold tracking-tight">Quick Operations</h2>
		<p class="mb-4 text-sm text-muted-foreground">
			Direct shortcuts to frequent orchestrator actions
		</p>
		<div class="flex flex-wrap gap-3">
			<Button onclick={() => (session.activeTab = 'projects')} class="gap-2">
				<FolderKanban class="size-4" />
				Manage Projects
			</Button>
			<Button variant="secondary" onclick={() => (session.activeTab = 'configs')} class="gap-2">
				<CalendarClock class="size-4" />
				View Schedules
			</Button>
			<Button variant="secondary" onclick={() => (session.activeTab = 'jobs')} class="gap-2">
				<History class="size-4" />
				Job History
			</Button>
			<Button variant="outline" onclick={() => (session.activeTab = 'specs')} class="gap-2">
				<FileCode class="size-4" />
				Inspect Task Specs
			</Button>
		</div>
	</div>
</div>
