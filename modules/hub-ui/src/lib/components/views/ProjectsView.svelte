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
	import {
		FolderKanban,
		Plus,
		RefreshCw,
		Search,
		Trash2,
		CheckCircle2,
		XCircle
	} from '@lucide/svelte';

	type Project = components['schemas']['ProjectRead'];

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let isDialogOpen = $state(false);
	let isSubmitting = $state(false);

	// New project form state
	let newName = $state('');

	let filteredProjects = $derived(
		projects.filter(
			(p) =>
				p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				p.github?.repository?.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

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

		isSubmitting = true;
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
				isDialogOpen = false;
				newName = '';
				loadProjects();
			}
		} catch {
			toast.error('An error occurred creating the project');
		} finally {
			isSubmitting = false;
		}
	}

	async function handleDelete(projectId: string) {
		if (!confirm('Are you sure you want to delete this project?')) return;
		try {
			const res = await api.DELETE('/api/v1/projects/{project_id}', {
				params: { path: { project_id: projectId } }
			});
			if (res.error) {
				toast.error('Failed to delete project');
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
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Projects</h1>
			<p class="text-sm text-muted-foreground">
				Organize workspaces first, then connect GitHub and Linear when needed
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadProjects} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
			<Button size="sm" onclick={() => (isDialogOpen = true)} class="gap-2">
				<Plus class="size-4" />
				New Project
			</Button>
		</div>
	</div>

	<!-- Controls & Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input placeholder="Search projects..." bind:value={searchQuery} class="h-10 pl-9" />
		</div>
	</div>

	<!-- Table Container -->
	<div
		class="overflow-hidden rounded-xl border border-border/80 bg-card/60 shadow-sm backdrop-blur-sm"
	>
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead class="w-[200px]">Project Name</TableHead>
					<TableHead>Connections</TableHead>
					<TableHead class="w-[120px]">Status</TableHead>
					<TableHead class="w-[180px]">Created</TableHead>
					<TableHead class="w-[100px] text-right">Actions</TableHead>
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
								{project.name}
							</TableCell>
							<TableCell class="font-mono text-xs text-muted-foreground">
								{#if project.github || project.linear}
									<div class="flex flex-wrap gap-1">
										{#if project.github}<Badge variant="secondary"
												>GitHub: {project.github.repository}</Badge
											>{/if}
										{#if project.linear}<Badge variant="secondary">Linear connected</Badge>{/if}
									</div>
								{:else}
									<span>None</span>
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
							<TableCell class="text-xs text-muted-foreground">
								{new Date(project.created_at).toLocaleString()}
							</TableCell>
							<TableCell class="text-right">
								<Button
									variant="ghost"
									size="icon"
									onclick={() => handleDelete(project.id)}
									class="size-8 text-muted-foreground hover:text-destructive"
									aria-label="Delete project"
								>
									<Trash2 class="size-4" />
								</Button>
							</TableCell>
						</TableRow>
					{/each}
				{/if}
			</TableBody>
		</Table>
	</div>

	<!-- Create Project Dialog -->
	<Dialog bind:open={isDialogOpen}>
		<DialogContent class="sm:max-w-[425px]">
			<DialogHeader>
				<DialogTitle>Register New Project</DialogTitle>
			</DialogHeader>
			<form onsubmit={handleCreateProject} class="space-y-4 py-2">
				<div class="space-y-2">
					<label for="pName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Project Name</label
					>
					<Input id="pName" placeholder="e.g. core-pipeline" bind:value={newName} required />
				</div>
				<div class="space-y-2">
					<p class="text-sm text-muted-foreground">
						Create the workspace now. GitHub and Linear can be connected from its settings later.
					</p>
				</div>
				<DialogFooter class="pt-4">
					<Button type="button" variant="outline" onclick={() => (isDialogOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isSubmitting}>
						{isSubmitting ? 'Saving...' : 'Create Project'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>
</div>
