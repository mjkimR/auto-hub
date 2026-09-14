<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import AppShell from '$lib/components/shared/AppShell.svelte';
	import LoginView from '$lib/features/auth/login/LoginView.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from 'svelte-sonner';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher />
<Toaster richColors position="top-right" />

{#if session.isAuthenticated}
	<AppShell>{@render children()}</AppShell>
{:else}
	<LoginView />
{/if}
