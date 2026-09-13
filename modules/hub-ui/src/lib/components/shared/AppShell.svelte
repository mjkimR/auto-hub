<script lang="ts">
	import { session } from '$lib/stores/session.svelte';
	import { api } from '$lib/api';
	import ThemeToggle from '$lib/components/shared/ThemeToggle.svelte';
	import { Button } from '$lib/components/ui/button';
	import {
		Server,
		LayoutDashboard,
		FolderKanban,
		CalendarClock,
		History,
		Settings,
		FileCode,
		LogOut,
		Workflow
	} from '@lucide/svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	let isOnline = $state(false);

	async function checkHealth() {
		try {
			const res = await api.GET('/api/health');
			const data = res.data as { status?: string } | undefined;
			isOnline = data?.status === 'ok';
		} catch {
			isOnline = false;
		}
	}

	onMount(() => {
		checkHealth();
		const interval = setInterval(checkHealth, 10000);
		return () => clearInterval(interval);
	});

	const navItems = [
		{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
		{ id: 'projects', label: 'Projects', icon: FolderKanban },
		{ id: 'pipeline-runs', label: 'Pipeline Runs', icon: Workflow },
		{ id: 'configs', label: 'Schedule Configs', icon: CalendarClock },
		{ id: 'jobs', label: 'Schedule Jobs', icon: History },
		{ id: 'system', label: 'System Configs', icon: Settings },
		{ id: 'specs', label: 'Task Specs', icon: FileCode }
	] as const;
</script>

<div class="flex min-h-screen bg-background text-foreground">
	<!-- Left Sidebar -->
	<aside
		class="sticky top-0 flex h-screen w-64 flex-col border-r border-sidebar-border bg-sidebar px-4 py-6 text-sidebar-foreground"
	>
		<!-- Brand / Logo -->
		<div class="flex items-center gap-3 px-2 pb-6">
			<div
				class="flex size-10 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-md"
			>
				<Server class="size-5" />
			</div>
			<div>
				<div class="font-bold tracking-tight text-sidebar-foreground">Auto-Hub</div>
				<div class="text-[11px] font-medium text-muted-foreground">Scheduler Manager</div>
			</div>
		</div>

		<!-- Nav Links -->
		<nav class="flex-1 space-y-1 py-2">
			{#each navItems as item (item.id)}
				<button
					type="button"
					onclick={() => (session.activeTab = item.id)}
					class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors {session.activeTab ===
					item.id
						? 'bg-sidebar-accent font-semibold text-sidebar-accent-foreground shadow-xs'
						: 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'}"
				>
					<item.icon class="size-4 shrink-0" />
					<span>{item.label}</span>
				</button>
			{/each}
		</nav>

		<!-- Bottom User & Status Area -->
		<div class="space-y-4 border-t border-sidebar-border pt-4">
			<div class="flex items-center justify-between px-2">
				<div class="flex items-center gap-2 text-xs">
					{#if isOnline}
						<span class="flex size-2 rounded-full bg-emerald-500"></span>
						<span class="text-muted-foreground">Core Online</span>
					{:else}
						<span class="flex size-2 rounded-full bg-destructive"></span>
						<span class="text-destructive">Offline</span>
					{/if}
				</div>
				<ThemeToggle />
			</div>

			<div class="flex items-center justify-between rounded-lg bg-sidebar-accent/60 p-2.5">
				<div class="flex flex-col overflow-hidden text-xs">
					<span class="font-semibold text-sidebar-foreground">API Session</span>
					<span class="max-w-[120px] truncate font-mono text-[10px] text-muted-foreground">
						{session.apiKey ? `${session.apiKey.slice(0, 10)}...` : 'None'}
					</span>
				</div>
				<Button
					variant="ghost"
					size="icon"
					onclick={() => session.logout()}
					class="size-8 text-muted-foreground hover:text-destructive"
					title="Logout"
					aria-label="Logout"
				>
					<LogOut class="size-4" />
				</Button>
			</div>
		</div>
	</aside>

	<!-- Main Content Area -->
	<main class="flex-1 overflow-y-auto">
		<!-- Top Bar -->
		<header
			class="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border/80 bg-background/80 px-8 backdrop-blur-md"
		>
			<div class="flex items-center gap-2">
				<span class="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
					Auto-Hub
				</span>
				<span class="text-muted-foreground/60">/</span>
				<span class="text-sm font-semibold text-foreground capitalize">
					{session.activeTab}
				</span>
			</div>

			<div class="flex items-center gap-3 text-xs text-muted-foreground">
				<span
					class="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 font-medium text-primary"
				>
					<span class="size-1.5 animate-pulse rounded-full bg-primary"></span>
					Svelte 5 Runes
				</span>
			</div>
		</header>

		<!-- Page Content Container -->
		<div class="mx-auto max-w-7xl p-8">
			{@render children()}
		</div>
	</main>
</div>
