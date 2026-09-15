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
		KeyRound,
		Plus,
		RefreshCw,
		Search,
		Trash2,
		CheckCircle2,
		XCircle,
		Settings2,
		GitBranch,
		Layers,
		Lock,
		Eye,
		EyeOff
	} from '@lucide/svelte';

	type Connector = components['schemas']['ConnectorRead'];
	type ConnectorProvider = components['schemas']['ConnectorProvider'];

	let connectors = $state<Connector[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');

	// Create dialog state
	let isCreateOpen = $state(false);
	let isCreating = $state(false);
	let newName = $state('');
	let newProvider = $state<ConnectorProvider>('github');
	let newToken = $state('');
	let showNewToken = $state(false);

	// Edit dialog state
	let isEditOpen = $state(false);
	let isUpdating = $state(false);
	let editingConnector = $state<Connector | null>(null);
	let editName = $state('');
	let editEnabled = $state(true);
	let editToken = $state('');
	let showEditToken = $state(false);

	let filteredConnectors = $derived(
		connectors.filter(
			(c) =>
				c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
				c.provider.toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	async function loadConnectors() {
		loading = true;
		try {
			const res = await api.GET('/api/v1/connectors', {
				params: { query: { limit: 100 } }
			});
			if (res.data?.items) {
				connectors = res.data.items;
			}
		} catch {
			toast.error('Failed to load connectors');
		} finally {
			loading = false;
		}
	}

	async function handleCreate(e: SubmitEvent) {
		e.preventDefault();
		if (!newName.trim()) {
			toast.error('Connector name is required');
			return;
		}
		if (!newToken.trim()) {
			toast.error('Token or credential secret is required');
			return;
		}

		isCreating = true;
		try {
			const res = await api.POST('/api/v1/connectors', {
				body: {
					name: newName.trim(),
					provider: newProvider,
					enabled: true,
					config: {},
					credentials: { token: newToken.trim() }
				}
			});

			if (res.error) {
				const detail = (res.error as { detail?: string }).detail || 'Failed to create connector';
				toast.error(detail);
			} else {
				toast.success(`Connector ${newName} registered`);
				isCreateOpen = false;
				newName = '';
				newToken = '';
				loadConnectors();
			}
		} catch {
			toast.error('An error occurred creating connector');
		} finally {
			isCreating = false;
		}
	}

	function openEdit(connector: Connector) {
		editingConnector = connector;
		editName = connector.name;
		editEnabled = connector.enabled;
		editToken = '';
		showEditToken = false;
		isEditOpen = true;
	}

	async function handleUpdate(e: SubmitEvent) {
		e.preventDefault();
		if (!editingConnector) return;

		isUpdating = true;
		try {
			if (editToken.trim()) {
				// Updating credentials with PUT
				const res = await api.PUT('/api/v1/connectors/{connector_id}', {
					params: { path: { connector_id: editingConnector.id } },
					body: {
						name: editName.trim(),
						provider: editingConnector.provider,
						enabled: editEnabled,
						config: editingConnector.config || {},
						credentials: { token: editToken.trim() }
					}
				});
				if (res.error) {
					const detail = (res.error as { detail?: string }).detail || 'Failed to update connector';
					toast.error(detail);
				} else {
					toast.success('Connector updated with new credentials');
					isEditOpen = false;
					loadConnectors();
				}
			} else {
				// Patching metadata without changing credentials
				const res = await api.PATCH('/api/v1/connectors/{connector_id}', {
					params: { path: { connector_id: editingConnector.id } },
					body: {
						name: editName.trim(),
						enabled: editEnabled
					}
				});
				if (res.error) {
					const detail = (res.error as { detail?: string }).detail || 'Failed to update connector';
					toast.error(detail);
				} else {
					toast.success('Connector settings saved');
					isEditOpen = false;
					loadConnectors();
				}
			}
		} catch {
			toast.error('Failed to update connector');
		} finally {
			isUpdating = false;
		}
	}

	async function handleDelete(connectorId: string) {
		if (!confirm('Are you sure you want to delete this connector? Projects using it may fail.'))
			return;
		try {
			const res = await api.DELETE('/api/v1/connectors/{connector_id}', {
				params: { path: { connector_id: connectorId } }
			});
			if (res.error) {
				const detail = (res.error as { detail?: string }).detail || 'Failed to delete connector';
				toast.error(detail);
			} else {
				toast.success('Connector deleted');
				loadConnectors();
			}
		} catch {
			toast.error('Failed to delete connector');
		}
	}

	onMount(() => {
		loadConnectors();
	});
</script>

<div class="space-y-6">
	<!-- Page Header -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Connectors</h1>
			<p class="text-sm text-muted-foreground">
				Secure encrypted credentials for external GitHub and Linear integrations
			</p>
		</div>
		<div class="flex items-center gap-3">
			<Button variant="outline" size="sm" onclick={loadConnectors} disabled={loading} class="gap-2">
				<RefreshCw class="size-4 {loading ? 'animate-spin' : ''}" />
				Refresh
			</Button>
			<Button size="sm" onclick={() => (isCreateOpen = true)} class="gap-2">
				<Plus class="size-4" />
				New Connector
			</Button>
		</div>
	</div>

	<!-- Controls & Search -->
	<div class="flex items-center gap-3">
		<div class="relative max-w-sm flex-1">
			<Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
			<Input placeholder="Search connectors..." bind:value={searchQuery} class="h-10 pl-9" />
		</div>
	</div>

	<!-- Table Container -->
	<div
		class="overflow-hidden rounded-xl border border-border/80 bg-card/60 shadow-xs backdrop-blur-xs"
	>
		<Table>
			<TableHeader>
				<TableRow>
					<TableHead class="w-[240px]">Connector Name</TableHead>
					<TableHead class="w-[140px]">Provider</TableHead>
					<TableHead class="w-[160px]">Credentials</TableHead>
					<TableHead class="w-[120px]">Status</TableHead>
					<TableHead class="w-[180px]">Created</TableHead>
					<TableHead class="w-[100px] text-right">Actions</TableHead>
				</TableRow>
			</TableHeader>
			<TableBody>
				{#if loading}
					<TableRow>
						<TableCell colspan={6} class="h-32 text-center text-muted-foreground">
							Loading connectors...
						</TableCell>
					</TableRow>
				{:else if filteredConnectors.length === 0}
					<TableRow>
						<TableCell colspan={6} class="h-32 text-center text-muted-foreground">
							<div class="flex flex-col items-center justify-center gap-2">
								<KeyRound class="size-8 text-muted-foreground/40" />
								<span>No connectors found</span>
							</div>
						</TableCell>
					</TableRow>
				{:else}
					{#each filteredConnectors as connector (connector.id)}
						<TableRow class="transition-colors hover:bg-muted/40">
							<TableCell>
								<div class="flex flex-col gap-0.5">
									<span class="font-semibold text-foreground">{connector.name}</span>
									<span class="font-mono text-[11px] text-muted-foreground">{connector.id}</span>
								</div>
							</TableCell>
							<TableCell>
								{#if connector.provider === 'github'}
									<Badge
										variant="outline"
										class="gap-1.5 border-primary/20 bg-primary/5 text-primary"
									>
										<GitBranch class="size-3" />
										GitHub
									</Badge>
								{:else if connector.provider === 'linear'}
									<Badge
										variant="outline"
										class="gap-1.5 border-indigo-500/30 bg-indigo-500/10 text-indigo-500"
									>
										<Layers class="size-3" />
										Linear
									</Badge>
								{:else if connector.provider === 'jules'}
									<Badge variant="outline" class="gap-1.5">Jules</Badge>
								{:else}
									<Badge variant="secondary">{connector.provider}</Badge>
								{/if}
							</TableCell>
							<TableCell>
								{#if connector.has_credentials}
									<Badge variant="secondary" class="gap-1 text-xs">
										<Lock class="size-3 text-emerald-500" />
										Encrypted Secret
									</Badge>
								{:else}
									<span class="text-xs text-muted-foreground">None</span>
								{/if}
							</TableCell>
							<TableCell>
								{#if connector.enabled}
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
								{new Date(connector.created_at).toLocaleString()}
							</TableCell>
							<TableCell class="text-right">
								<div class="flex items-center justify-end gap-1">
									<Button
										variant="ghost"
										size="icon"
										onclick={() => openEdit(connector)}
										class="size-8 text-muted-foreground hover:text-foreground"
										title="Edit Connector"
										aria-label="Edit Connector"
									>
										<Settings2 class="size-4" />
									</Button>
									<Button
										variant="ghost"
										size="icon"
										onclick={() => handleDelete(connector.id)}
										class="size-8 text-muted-foreground hover:text-destructive"
										title="Delete Connector"
										aria-label="Delete Connector"
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

	<!-- Create Connector Dialog -->
	<Dialog bind:open={isCreateOpen}>
		<DialogContent class="sm:max-w-[450px]">
			<DialogHeader>
				<DialogTitle>Register New Connector</DialogTitle>
				<DialogDescription>
					Credentials are encrypted with AES-GCM and stored securely.
				</DialogDescription>
			</DialogHeader>
			<form onsubmit={handleCreate} class="space-y-4 py-2">
				<div class="space-y-1.5">
					<label for="cName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Connector Name</label
					>
					<Input id="cName" placeholder="e.g. Org GitHub PAT" bind:value={newName} required />
				</div>

				<div class="space-y-1.5">
					<label for="cProvider" class="text-xs font-semibold text-muted-foreground uppercase"
						>Provider</label
					>
					<select
						id="cProvider"
						bind:value={newProvider}
						class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs focus:ring-1 focus:ring-ring"
					>
						<option value="github">GitHub (Personal Access Token / App Token)</option>
						<option value="linear">Linear (API Key)</option>
						<option value="jules">Jules (API Key)</option>
					</select>
				</div>

				<div class="space-y-1.5">
					<label for="cToken" class="text-xs font-semibold text-muted-foreground uppercase">
						Secret Token
					</label>
					<div class="relative">
						<Input
							id="cToken"
							type={showNewToken ? 'text' : 'password'}
							placeholder={newProvider === 'github'
								? 'ghp_...'
								: newProvider === 'jules'
									? 'Jules API key'
									: 'lin_api_...'}
							bind:value={newToken}
							required
							class="pr-10"
						/>
						<button
							type="button"
							onclick={() => (showNewToken = !showNewToken)}
							class="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground"
							aria-label="Toggle password visibility"
						>
							{#if showNewToken}
								<EyeOff class="size-4" />
							{:else}
								<Eye class="size-4" />
							{/if}
						</button>
					</div>
				</div>

				<DialogFooter class="pt-4">
					<Button type="button" variant="outline" onclick={() => (isCreateOpen = false)}>
						Cancel
					</Button>
					<Button type="submit" disabled={isCreating}>
						{isCreating ? 'Saving...' : 'Register Connector'}
					</Button>
				</DialogFooter>
			</form>
		</DialogContent>
	</Dialog>

	<!-- Edit Connector Dialog -->
	<Dialog bind:open={isEditOpen}>
		<DialogContent class="sm:max-w-[450px]">
			<DialogHeader>
				<DialogTitle>Edit Connector</DialogTitle>
				<DialogDescription>
					Update connector name, enabled state, or rotate secret credentials.
				</DialogDescription>
			</DialogHeader>
			<form onsubmit={handleUpdate} class="space-y-4 py-2">
				<div class="space-y-1.5">
					<label for="editCName" class="text-xs font-semibold text-muted-foreground uppercase"
						>Connector Name</label
					>
					<Input id="editCName" bind:value={editName} required />
				</div>

				<div class="flex items-center gap-2 pt-1">
					<input
						type="checkbox"
						id="editCEnabled"
						bind:checked={editEnabled}
						class="size-4 rounded border-border text-primary focus:ring-primary"
					/>
					<label for="editCEnabled" class="text-sm font-medium text-foreground">
						Enabled for authentication
					</label>
				</div>

				<div class="space-y-1.5 pt-2">
					<label for="editCToken" class="text-xs font-semibold text-muted-foreground uppercase">
						Rotate Secret Token (Optional)
					</label>
					<div class="relative">
						<Input
							id="editCToken"
							type={showEditToken ? 'text' : 'password'}
							placeholder="Leave blank to preserve existing token"
							bind:value={editToken}
							class="pr-10"
						/>
						<button
							type="button"
							onclick={() => (showEditToken = !showEditToken)}
							class="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground"
							aria-label="Toggle password visibility"
						>
							{#if showEditToken}
								<EyeOff class="size-4" />
							{:else}
								<Eye class="size-4" />
							{/if}
						</button>
					</div>
				</div>

				<DialogFooter class="pt-4">
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
</div>
