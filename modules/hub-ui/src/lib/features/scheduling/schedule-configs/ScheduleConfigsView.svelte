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
		Clock,
		Pencil,
		Trash2,
		AlertTriangle
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

	// Edit dialog state
	let isEditDialogOpen = $state(false);
	let isEditSubmitting = $state(false);
	let editingConfigId = $state<string | null>(null);
	let editName = $state('');
	let editDesc = $state('');
	let editTaskFunc = $state('');
	let editScheduleType = $state<'cron' | 'interval'>('interval');
	let editCronExpr = $state('0 9 * * 1-5');
	let editIntervalSeconds = $state(60);
	let editPayloadObject = $state<Record<string, unknown>>({});
	let editEnabled = $state(true);

	// Delete dialog state
	let isDeleteDialogOpen = $state(false);
	let isDeleting = $state(false);
	let deletingConfig = $state<ScheduleConfig | null>(null);

	let selectedTaskSpec = $derived(taskSpecs.find((s) => s.name === formTaskFunc));
	let editSelectedTaskSpec = $derived(taskSpecs.find((s) => s.name === editTaskFunc));

	let filteredConfigs = $derived(
		configs.filter(
			(c) =>
				c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.task_func.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	function isProjectManaged(config: ScheduleConfig): boolean {
		return (
			config.task_func === 'pipeline.dispatch_project' ||
			config.task_func === 'pipeline.observe_project'
		);
	}

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

	function openEdit(config: ScheduleConfig) {
		editingConfigId = config.id;
		editName = config.name;
		editDesc = config.description ?? '';
		editTaskFunc = config.task_func;
		editScheduleType = config.cron_expression ? 'cron' : 'interval';
		editCronExpr = config.cron_expression ?? '0 9 * * 1-5';
		editIntervalSeconds = config.interval_seconds ?? 60;
		editPayloadObject = config.payload ? JSON.parse(JSON.stringify(config.payload)) : {};
		editEnabled = config.enabled;
		isEditDialogOpen = true;
	}

	async function handleUpdateSchedule(e: SubmitEvent) {
		e.preventDefault();
		if (!editingConfigId || !editName.trim()) {
			toast.error('Schedule name is required');
			return;
		}

		isEditSubmitting = true;
		try {
			const res = await api.PUT('/api/v1/schedule_configs/{schedule_config_id}', {
				params: { path: { schedule_config_id: editingConfigId } },
				body: {
					name: editName.trim(),
					description: editDesc.trim() || null,
					task_func: editTaskFunc,
					cron_expression: editScheduleType === 'cron' ? editCronExpr : null,
					interval_seconds: editScheduleType === 'interval' ? Number(editIntervalSeconds) : null,
					payload: editPayloadObject,
					enabled: editEnabled
				}
			});

			if (res.error) {
				toast.error('Failed to update schedule');
			} else {
				toast.success(`Schedule ${editName} updated!`);
				isEditDialogOpen = false;
				loadConfigs();
			}
		} catch {
			toast.error('Error updating schedule configuration');
		} finally {
			isEditSubmitting = false;
		}
	}

	function openDelete(config: ScheduleConfig) {
		deletingConfig = config;
		isDeleteDialogOpen = true;
	}

	async function confirmDelete() {
		if (!deletingConfig) return;

		isDeleting = true;
		try {
			const res = await api.DELETE('/api/v1/schedule_configs/{schedule_config_id}', {
				params: { path: { schedule_config_id: deletingConfig.id } }
			});

			if (res.error) {
				toast.error('Failed to delete schedule');
			} else {
				toast.success(`Schedule ${deletingConfig.name} deleted`);
				isDeleteDialogOpen = false;
				deletingConfig = null;
				loadConfigs();
			}
		} catch {
			toast.error('Error deleting schedule');
		} finally {
			isDeleting = false;
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
		<div class="flex items-center gap-2">
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
				<Play class="size-3.5" />
				Trigger Dispatcher
			</Button>
			<Button size="sm" onclick={() => (isDialogOpen = true)} class="gap-2">
				<Plus class="size-4" />
				New Schedule
			</Button>
		</div>
	</div>

	<!-- Search & Filter Bar -->
	<div class="flex items-center gap-2">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Search by schedule or task func..."
				bind:value={searchQuery}
				class="h-9 pl-9 text-xs"
			/>
		</div>
	</div>

	<!-- Configurations Table -->
	<div class="rounded-md border bg-card">
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead>Schedule Name</TableHead>
					<TableHead>Target Task</TableHead>
					<TableHead>Trigger Cadence</TableHead>
					<TableHead>Status</TableHead>
					<TableHead>Next Run</TableHead>
					<TableHead class="text-right">Actions</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading && configs.length === 0}
					<TableRow>
						<TableCell colspan={6} class="h-32 text-center text-muted-foreground">
							<div class="flex items-center justify-center gap-2">
								<RefreshCw class="size-4 animate-spin" />
								<span>Loading configurations...</span>
							</div>
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
								<div class="flex items-center gap-2">
									<span class="font-semibold text-foreground">{config.name}</span>
									{#if isProjectManaged(config)}
										<Badge
											variant="outline"
											class="border-blue-500/30 bg-blue-500/10 text-[10px] text-blue-600 dark:text-blue-400"
										>
											Project Managed
										</Badge>
									{/if}
								</div>
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
								<div class="flex items-center justify-end gap-1.5">
									<Button
										variant="outline"
										size="sm"
										onclick={() => toggleEnable(config)}
										class="h-8 text-xs"
									>
										{config.enabled ? 'Pause' : 'Resume'}
									</Button>
									<Button
										variant="outline"
										size="icon"
										class="size-8 text-muted-foreground hover:text-foreground"
										onclick={() => openEdit(config)}
										title="Edit Schedule"
									>
										<Pencil class="size-3.5" />
									</Button>
									<Button
										variant="outline"
										size="icon"
										class="size-8 text-muted-foreground hover:border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
										onclick={() => openDelete(config)}
										title="Delete Schedule"
									>
										<Trash2 class="size-3.5" />
									</Button>
								</div>
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
						>Target Task</label
					>
					<select
						id="scTask"
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-xs shadow-xs focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
						bind:value={formTaskFunc}
						required
					>
						<option value="" disabled selected>Select a task function to execute...</option>
						{#each taskSpecs as spec (spec.name)}
							<option value={spec.name}>{spec.name}</option>
						{/each}
					</select>
					{#if selectedTaskSpec?.description}
						<p class="text-[11px] text-muted-foreground italic">{selectedTaskSpec.description}</p>
					{/if}
				</div>

				<!-- Schedule Cadence Type Selection -->
				<div class="space-y-2">
					<span class="text-xs font-semibold text-muted-foreground uppercase"
						>Execution Cadence</span
					>
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

	<!-- Edit Schedule Dialog -->
	<Dialog bind:open={isEditDialogOpen}>
		<DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
			<DialogHeader>
				<DialogTitle>Edit Schedule Configuration</DialogTitle>
			</DialogHeader>

			<form onsubmit={handleUpdateSchedule} class="space-y-4 py-2">
				<!-- Name & Description -->
				<div class="space-y-2">
					<label for="editScName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Schedule Name</label
					>
					<Input id="editScName" placeholder="Schedule name" bind:value={editName} required />
				</div>

				<div class="space-y-2">
					<label for="editScDesc" class="text-xs font-semibold text-muted-foreground uppercase"
						>Description</label
					>
					<Input
						id="editScDesc"
						placeholder="Brief summary of what this schedule runs"
						bind:value={editDesc}
					/>
				</div>

				<!-- Target Task (Read-only) -->
				<div class="space-y-2">
					<label for="editScTask" class="text-xs font-semibold text-muted-foreground uppercase"
						>Target Task</label
					>
					<Input id="editScTask" value={editTaskFunc} disabled class="bg-muted font-mono text-xs" />
				</div>

				<!-- Schedule Cadence Type Selection -->
				<div class="space-y-2">
					<span class="text-xs font-semibold text-muted-foreground uppercase"
						>Execution Cadence</span
					>
					<div class="flex gap-2">
						<Button
							type="button"
							size="sm"
							variant={editScheduleType === 'cron' ? 'default' : 'outline'}
							onclick={() => (editScheduleType = 'cron')}
							class="flex-1 gap-1.5"
						>
							<CalendarClock class="size-3.5" />
							Cron Expression
						</Button>
						<Button
							type="button"
							size="sm"
							variant={editScheduleType === 'interval' ? 'default' : 'outline'}
							onclick={() => (editScheduleType = 'interval')}
							class="flex-1 gap-1.5"
						>
							<Clock class="size-3.5" />
							Interval Seconds
						</Button>
					</div>
				</div>

				{#if editScheduleType === 'cron'}
					<div class="space-y-1.5">
						<label for="editScCron" class="text-xs font-semibold text-muted-foreground uppercase"
							>Cron Expression</label
						>
						<Input
							id="editScCron"
							placeholder="* * * * * (e.g. 0 9 * * 1-5)"
							bind:value={editCronExpr}
							class="font-mono text-xs"
							required
						/>
						<p class="text-[11px] text-muted-foreground">Standard 5-field cron syntax</p>
					</div>
				{:else}
					<div class="space-y-1.5">
						<label
							for="editScInterval"
							class="text-xs font-semibold text-muted-foreground uppercase"
							>Interval (Seconds)</label
						>
						<Input
							id="editScInterval"
							type="number"
							min="1"
							bind:value={editIntervalSeconds}
							class="font-mono text-xs"
							required
						/>
						<p class="text-[11px] text-muted-foreground">Repeats every N seconds (e.g. 60, 300)</p>
					</div>
				{/if}

				<!-- Dynamic JSON Schema Form or Payload editor -->
				{#if editSelectedTaskSpec?.payload_schema}
					<div class="pt-2">
						<JsonSchemaForm
							schema={editSelectedTaskSpec.payload_schema}
							bind:value={editPayloadObject}
						/>
					</div>
				{/if}

				<!-- Enabled Toggle -->
				<div class="flex items-center justify-between rounded-lg border p-3">
					<div class="space-y-0.5">
						<div class="text-sm font-medium">Active Schedule</div>
						<div class="text-xs text-muted-foreground">
							Whether the dispatcher should execute this schedule
						</div>
					</div>
					<input
						type="checkbox"
						bind:checked={editEnabled}
						class="size-4 rounded border-gray-300 text-primary focus:ring-primary"
					/>
				</div>

				<DialogFooter class="pt-4">
					<Button
						type="button"
						variant="outline"
						onclick={() => (isEditDialogOpen = false)}
						disabled={isEditSubmitting}
					>
						Cancel
					</Button>
					<Button type="submit" disabled={isEditSubmitting}>
						{isEditSubmitting ? 'Saving...' : 'Save Changes'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>

	<!-- Delete Schedule Confirmation Dialog -->
	<Dialog bind:open={isDeleteDialogOpen}>
		<DialogContent class="sm:max-w-[440px]">
			<DialogHeader>
				<DialogTitle class="flex items-center gap-2 text-destructive">
					<AlertTriangle class="size-5" />
					Delete Schedule Configuration
				</DialogTitle>
			</DialogHeader>

			<div class="space-y-3 py-2">
				<p class="text-sm text-foreground">
					Are you sure you want to delete <span class="font-semibold text-foreground"
						>"{deletingConfig?.name}"</span
					>?
				</p>
				{#if deletingConfig && isProjectManaged(deletingConfig)}
					<div
						class="rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-600 dark:text-amber-400"
					>
						<strong>Warning:</strong> This schedule is automatically managed for a project. Deleting it
						will stop automated background dispatching for this project.
					</div>
				{/if}
				<p class="text-xs text-muted-foreground">
					This action cannot be undone. Past execution history under Schedule Jobs will be
					preserved.
				</p>
			</div>

			<DialogFooter>
				<Button
					type="button"
					variant="outline"
					onclick={() => (isDeleteDialogOpen = false)}
					disabled={isDeleting}
				>
					Cancel
				</Button>
				<Button type="button" variant="destructive" onclick={confirmDelete} disabled={isDeleting}>
					{isDeleting ? 'Deleting...' : 'Delete Schedule'}
				</Button>
			</DialogFooter>
		</DialogContent>
	</Dialog>
</div>
