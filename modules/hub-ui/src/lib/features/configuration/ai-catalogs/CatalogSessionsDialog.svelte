<script lang="ts">
	import { onMount } from 'svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogFooter,
		DialogHeader,
		DialogTitle
	} from '$lib/components/ui/dialog';
	import { sessionTitle, type AICatalogSession } from './ai-catalogs.svelte';
	import type { CatalogDialogProps } from './catalog-kinds';

	const PAGE_SIZE = 20;

	let { catalog, catalogs, onclose }: CatalogDialogProps = $props();

	let open = $state(true);
	let loading = $state(true);
	let sessions = $state<AICatalogSession[]>([]);
	let offset = $state(0);
	let total = $state(0);

	const firstShown = $derived(sessions.length === 0 ? 0 : offset + 1);
	const lastShown = $derived(offset + sessions.length);

	$effect(() => {
		if (!open) onclose();
	});

	async function loadPage(pageOffset: number) {
		loading = true;
		const page = await catalogs.loadSessions(catalog.key, pageOffset, PAGE_SIZE);
		sessions = page.items;
		total = page.total;
		offset = pageOffset;
		loading = false;
	}

	onMount(() => {
		loadPage(0);
	});
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-2xl">
		<DialogHeader>
			<DialogTitle>{catalog.name} sessions</DialogTitle>
			<DialogDescription>
				Sessions this catalog started, most recent first. Reports and changes stay with the provider
				or the pull requests it opens.
			</DialogDescription>
		</DialogHeader>
		{#if loading}
			<p class="text-sm text-muted-foreground">Loading sessions…</p>
		{:else if sessions.length === 0}
			<p class="text-sm text-muted-foreground">No sessions yet.</p>
		{:else}
			<ul class="max-h-96 space-y-2 overflow-y-auto">
				{#each sessions as item (item.id)}
					<li class="rounded-md border border-border/80 p-3 text-sm">
						<div class="flex items-start justify-between gap-3">
							<span class="font-medium">{sessionTitle(item.title)}</span>
							<Badge variant={item.state === 'failed' ? 'destructive' : 'secondary'}
								>{item.state.replaceAll('_', ' ')}</Badge
							>
						</div>
						<p class="mt-1 text-xs text-muted-foreground">
							Started {new Date(item.created_at).toLocaleString()}
						</p>
						{#if item.failure_detail}
							<p class="mt-1 text-xs text-destructive">{item.failure_detail}</p>
						{/if}
						{#if item.url || item.pull_request_url}
							<div class="mt-2 flex flex-wrap gap-3 text-xs">
								{#if item.url}
									<a class="text-primary underline" href={item.url} target="_blank" rel="noreferrer"
										>Open session</a
									>
								{/if}
								{#if item.pull_request_url}
									<a
										class="text-primary underline"
										href={item.pull_request_url}
										target="_blank"
										rel="noreferrer">Pull request</a
									>
								{/if}
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		<DialogFooter class="items-center gap-2 sm:justify-between">
			<span class="text-xs text-muted-foreground">{firstShown}–{lastShown} of {total}</span>
			<div class="flex gap-2">
				<Button
					type="button"
					variant="outline"
					size="sm"
					disabled={loading || offset === 0}
					onclick={() => loadPage(Math.max(0, offset - PAGE_SIZE))}>Previous</Button
				>
				<Button
					type="button"
					variant="outline"
					size="sm"
					disabled={loading || offset + PAGE_SIZE >= total}
					onclick={() => loadPage(offset + PAGE_SIZE)}>Next</Button
				>
				<Button type="button" variant="outline" size="sm" onclick={() => (open = false)}
					>Close</Button
				>
			</div>
		</DialogFooter>
	</DialogContent>
</Dialog>
