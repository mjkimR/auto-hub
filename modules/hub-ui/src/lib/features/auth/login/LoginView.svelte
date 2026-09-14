<script lang="ts">
	import { session } from '$lib/stores/session.svelte';
	import { api } from '$lib/api';
	import { toast } from 'svelte-sonner';
	import { Server, KeyRound, Lock, AlertCircle, Loader2 } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import {
		Card,
		CardHeader,
		CardTitle,
		CardDescription,
		CardContent
	} from '$lib/components/ui/card';
	import ThemeToggle from '$lib/components/shared/ThemeToggle.svelte';

	let apiKey = $state('');
	let isValidating = $state(false);
	let errorMsg = $state<string | null>(null);

	async function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		if (!apiKey.trim()) {
			errorMsg = 'API Key is required';
			return;
		}

		isValidating = true;
		errorMsg = null;

		try {
			const res = await api.GET('/api/v1/tasks/specs', {
				headers: { 'X-API-Key': apiKey.trim() }
			});

			if (res.error) {
				errorMsg = 'Authentication failed. Please check your API key.';
				toast.error('Authentication failed');
			} else {
				session.setApiKey(apiKey.trim());
				toast.success('Authenticated successfully');
			}
		} catch {
			errorMsg = 'Could not reach server. Verify server is running on port 8389.';
			toast.error('Connection error');
		} finally {
			isValidating = false;
		}
	}
</script>

<div
	class="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background p-6"
>
	<!-- Background glow effects -->
	<div
		class="pointer-events-none absolute -top-40 left-1/4 size-96 rounded-full bg-primary/10 blur-3xl"
	></div>
	<div
		class="pointer-events-none absolute right-1/4 -bottom-40 size-96 rounded-full bg-primary/10 blur-3xl"
	></div>

	<!-- Top right theme toggle -->
	<div class="absolute top-6 right-6">
		<ThemeToggle />
	</div>

	<!-- Login Card -->
	<Card
		class="relative z-10 w-full max-w-md border-border/80 bg-card/80 shadow-xl backdrop-blur-xl"
	>
		<CardHeader class="space-y-3 text-center">
			<div
				class="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/25"
			>
				<Server class="size-7" />
			</div>
			<CardTitle class="text-2xl font-bold tracking-tight">Auto-Hub Manager</CardTitle>
			<CardDescription class="text-sm text-muted-foreground">
				Enter your Scheduler API Key to access the orchestrator
			</CardDescription>
		</CardHeader>

		<CardContent>
			{#if errorMsg}
				<div
					class="mb-5 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm font-medium text-destructive"
				>
					<AlertCircle class="size-4 shrink-0" />
					<span>{errorMsg}</span>
				</div>
			{/if}

			<form onsubmit={handleSubmit} class="space-y-4">
				<div class="space-y-2">
					<label
						for="apiKey"
						class="text-xs font-semibold tracking-wider text-muted-foreground uppercase"
					>
						API Key
					</label>
					<div class="relative">
						<KeyRound
							class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
						/>
						<Input
							id="apiKey"
							type="password"
							placeholder="Enter secret API key"
							bind:value={apiKey}
							class="h-11 pl-10"
							disabled={isValidating}
							required
						/>
					</div>
				</div>

				<Button
					type="submit"
					class="h-11 w-full gap-2 font-semibold shadow-md"
					disabled={isValidating}
				>
					{#if isValidating}
						<Loader2 class="size-4 animate-spin" />
						Validating...
					{:else}
						<Lock class="size-4" />
						Authenticate
					{/if}
				</Button>
			</form>
		</CardContent>
	</Card>

	<footer
		class="mt-8 text-center text-xs font-semibold tracking-widest text-muted-foreground/60 uppercase"
	>
		Auto-Hub Svelte • High Performance Cloud Scheduler UI
	</footer>
</div>
