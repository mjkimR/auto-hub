<script lang="ts">
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
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
	import { dailyQuotaConfig, isKnownTimezone, type DailyQuotaConfig } from './ai-catalogs.svelte';
	import type { CatalogDialogProps } from './catalog-kinds';

	let { catalog, catalogs, onclose }: CatalogDialogProps = $props();

	// The dialog is mounted per opening, so it edits the policy as it was when opened.
	const initial = untrack(() => dailyQuotaConfig(catalog));
	let open = $state(true);
	// Number inputs bind numbers; string state would make every keystroke rewrite the field.
	let dailyTaskLimit = $state<number | null>(initial?.daily_task_limit ?? 100);
	let quotaWindow = $state<DailyQuotaConfig['window']>(initial?.window ?? 'rolling');
	let timezone = $state(initial?.timezone ?? 'UTC');

	$effect(() => {
		if (!open) onclose();
	});

	async function save(event: SubmitEvent) {
		event.preventDefault();
		const limit = Number(dailyTaskLimit);
		if (!Number.isInteger(limit) || limit < 1) return;
		const resetTimezone = timezone.trim() || 'UTC';
		if (quotaWindow === 'calendar' && !isKnownTimezone(resetTimezone)) {
			toast.error(`Unknown timezone: ${resetTimezone}`);
			return;
		}
		const config = { daily_task_limit: limit, window: quotaWindow, timezone: resetTimezone };
		if (await catalogs.updatePolicyConfig(catalog.key, config)) open = false;
	}
</script>

<Dialog bind:open>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Quota policy</DialogTitle>
			<DialogDescription>
				The hub counts every admitted task. When the day's limit is reached it holds the catalog
				until the window has room again, plus the catalog's safety jitter. Concurrency uses the
				configured limit.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={save} class="space-y-4">
			<label class="grid gap-1 text-sm font-medium">
				Daily task limit
				<Input type="number" min="1" step="1" bind:value={dailyTaskLimit} required />
			</label>
			<label class="grid gap-1 text-sm font-medium">
				Daily window
				<select
					bind:value={quotaWindow}
					class="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
				>
					<option value="rolling">Rolling 24 hours</option>
					<option value="calendar">Calendar day</option>
				</select>
			</label>
			{#if quotaWindow === 'calendar'}
				<label class="grid gap-1 text-sm font-medium">
					Reset timezone
					<Input bind:value={timezone} placeholder="UTC or an IANA name like America/Los_Angeles" />
				</label>
			{/if}
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Cancel</Button>
				<Button type="submit" disabled={catalogs.saving}>Save quota policy</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
