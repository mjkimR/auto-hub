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
		DialogFooter
	} from '$lib/components/ui/dialog';
	import JsonSchemaForm from '$lib/components/shared/JsonSchemaForm.svelte';
	import {
		CalendarClock,
		RefreshCw,
		Search,
		CheckCircle2,
		PauseCircle,
		Play,
		Plus,
		Clock
	} from '@lucide/svelte';

	type ScheduleConfig = components['schemas']['ScheduleConfigRead'];
	type TaskSpec = components['schemas']['TaskSpecResponse'];

	let configs = $state<ScheduleConfig[]>([]);
	let taskSpecs = $state<TaskSpec[]>([]);
	let loading = $state(true);
	let isTriggering = $state(false);
	let searchQuery = $state('');

	// Create dialog state
	let isDialogOpen = $state(false);
	let isSubmitting = $state(false);
	let formName = $state('');
	let formDesc = $state('');
	let formTaskFunc = $state('');
	let scheduleType = $state<'cron' | 'interval'>('cron');
	let cronExpr = $state('0 9 * * 1-5');
	let intervalSeconds = $state(300);
	let payloadObject = $state<Record<string, unknown>>({});

	let selectedTaskSpec = $derived(taskSpecs.find((s) => s.name === formTaskFunc));

	let filteredConfigs = $derived(
		configs.filter(
			(c) =>
				c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.task_func.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	async function loadConfigs() {
		loading = true;
		try {
			const [cfgRes, specRes] = await Promise.all([
				api.GET('/api/v1/schedule_configs', {}),
				api.GET('/api/v1/tasks/specs')
			]);
			if (cfgRes.data?.items) {
				configs = cfgRes.data.items;
			}
			if (specRes.data && Array.isArray(specRes.data)) {
				taskSpecs = specRes.data;
			}
		} catch {
			toast.error('Failed to load schedule configs');
		} finally {
			loading = false;
		}
	}

	async function toggleEnable(config: ScheduleConfig) {
		try {
			const res = await api.PATCH('/api/v1/schedule_configs/{schedule_config_id}', {
				params: { path: { schedule_config_id: config.id } },
				body: { enabled: !config.enabled }
			});
			if (res.error) {
				toast.error('Failed to update schedule status');
			} else {
				toast.success(`Schedule ${!config.enabled ? 'enabled' : 'disabled'}`);
				loadConfigs();
			}
		} catch {
			toast.error('Error updating schedule');
		}
	}

	async function triggerDispatcher() {
		isTriggering = true;
		try {
			const res = await api.POST('/api/v1/dispatchers/trigger', {});
			if (res.error) {
				toast.error('Dispatcher trigger failed');
			} else {
				toast.success(`Dispatcher tick completed! Dispatched: ${res.data?.dispatched ?? 0}`);
				loadConfigs();
			}
		} catch {
			toast.error('Error triggering dispatcher');
		} finally {
			isTriggering = false;
		}
	}

	async function handleCreateSchedule(e: SubmitEvent) {
		e.preventDefault();
		if (!formName.trim() || !formTaskFunc) {
			toast.error('Name and Task Function are required');
			return;
		}

		isSubmitting = true;
		try {
			const res = await api.POST('/api/v1/schedule_configs', {
				body: {
					name: formName.trim(),
					description: formDesc.trim() || null,
					task_func: formTaskFunc,
					cron_expression: scheduleType === 'cron' ? cronExpr : null,
					interval_seconds: scheduleType === 'interval' ? Number(intervalSeconds) : null,
					payload: payloadObject,
					enabled: true
				}
			});

			if (res.error) {
				toast.error('Failed to create schedule');
			} else {
				toast.success(`Schedule ${formName} created!`);
				isDialogOpen = false;
				formName = '';
				formDesc = '';
				formTaskFunc = '';
				payloadObject = {};
				loadConfigs();
			}
		} catch {
			toast.error('Error creating schedule config');
		} finally {
			isSubmitting = false;
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
			<h1 class="text-3xl font-bold tracking-tight">Schedule Configurations</h1>
			<p class="text-sm text-muted-foreground">
				Automated cron triggers and execution cadence rules
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadConfigs} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
			<Button
				variant="secondary"
				size="sm"
				onclick={triggerDispatcher}
				disabled={isTriggering}
				class="gap-2"
			>
				<Play class="size-3.5 {isTriggering ? 'animate-spin' : ''}" />
				Trigger Dispatcher
			</Button>
			<Button size="sm" onclick={() => (isDialogOpen = true)} class="gap-2">
				<Plus class="size-4" />
				New Schedule
			</Button>
		</div>
	</div>

	<!-- Controls & Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Search by schedule or task func..."
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
					<TableHead class="w-[220px]">Schedule Name</TableHead>
					<TableHead>Target Task</TableHead>
					<TableHead class="w-[160px]">Trigger Cadence</TableHead>
					<TableHead class="w-[120px]">Status</TableHead>
					<TableHead class="w-[180px]">Next Run</TableHead>
					<TableHead class="w-[100px] text-right">Actions</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading}
					<TableRow>
						<TableCell colspan={6} class="h-32 text-center text-muted-foreground">
							Loading schedules...
						</TableCell>
					</TableRow>
				{:else if filteredConfigs.length === 0}
					<TableRow>
						<TableCell colspan={6} class="h-32 text-center text-muted-foreground">
							<div class="flex flex-col items-center justify-center gap-2">
								<CalendarClock class="size-8 text-muted-foreground/40" />
								<span>No schedule configurations found</span>
							</div>
						</TableCell>
					</TableRow>
				{:else}
					{#each filteredConfigs as config (config.id)}
						<TableRow class="transition-colors hover:bg-muted/40">
							<TableCell>
								<div class="font-semibold text-foreground">{config.name}</div>
								{#if config.description}
									<div class="line-clamp-1 text-xs text-muted-foreground">{config.description}</div>
								{/if}
							</TableCell>
							<TableCell class="font-mono text-xs text-muted-foreground">
								{config.task_func}
							</TableCell>
							<TableCell class="font-mono text-xs">
								{#if config.cron_expression}
									<span class="rounded bg-primary/10 px-2 py-0.5 text-primary">
										cron: {config.cron_expression}
									</span>
								{:else if config.interval_seconds}
									<span class="rounded bg-secondary px-2 py-0.5 text-secondary-foreground">
										every {config.interval_seconds}s
									</span>
								{:else}
									<span class="text-muted-foreground">Manual only</span>
								{/if}
							</TableCell>
							<TableCell>
								{#if config.enabled}
									<Badge
										variant="default"
										class="gap-1 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
									>
										<CheckCircle2 class="size-3" />
										Active
									</Badge>
								{:else}
									<Badge variant="secondary" class="gap-1 text-muted-foreground">
										<PauseCircle class="size-3" />
										Paused
									</Badge>
								{/if}
							</TableCell>
							<TableCell class="text-xs text-muted-foreground">
								{config.next_run_at ? new Date(config.next_run_at).toLocaleString() : '—'}
							</TableCell>
							<TableCell class="text-right">
								<Button
									variant="outline"
									size="sm"
									onclick={() => toggleEnable(config)}
									class="h-8 text-xs"
								>
									{config.enabled ? 'Pause' : 'Resume'}
								</Button>
							</TableCell>
						</TableRow>
					{/each}
				{/if}
			</TableBody>
		</Table>
	</div>

	<!-- Create Schedule Dialog -->
	<Dialog bind:open={isDialogOpen}>
		<DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
			<DialogHeader>
				<DialogTitle>Configure New Schedule</DialogTitle>
			</DialogHeader>

			<form onsubmit={handleCreateSchedule} class="space-y-4 py-2">
				<!-- Name & Description -->
				<div class="space-y-2">
					<label for="scName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Schedule Name</label
					>
					<Input id="scName" placeholder="e.g. Daily Data Sync" bind:value={formName} required />
				</div>

				<div class="space-y-2">
					<label for="scDesc" class="text-xs font-semibold text-muted-foreground uppercase"
						>Description (optional)</label
					>
					<Input
						id="scDesc"
						placeholder="Brief summary of what this schedule runs"
						bind:value={formDesc}
					/>
				</div>

				<!-- Task Target Selection -->
				<div class="space-y-2">
					<label for="scTask" class="text-xs font-semibold text-muted-foreground uppercase"
						>Target Worker Task</label
					>
					<select
						id="scTask"
						class="h-10 w-full rounded-md border border-input bg-background px-3 text-xs focus:border-primary focus:outline-none"
						bind:value={formTaskFunc}
						required
					>
						<option value="" disabled>Select worker task...</option>
						{#each taskSpecs as spec (spec.name)}
							<option value={spec.name}>{spec.name} — {spec.description || 'No description'}</option
							>
						{/each}
					</select>
				</div>

				<!-- Trigger Type Selector -->
				<div class="space-y-2">
					<span class="text-xs font-semibold text-muted-foreground uppercase">Schedule Type</span>
					<div class="flex gap-2">
						<Button
							type="button"
							size="sm"
							variant={scheduleType === 'cron' ? 'default' : 'outline'}
							onclick={() => (scheduleType = 'cron')}
							class="flex-1 gap-1.5"
						>
							<CalendarClock class="size-3.5" />
							Cron Expression
						</Button>
						<Button
							type="button"
							size="sm"
							variant={scheduleType === 'interval' ? 'default' : 'outline'}
							onclick={() => (scheduleType = 'interval')}
							class="flex-1 gap-1.5"
						>
							<Clock class="size-3.5" />
							Interval Seconds
						</Button>
					</div>
				</div>

				{#if scheduleType === 'cron'}
					<div class="space-y-1.5">
						<label for="scCron" class="text-xs font-semibold text-muted-foreground uppercase"
							>Cron Expression</label
						>
						<Input
							id="scCron"
							placeholder="* * * * * (e.g. 0 9 * * 1-5)"
							bind:value={cronExpr}
							class="font-mono text-xs"
							required
						/>
						<p class="text-[11px] text-muted-foreground">Standard 5-field cron syntax</p>
					</div>
				{:else}
					<div class="space-y-1.5">
						<label for="scInterval" class="text-xs font-semibold text-muted-foreground uppercase"
							>Interval (Seconds)</label
						>
						<Input
							id="scInterval"
							type="number"
							min="1"
							bind:value={intervalSeconds}
							class="font-mono text-xs"
							required
						/>
						<p class="text-[11px] text-muted-foreground">Repeats every N seconds</p>
					</div>
				{/if}

				<!-- Dynamic JSON Schema Form for Payload -->
				{#if formTaskFunc}
					<div class="pt-2">
						<JsonSchemaForm schema={selectedTaskSpec?.payload_schema} bind:value={payloadObject} />
					</div>
				{/if}

				<DialogFooter class="pt-4">
					<Button type="button" variant="outline" onclick={() => (isDialogOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isSubmitting}>
						{isSubmitting ? 'Saving...' : 'Create Schedule'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>
</div>
