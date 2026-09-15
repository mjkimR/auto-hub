<script lang="ts">
	import { untrack } from 'svelte';
	import { Button } from '$lib/components/ui/button';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogFooter,
		DialogHeader,
		DialogTitle
	} from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';
	import { codexWindowConfig } from './ai-catalogs.svelte';
	import type { CatalogDialogProps } from './catalog-kinds';

	let { catalog, catalogs, onclose }: CatalogDialogProps = $props();

	// The dialog is mounted per opening, so it edits the policy as it was when opened.
	const initial = untrack(() => codexWindowConfig(catalog));
	let open = $state(true);
	let shortRefreshEnabled = $state(initial.short_refresh_enabled);
	// Number inputs bind numbers; string state would make every keystroke rewrite the field.
	let shortRefreshHours = $state<number | null>(initial.short_refresh_cycle_minutes / 60);
	let longRefreshDays = $state<number | null>(initial.long_refresh_cycle_minutes / (60 * 24));

	$effect(() => {
		if (!open) onclose();
	});

	async function save(event: SubmitEvent) {
		event.preventDefault();
		const shortHours = Number(shortRefreshHours);
		const longDays = Number(longRefreshDays);
		if (
			!Number.isFinite(shortHours) ||
			shortHours <= 0 ||
			!Number.isFinite(longDays) ||
			longDays <= 0
		) {
			return;
		}
		const config = {
			...initial,
			short_refresh_enabled: shortRefreshEnabled,
			short_refresh_cycle_minutes: Math.round(shortHours * 60),
			long_refresh_cycle_minutes: Math.round(longDays * 24 * 60)
		};
		if (await catalogs.updatePolicyConfig(catalog.key, config)) open = false;
	}
</script>

<Dialog bind:open>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Refresh policy</DialogTitle>
			<DialogDescription>
				A quota block waits one cycle from the first task of the current usage window, plus the
				catalog's safety jitter; after two failed short cycles, the long cycle is used.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={save} class="space-y-4">
			<label class="flex items-center gap-2 text-sm font-medium">
				<input type="checkbox" bind:checked={shortRefreshEnabled} />
				Use short refresh cycle
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Short cycle (hours)
				<Input
					type="number"
					min="0.1"
					step="0.1"
					bind:value={shortRefreshHours}
					disabled={!shortRefreshEnabled}
					required
				/>
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Long cycle (days)
				<Input type="number" min="0.1" step="0.1" bind:value={longRefreshDays} required />
			</label>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Cancel</Button>
				<Button type="submit" disabled={catalogs.saving}>Save policy</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
