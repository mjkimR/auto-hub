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
		FolderKanban,
		Plus,
		RefreshCw,
		Search,
		Trash2,
		CheckCircle2,
		XCircle,
		Settings2,
		Activity,
		Sparkles,
		ExternalLink,
		AlertCircle,
		MinusCircle,
		GitBranch,
		CheckCheck,
		CalendarClock
	} from '@lucide/svelte';

	type Project = components['schemas']['ProjectRead'];
	type Connector = components['schemas']['ConnectorRead'];
	type ConnectionCheck = components['schemas']['ConnectionCheck'];
	type AICatalog = components['schemas']['AICatalogRead'];

	let projects = $state<Project[]>([]);
	let connectors = $state<Connector[]>([]);
	let catalogs = $state<AICatalog[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');

	// Create dialog
	let isCreateOpen = $state(false);
	let isCreating = $state(false);
	let newName = $state('');

	// Edit / Settings dialog
	let isEditOpen = $state(false);
	let isUpdating = $state(false);
	let editingProject = $state<Project | null>(null);
	let editName = $state('');
	let editEnabled = $state(true);
	let hasGithub = $state(false);
	let githubRepo = $state('');
	let githubConnectorId = $state('');
	let githubWorkflow = $state('ci.yml');
	let githubRequiredJobs = $state('lint, test');
	let autoMerge = $state(true);
	let mergeMethod = $state<'squash' | 'merge' | 'rebase'>('squash');
	let autoFixCi = $state(true);
	let autoFixConflicts = $state(true);
	let autoEnrollOnTrigger = $state(true);
	let dispatchIntervalSeconds = $state('60');
	let aiCatalogId = $state('');

	// Connection Check dialog
	let isCheckOpen = $state(false);
	let isChecking = $state(false);
	let checkingProject = $state<Project | null>(null);
	let checkPullNumber = $state<number>(1);
	let checkResult = $state<ConnectionCheck | null>(null);

	// Quick Schedule dialog
	let isScheduleOpen = $state(false);
	let isScheduling = $state(false);
	let schedulingProject = $state<Project | null>(null);
	let scheduleName = $state('');
	let scheduleDescription = $state('');
	let scheduleTaskType = $state<'pipeline.dispatch_project' | 'pipeline.observe_project'>(
		'pipeline.dispatch_project'
	);
	let scheduleObservationPulls = $state('1');
	let scheduleTriggerType = $state<'interval' | 'cron'>('interval');
	let scheduleIntervalSeconds = $state('300');
	let scheduleCronExpression = $state('*/5 * * * *');

	let githubConnectors = $derived(connectors.filter((c) => c.provider === 'github'));
	let pipelineCatalogs = $derived(catalogs.filter((c) => c.pipeline_delivery));

	let filteredProjects = $derived(
		projects.filter(
			(p) =>
				p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				(p.github?.repository &&
					p.github.repository.toLowerCase().includes(searchQuery.toLowerCase()))
		)
	);

	async function loadConnectors() {
		try {
			const res = await api.GET('/api/v1/connectors', {
				params: { query: { limit: 100 } }
			});
			if (res.data?.items) {
				connectors = res.data.items;
			}
			const catalogRes = await api.GET('/api/v1/ai-catalogs');
			catalogs = catalogRes.data?.items ?? [];
		} catch {
			// Ignore connector load failure
		}
	}

	async function loadProjects() {
		loading = true;
		try {
			const res = await api.GET('/api/v1/projects', {});
			if (res.data?.items) {
				projects = res.data.items;
			}
		} catch {
			toast.error('Failed to load projects');
		} finally {
			loading = false;
		}
	}

	async function handleCreateProject(e: SubmitEvent) {
		e.preventDefault();
		if (!newName.trim()) {
			toast.error('Project name is required');
			return;
		}

		isCreating = true;
		try {
			const res = await api.POST('/api/v1/projects', {
				body: {
					name: newName.trim(),
					enabled: true
				}
			});

			if (res.error) {
				toast.error('Failed to create project');
			} else {
				toast.success(`Project ${newName} created`);
				isCreateOpen = false;
				newName = '';
				loadProjects();
			}
		} catch {
			toast.error('An error occurred creating the project');
		} finally {
			isCreating = false;
		}
	}

	function openEdit(project: Project) {
		editingProject = project;
		editName = project.name;
		editEnabled = project.enabled;
		if (project.github) {
			hasGithub = true;
			githubRepo = project.github.repository;
			githubConnectorId = project.github.github_connector_id;
			githubWorkflow = project.github.verification.workflow;
			githubRequiredJobs = project.github.verification.required_jobs.join(', ');
			autoMerge = project.github.automation?.auto_merge ?? true;
			mergeMethod = project.github.automation?.merge_method ?? 'squash';
			autoFixCi = project.github.automation?.auto_fix_ci ?? true;
			autoFixConflicts = project.github.automation?.auto_fix_conflicts ?? true;
			autoEnrollOnTrigger = project.github.automation?.auto_enroll_on_trigger ?? true;
			dispatchIntervalSeconds = String(project.github.automation?.dispatch_interval_seconds ?? 60);
			aiCatalogId = project.github.ai_catalog_id ?? '';
		} else {
			hasGithub = false;
			githubRepo = '';
			githubConnectorId = githubConnectors[0]?.id || '';
			githubWorkflow = 'ci.yml';
			githubRequiredJobs = 'lint, test';
			autoMerge = true;
			mergeMethod = 'squash';
			autoFixCi = true;
			autoFixConflicts = true;
			autoEnrollOnTrigger = true;
			dispatchIntervalSeconds = '60';
			aiCatalogId = '';
		}

		isEditOpen = true;
	}

	async function handleUpdateProject(e: SubmitEvent) {
		e.preventDefault();
		if (!editingProject) return;

		isUpdating = true;
		try {
			const jobs = githubRequiredJobs
				.split(',')
				.map((j) => j.trim())
				.filter(Boolean);

			const body: components['schemas']['ProjectUpdate'] = {
				name: editName.trim(),
				enabled: editEnabled,
				expected_revision: editingProject.revision,
				github: hasGithub
					? {
							repository: githubRepo.trim(),
							github_connector_id: githubConnectorId,
							ai_catalog_id: aiCatalogId || null,
							verification: {
								workflow: githubWorkflow.trim(),
								required_jobs: jobs,
								event: 'pull_request'
							},
							automation: {
								auto_merge: autoMerge,
								merge_method: mergeMethod,
								auto_fix_ci: autoFixCi,
								auto_fix_conflicts: autoFixConflicts,
								auto_enroll_on_trigger: autoEnrollOnTrigger,
								dispatch_interval_seconds: Number(dispatchIntervalSeconds)
							}
						}
					: null
			};

			const res = await api.PUT('/api/v1/projects/{project_id}', {
				params: { path: { project_id: editingProject.id } },
				body
			});

			if (res.error) {
				const detail = (res.error as { detail?: string }).detail || 'Failed to update project';
				toast.error(detail);
			} else {
				toast.success('Project configuration updated');
				isEditOpen = false;
				loadProjects();
			}
		} catch {
			toast.error('Failed to update project settings');
		} finally {
			isUpdating = false;
		}
	}

	function openCheck(project: Project) {
		checkingProject = project;
		checkPullNumber = 1;
		checkResult = project.last_check || null;
		isCheckOpen = true;
	}

	async function runConnectionCheck() {
		if (!checkingProject) return;
		isChecking = true;
		try {
			const res = await api.POST('/api/v1/projects/{project_id}/check', {
				params: { path: { project_id: checkingProject.id } },
				body: { pull_number: Number(checkPullNumber) }
			});

			if (res.error) {
				const detail = (res.error as { detail?: string }).detail || 'Connection check failed';
				toast.error(detail);
			} else if (res.data) {
				checkResult = res.data;
				if (res.data.ready) {
					toast.success('Connection check passed! Project is ready.');
				} else {
					toast.warning('Connection check completed with issues.');
				}
				loadProjects();
			}
		} catch {
			toast.error('An error occurred during connection check');
		} finally {
			isChecking = false;
		}
	}

	function openSchedule(project: Project) {
		schedulingProject = project;
		scheduleName = `Dispatch ${project.name}`;
		scheduleDescription = `Automated run dispatcher & progress tracker for ${project.name}`;
		scheduleTaskType = 'pipeline.dispatch_project';
		scheduleObservationPulls = '1';
		scheduleTriggerType = 'interval';
		scheduleIntervalSeconds = '300';
		scheduleCronExpression = '*/5 * * * *';
		isScheduleOpen = true;
	}

	function onTaskTypeChange(type: 'pipeline.dispatch_project' | 'pipeline.observe_project') {
		scheduleTaskType = type;
		if (schedulingProject) {
			if (type === 'pipeline.dispatch_project') {
				scheduleName = `Dispatch ${schedulingProject.name}`;
				scheduleDescription = `Automated run dispatcher & progress tracker for ${schedulingProject.name}`;
			} else {
				scheduleName = `Observe ${schedulingProject.name}`;
				scheduleDescription = `CI observation for ${schedulingProject.name}`;
			}
		}
	}

	async function handleCreateQuickSchedule(e: SubmitEvent) {
		e.preventDefault();
		if (!schedulingProject) return;

		let payload: Record<string, unknown> = {
			project_id: schedulingProject.id
		};

		if (scheduleTaskType === 'pipeline.observe_project') {
			const pulls = scheduleObservationPulls
				.split(',')
				.map((p) => parseInt(p.trim(), 10))
				.filter((n) => !isNaN(n) && n > 0);

			if (pulls.length === 0) {
				toast.error('Please specify at least one valid pull request number');
				return;
			}
			payload = {
				project_id: schedulingProject.id,
				pull_numbers: pulls
			};
		}

		isScheduling = true;
		try {
			const res = await api.POST('/api/v1/schedule_configs', {
				body: {
					name: scheduleName.trim(),
					description: scheduleDescription.trim() || null,
					task_func: scheduleTaskType,
					cron_expression: scheduleTriggerType === 'cron' ? scheduleCronExpression.trim() : null,
					interval_seconds:
						scheduleTriggerType === 'interval' ? Number(scheduleIntervalSeconds) : null,
					payload,
					enabled: true
				}
			});

			if (res.error) {
				toast.error('Failed to create schedule');
			} else {
				toast.success(`Schedule created for ${schedulingProject.name}!`);
				isScheduleOpen = false;
			}
		} catch {
			toast.error('Error creating schedule');
		} finally {
			isScheduling = false;
		}
	}

	async function handleDelete(projectId: string) {
		if (!confirm('Are you sure you want to delete this project?')) return;
		try {
			const res = await api.DELETE('/api/v1/projects/{project_id}', {
				params: { path: { project_id: projectId } }
			});
			if (res.error) {
				const detail = (res.error as { detail?: string }).detail || 'Failed to delete project';
				toast.error(detail);
			} else {
				toast.success('Project deleted');
				loadProjects();
			}
		} catch {
			toast.error('Failed to delete project');
		}
	}

	onMount(() => {
		loadProjects();
		loadConnectors();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Projects</h1>
			<p class="text-sm text-muted-foreground">
				Manage repository connections and verify CI pipelines
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadProjects} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
			<Button size="sm" onclick={() => (isCreateOpen = true)} class="gap-2">
				<Plus class="size-4" />
				New Project
			</Button>
		</div>
	</div>

	<!-- Controls & Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input
				placeholder="Search projects or repositories..."
				bind:value={searchQuery}
				class="h-10 pl-9"
			/>
		</div>
	</div>

	<!-- Table Container -->
	<div
		class="overflow-hidden rounded-xl border border-border/80 bg-card/60 shadow-xs backdrop-blur-xs"
	>
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead class="w-[200px]">Project Name</TableHead>
					<TableHead>Providers & Verification</TableHead>
					<TableHead class="w-[140px]">Last CI Check</TableHead>
					<TableHead class="w-[100px]">Status</TableHead>
					<TableHead class="w-[180px] text-right">Actions</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading}
					<TableRow>
						<TableCell colspan={5} class="h-32 text-center text-muted-foreground">
							Loading projects...
						</TableCell>
					</TableRow>
				{:else if filteredProjects.length === 0}
					<TableRow>
						<TableCell colspan={5} class="h-32 text-center text-muted-foreground">
							<div class="flex flex-col items-center justify-center gap-2">
								<FolderKanban class="size-8 text-muted-foreground/40" />
								<span>No projects found</span>
							</div>
						</TableCell>
					</TableRow>
				{:else}
					{#each filteredProjects as project (project.id)}
						<TableRow class="transition-colors hover:bg-muted/40">
							<TableCell class="font-semibold text-foreground">
								<div class="flex flex-col gap-0.5">
									<span>{project.name}</span>
									<span class="font-mono text-[11px] text-muted-foreground"
										>rev {project.revision}</span
									>
								</div>
							</TableCell>
							<TableCell class="text-xs">
								<div class="flex flex-wrap items-center gap-1.5">
									{#if project.github}
										<Badge
											variant="outline"
											class="gap-1.5 border-primary/20 bg-primary/5 font-mono text-primary"
										>
											<GitBranch class="size-3" />
											{project.github.repository}
										</Badge>
										<Badge variant="secondary" class="font-mono text-[10px]">
											{project.github.verification.workflow}
										</Badge>
									{:else}
										<span class="text-muted-foreground">No GitHub</span>
									{/if}
								</div>
							</TableCell>
							<TableCell>
								{#if project.last_check}
									{#if project.last_check.ready}
										<Badge
											variant="default"
											class="cursor-pointer gap-1 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25 dark:text-emerald-400"
											onclick={() => openCheck(project)}
										>
											<CheckCircle2 class="size-3" />
											Ready
										</Badge>
									{:else}
										<Badge
											variant="secondary"
											class="cursor-pointer gap-1 bg-amber-500/15 text-amber-600 hover:bg-amber-500/25 dark:text-amber-400"
											onclick={() => openCheck(project)}
										>
											<AlertCircle class="size-3" />
											Issue
										</Badge>
									{/if}
								{:else}
									<span class="text-xs text-muted-foreground">Unchecked</span>
								{/if}
							</TableCell>
							<TableCell>
								{#if project.enabled}
									<Badge
										variant="default"
										class="gap-1 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400"
									>
										<CheckCircle2 class="size-3" />
										Active
									</Badge>
								{:else}
									<Badge variant="secondary" class="gap-1 text-muted-foreground">
										<XCircle class="size-3" />
										Disabled
									</Badge>
								{/if}
							</TableCell>
							<TableCell class="text-right">
								<div class="flex items-center justify-end gap-1">
									<Button
										variant="ghost"
										size="icon"
										onclick={() => openCheck(project)}
										class="size-8 text-muted-foreground hover:text-primary"
										title="Connection Check"
										aria-label="Connection Check"
									>
										<Activity class="size-4" />
									</Button>
									<Button
										variant="ghost"
										size="icon"
										onclick={() => openSchedule(project)}
										class="size-8 text-muted-foreground hover:text-emerald-500"
										title="Create Scheduled Automation"
										aria-label="Create Schedule"
									>
										<CalendarClock class="size-4" />
									</Button>
									<Button
										variant="ghost"
										size="icon"
										onclick={() => openEdit(project)}
										class="size-8 text-muted-foreground hover:text-foreground"
										title="Configure Project"
										aria-label="Configure Project"
									>
										<Settings2 class="size-4" />
									</Button>
									<Button
										variant="ghost"
										size="icon"
										onclick={() => handleDelete(project.id)}
										class="size-8 text-muted-foreground hover:text-destructive"
										title="Delete Project"
										aria-label="Delete Project"
									>
										<Trash2 class="size-4" />
									</Button>
								</div>
							</TableCell>
						</TableRow>
					{/each}
				{/if}
			</TableBody>
		</Table>
	</div>

	<!-- Create Project Dialog -->
	<Dialog bind:open={isCreateOpen}>
		<DialogContent class="sm:max-w-[425px]">
			<DialogHeader>
				<DialogTitle>Register New Project</DialogTitle>
				<DialogDescription>
					Create a project workspace. You can configure GitHub and Linear connections right after.
				</DialogDescription>
			</DialogHeader>
			<form onsubmit={handleCreateProject} class="space-y-4 py-2">
				<div class="space-y-2">
					<label for="pName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Project Name</label
					>
					<Input id="pName" placeholder="e.g. backend-pipeline" bind:value={newName} required />
				</div>
				<DialogFooter class="pt-4">
					<Button type="button" variant="outline" onclick={() => (isCreateOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isCreating}>
						{isCreating ? 'Creating...' : 'Create Project'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>

	<!-- Edit / Configure Project Dialog -->
	<Dialog bind:open={isEditOpen}>
		<DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[550px]">
			<DialogHeader>
				<DialogTitle>Project Settings</DialogTitle>
				<DialogDescription>
					Configure the repository, CI workflow jobs, and Codex dispatch prerequisites.
				</DialogDescription>
			</DialogHeader>
			<form onsubmit={handleUpdateProject} class="space-y-5 py-2">
				<!-- Basic Info -->
				<div class="space-y-3">
					<div class="space-y-1.5">
						<label for="editName" class="text-xs font-semibold text-muted-foreground uppercase"
							>Project Name</label
						>
						<Input id="editName" bind:value={editName} required />
					</div>
					<div class="flex items-center gap-2">
						<input
							type="checkbox"
							id="editEnabled"
							bind:checked={editEnabled}
							class="size-4 rounded border-border text-primary focus:ring-primary"
						/>
						<label for="editEnabled" class="text-sm font-medium text-foreground">
							Project Active (enabled for scheduled tasks)
						</label>
					</div>
				</div>

				<!-- GitHub Section -->
				<div class="space-y-3 rounded-lg border border-border/80 bg-muted/20 p-3.5">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<GitBranch class="size-4 text-foreground" />
							<span class="text-sm font-semibold">GitHub Provider</span>
						</div>
						<label class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
							<input
								type="checkbox"
								bind:checked={hasGithub}
								class="size-3.5 rounded border-border text-primary focus:ring-primary"
							/>
							Enable GitHub
						</label>
					</div>

					{#if hasGithub}
						<div class="space-y-3 pt-2">
							<div class="space-y-1">
								<label
									for="ghRepo"
									class="text-[11px] font-semibold text-muted-foreground uppercase"
								>
									Repository (owner/repo)
								</label>
								<Input
									id="ghRepo"
									placeholder="e.g. acme/my-app"
									bind:value={githubRepo}
									required={hasGithub}
								/>
							</div>

							<div class="space-y-1">
								<label
									for="ghConn"
									class="text-[11px] font-semibold text-muted-foreground uppercase"
								>
									GitHub Connector
								</label>
								{#if githubConnectors.length > 0}
									<select
										id="ghConn"
										bind:value={githubConnectorId}
										class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:ring-1 focus:ring-ring"
									>
										{#each githubConnectors as conn (conn.id)}
											<option value={conn.id}>{conn.name} ({conn.id.slice(0, 8)}...)</option>
										{/each}
									</select>
								{:else}
									<Input
										id="ghConn"
										placeholder="Connector UUID"
										bind:value={githubConnectorId}
										required={hasGithub}
									/>
									<span class="text-[11px] text-amber-500"
										>No GitHub connectors found. Please create one in Connectors.</span
									>
								{/if}
							</div>

							<div class="grid grid-cols-2 gap-2">
								<div class="space-y-1">
									<label
										for="ghWf"
										class="text-[11px] font-semibold text-muted-foreground uppercase"
									>
										Workflow File
									</label>
									<Input
										id="ghWf"
										placeholder="ci.yml"
										bind:value={githubWorkflow}
										required={hasGithub}
									/>
								</div>
								<div class="space-y-1">
									<label
										for="ghJobs"
										class="text-[11px] font-semibold text-muted-foreground uppercase"
									>
										Required Jobs
									</label>
									<Input
										id="ghJobs"
										placeholder="lint, test"
										bind:value={githubRequiredJobs}
										required={hasGithub}
									/>
								</div>
							</div>

							<details class="rounded-md border border-border/80 bg-background/50 p-3">
								<summary class="cursor-pointer text-xs font-semibold text-foreground">
									Advanced automation
								</summary>
								<div class="mt-3 space-y-3">
									<label class="flex items-center justify-between gap-3 text-sm">
										<span>
											<span class="font-medium text-foreground"
												>Automatically merge after CI passes</span
											>
											<span class="mt-0.5 block text-xs text-muted-foreground"
												>GitHub branch rules remain the final authority.</span
											>
										</span>
										<input
											type="checkbox"
											bind:checked={autoMerge}
											class="size-4 rounded border-border text-primary focus:ring-primary"
										/>
									</label>

									<div class="grid grid-cols-2 gap-3">
										<div class="space-y-1">
											<label
												for="mergeMethod"
												class="text-[11px] font-semibold text-muted-foreground uppercase"
												>Merge method</label
											>
											<select
												id="mergeMethod"
												bind:value={mergeMethod}
												disabled={!autoMerge}
												class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs disabled:cursor-not-allowed disabled:opacity-50"
											>
												<option value="squash">Squash</option>
												<option value="merge">Create merge commit</option>
												<option value="rebase">Rebase</option>
											</select>
										</div>
										<div class="space-y-1">
											<label
												for="dispatchInterval"
												class="text-[11px] font-semibold text-muted-foreground uppercase"
												>Dispatch interval (seconds)</label
											>
											<Input
												id="dispatchInterval"
												type="number"
												min="30"
												max="3600"
												bind:value={dispatchIntervalSeconds}
											/>
										</div>
									</div>

									<div class="space-y-1">
										<label
											for="aiCatalog"
											class="text-[11px] font-semibold text-muted-foreground uppercase"
											>AI catalog</label
										>
										<select
											id="aiCatalog"
											bind:value={aiCatalogId}
											class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs"
										>
											<option value="">Default (Personal Codex)</option>
											{#each pipelineCatalogs as catalog (catalog.id)}
												<option value={catalog.id}>{catalog.name} ({catalog.kind})</option>
											{/each}
										</select>
									</div>

									<label class="flex items-center justify-between gap-3 text-sm">
										<span class="font-medium text-foreground"
											>Ask the AI agent to fix failed CI</span
										>
										<input
											type="checkbox"
											bind:checked={autoFixCi}
											class="size-4 rounded border-border text-primary focus:ring-primary"
										/>
									</label>
									<label class="flex items-center justify-between gap-3 text-sm">
										<span class="font-medium text-foreground"
											>Ask the AI agent to resolve merge conflicts</span
										>
										<input
											type="checkbox"
											bind:checked={autoFixConflicts}
											class="size-4 rounded border-border text-primary focus:ring-primary"
										/>
									</label>
									<label class="flex items-center justify-between gap-3 text-sm">
										<span>
											<span class="font-medium text-foreground"
												>Enroll PRs containing @auto-run</span
											>
											<span class="mt-0.5 block text-xs text-muted-foreground"
												>Turning this off keeps PR enrollment manual.</span
											>
										</span>
										<input
											type="checkbox"
											bind:checked={autoEnrollOnTrigger}
											class="size-4 rounded border-border text-primary focus:ring-primary"
										/>
									</label>
								</div>
							</details>

							<div class="space-y-2 rounded-md border border-primary/20 bg-primary/5 p-3 text-xs">
								<div class="font-semibold text-foreground">Codex dispatch checklist</div>
								<ul class="space-y-1.5 text-muted-foreground">
									<li>
										Codex is connected to the same GitHub user as this connector and has an
										environment for this repository.
									</li>
									<li>
										The environment can reach <code>github.com</code> and has a repository-scoped
										<code>GH_TOKEN</code> with Contents and Pull requests read/write access.
									</li>
									<li>
										This connector uses that user’s PAT with Pull requests read/write, Issues read,
										Actions read, and Contents read access.
									</li>
									<li>
										The repository has an <code>AGENTS.md</code> that states its required checks.
									</li>
								</ul>
								<p class="text-muted-foreground">
									Run Connection Check after saving to confirm the connector account and CI read
									access.
								</p>
							</div>
						</div>
					{/if}
				</div>

				<DialogFooter class="pt-2">
					<Button type="button" variant="outline" onclick={() => (isEditOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isUpdating}>
						{isUpdating ? 'Saving...' : 'Save Changes'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>

	<!-- Connection Check Dialog -->
	<Dialog bind:open={isCheckOpen}>
		<DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[600px]">
			<DialogHeader>
				<DialogTitle class="flex items-center gap-2">
					<Activity class="size-5 text-primary" />
					Connection & CI Check
				</DialogTitle>
				<DialogDescription>
					Verify read access to GitHub repository, active CI workflow, and evaluate PR checks.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-4 py-2">
				{#if checkingProject}
					<div
						class="flex items-center justify-between rounded-lg border border-border/70 bg-muted/30 p-3"
					>
						<div>
							<div class="font-semibold text-foreground">{checkingProject.name}</div>
							<div class="font-mono text-xs text-muted-foreground">
								{checkingProject.github?.repository || 'No GitHub configured'}
							</div>
						</div>
						<div class="flex items-center gap-2">
							<div class="flex items-center gap-1.5">
								<span class="text-xs font-semibold text-muted-foreground">PR #</span>
								<Input
									type="number"
									min="1"
									bind:value={checkPullNumber}
									class="h-8 w-20 text-xs"
									disabled={isChecking}
								/>
							</div>
							<Button size="sm" onclick={runConnectionCheck} disabled={isChecking} class="gap-1.5">
								<RefreshCw class="size-3.5 {isChecking ? 'animate-spin' : ''}" />
								{isChecking ? 'Checking...' : 'Run Check'}
							</Button>
						</div>
					</div>
				{/if}

				{#if checkResult}
					<!-- Overall status -->
					<div
						class="flex items-center justify-between rounded-lg border p-3 {checkResult.ready
							? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
							: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'}"
					>
						<div class="flex items-center gap-2">
							{#if checkResult.ready}
								<CheckCheck class="size-5" />
								<span class="font-semibold">Ready for CI Observation</span>
							{:else}
								<AlertCircle class="size-5" />
								<span class="font-semibold">Check Incomplete or Failed</span>
							{/if}
						</div>
						<span class="font-mono text-xs text-muted-foreground">
							{new Date(checkResult.checked_at).toLocaleTimeString()}
						</span>
					</div>

					<!-- Individual Checks -->
					<div class="space-y-2">
						<span class="text-xs font-semibold text-muted-foreground uppercase"
							>Verification Items</span
						>
						<div class="divide-y divide-border/60 rounded-lg border border-border/80 bg-card">
							{#each checkResult.checks as check (check.name)}
								<div class="flex items-start justify-between p-3">
									<div class="space-y-0.5">
										<div class="text-sm font-medium text-foreground">{check.name}</div>
										<div class="text-xs text-muted-foreground">{check.detail}</div>
									</div>
									<div>
										{#if check.status === 'passed'}
											<Badge
												variant="default"
												class="gap-1 bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25 dark:text-emerald-400"
											>
												<CheckCircle2 class="size-3" />
												Passed
											</Badge>
										{:else if check.status === 'failed'}
											<Badge
												variant="destructive"
												class="gap-1 bg-rose-500/15 text-rose-600 hover:bg-rose-500/25 dark:text-rose-400"
											>
												<XCircle class="size-3" />
												Failed
											</Badge>
										{:else}
											<Badge variant="secondary" class="gap-1 text-muted-foreground">
												<MinusCircle class="size-3" />
												Skipped
											</Badge>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					</div>

					<!-- PR Observation Details if available -->
					{#if checkResult.observation?.pulls?.[0]}
						{@const pull = checkResult.observation.pulls[0]}
						<div class="space-y-2 rounded-lg border border-border/70 bg-muted/20 p-3 text-xs">
							<div class="flex items-center justify-between font-semibold text-foreground">
								<span>PR #{pull.number} Verification Detail</span>
								<a
									href={pull.url}
									target="_blank"
									rel="noreferrer"
									class="inline-flex items-center gap-1 text-primary hover:underline"
								>
									View on GitHub
									<ExternalLink class="size-3" />
								</a>
							</div>
							<div class="grid grid-cols-2 gap-2 text-muted-foreground">
								<div>Head: <span class="font-mono">{pull.head_sha.slice(0, 7)}</span></div>
								<div>
									Status: <span class="font-semibold text-foreground capitalize"
										>{pull.result.status}</span
									>
								</div>
							</div>
							{#if pull.result.reason}
								<div class="text-muted-foreground">
									Reason: <span class="text-foreground">{pull.result.reason}</span>
								</div>
							{/if}
						</div>
					{/if}
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (isCheckOpen = false)}>Close</Button>
			</DialogFooter>
		</DialogContent>
	</Dialog>

	<!-- Quick Schedule Dialog -->
	<Dialog bind:open={isScheduleOpen}>
		<DialogContent class="sm:max-w-[500px]">
			<DialogHeader>
				<div class="flex items-center gap-2">
					<div
						class="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500"
					>
						<CalendarClock class="size-4" />
					</div>
					<div>
						<DialogTitle>Create Scheduled Automation</DialogTitle>
						<DialogDescription>
							Automate background execution for <span class="font-semibold text-foreground"
								>{schedulingProject?.name}</span
							>
						</DialogDescription>
					</div>
				</div>
			</DialogHeader>

			<form onsubmit={handleCreateQuickSchedule} class="space-y-4 py-2">
				<!-- Task Selection -->
				<div class="space-y-2">
					<span class="text-xs font-semibold text-muted-foreground uppercase">Automation Task</span>
					<div class="grid grid-cols-2 gap-2">
						<button
							type="button"
							onclick={() => onTaskTypeChange('pipeline.dispatch_project')}
							class="flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-all {scheduleTaskType ===
							'pipeline.dispatch_project'
								? 'border-primary bg-primary/5 ring-1 ring-primary'
								: 'border-border hover:bg-muted/50'}"
						>
							<div class="flex items-center gap-1.5 text-xs font-semibold text-foreground">
								<Sparkles class="size-3.5 text-primary" />
								Auto-Dispatch
							</div>
							<p class="text-[11px] leading-snug text-muted-foreground">
								Picks actionable tasks, creates runs & progresses CI automatically.
							</p>
						</button>

						<button
							type="button"
							onclick={() => onTaskTypeChange('pipeline.observe_project')}
							class="flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-all {scheduleTaskType ===
							'pipeline.observe_project'
								? 'border-primary bg-primary/5 ring-1 ring-primary'
								: 'border-border hover:bg-muted/50'}"
						>
							<div class="flex items-center gap-1.5 text-xs font-semibold text-foreground">
								<Activity class="size-3.5 text-primary" />
								Observe CI
							</div>
							<p class="text-[11px] leading-snug text-muted-foreground">
								Polls GitHub Actions jobs for specified PRs and records latest status.
							</p>
						</button>
					</div>
				</div>

				<!-- PR numbers if observe -->
				{#if scheduleTaskType === 'pipeline.observe_project'}
					<div class="space-y-1.5 rounded-lg border border-border/80 bg-muted/20 p-3">
						<label for="schedPulls" class="text-xs font-semibold text-muted-foreground uppercase">
							Pull Request Numbers (comma-separated)
						</label>
						<Input
							id="schedPulls"
							placeholder="e.g. 1, 42, 105"
							bind:value={scheduleObservationPulls}
							required
						/>
						<p class="text-[11px] text-muted-foreground">
							Specify up to 10 active PR numbers to track.
						</p>
					</div>
				{/if}

				<!-- Basic Config -->
				<div class="space-y-3">
					<div class="space-y-1.5">
						<label for="schedName" class="text-xs font-semibold text-muted-foreground uppercase">
							Schedule Name
						</label>
						<Input id="schedName" bind:value={scheduleName} required />
					</div>

					<div class="space-y-1.5">
						<label for="schedDesc" class="text-xs font-semibold text-muted-foreground uppercase">
							Description (optional)
						</label>
						<Input id="schedDesc" bind:value={scheduleDescription} />
					</div>
				</div>

				<!-- Trigger Cadence -->
				<div class="space-y-2">
					<div class="flex items-center justify-between">
						<span class="text-xs font-semibold text-muted-foreground uppercase">Cadence</span>
						<div class="flex rounded-md border border-border bg-muted/50 p-0.5">
							<button
								type="button"
								class="rounded px-2 py-0.5 text-xs font-medium transition-colors {scheduleTriggerType ===
								'interval'
									? 'bg-background text-foreground shadow-xs'
									: 'text-muted-foreground hover:text-foreground'}"
								onclick={() => (scheduleTriggerType = 'interval')}
							>
								Interval
							</button>
							<button
								type="button"
								class="rounded px-2 py-0.5 text-xs font-medium transition-colors {scheduleTriggerType ===
								'cron'
									? 'bg-background text-foreground shadow-xs'
									: 'text-muted-foreground hover:text-foreground'}"
								onclick={() => (scheduleTriggerType = 'cron')}
							>
								Cron
							</button>
						</div>
					</div>

					{#if scheduleTriggerType === 'interval'}
						<div class="space-y-2">
							<div class="flex gap-2">
								<Button
									type="button"
									size="sm"
									variant={scheduleIntervalSeconds === '60' ? 'default' : 'outline'}
									class="flex-1 text-xs"
									onclick={() => (scheduleIntervalSeconds = '60')}
								>
									1m
								</Button>
								<Button
									type="button"
									size="sm"
									variant={scheduleIntervalSeconds === '300' ? 'default' : 'outline'}
									class="flex-1 text-xs"
									onclick={() => (scheduleIntervalSeconds = '300')}
								>
									5m
								</Button>
								<Button
									type="button"
									size="sm"
									variant={scheduleIntervalSeconds === '900' ? 'default' : 'outline'}
									class="flex-1 text-xs"
									onclick={() => (scheduleIntervalSeconds = '900')}
								>
									15m
								</Button>
								<Button
									type="button"
									size="sm"
									variant={scheduleIntervalSeconds === '3600' ? 'default' : 'outline'}
									class="flex-1 text-xs"
									onclick={() => (scheduleIntervalSeconds = '3600')}
								>
									1h
								</Button>
							</div>
							<div class="flex items-center gap-2">
								<Input
									type="number"
									min="10"
									bind:value={scheduleIntervalSeconds}
									placeholder="Custom seconds"
									class="font-mono text-sm"
								/>
								<span class="text-xs whitespace-nowrap text-muted-foreground">seconds</span>
							</div>
						</div>
					{:else}
						<div class="space-y-1">
							<Input
								bind:value={scheduleCronExpression}
								placeholder="*/5 * * * *"
								class="font-mono text-sm"
								required
							/>
							<p class="text-[11px] text-muted-foreground">Standard 5-field cron syntax (UTC).</p>
						</div>
					{/if}
				</div>

				<DialogFooter class="pt-2">
					<Button type="button" variant="outline" onclick={() => (isScheduleOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isScheduling}>
						{isScheduling ? 'Creating...' : 'Create Schedule'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>
</div>
