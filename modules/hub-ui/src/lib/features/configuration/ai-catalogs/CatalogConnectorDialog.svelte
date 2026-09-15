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
	import type { CatalogDialogProps } from './catalog-kinds';

	let { catalog, catalogs, onclose }: CatalogDialogProps = $props();

	let open = $state(true);
	let connectorId = $state(untrack(() => catalog.connector_id ?? ''));
	const candidates = $derived(
		catalogs.connectors.filter((item) => item.provider === catalog.connector_provider)
	);

	$effect(() => {
		if (!open) onclose();
	});

	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (await catalogs.setConnector(catalog.key, connectorId || null)) open = false;
	}
</script>

<Dialog bind:open>
	<DialogContent>
		<DialogHeader>
			<DialogTitle>Catalog connector</DialogTitle>
			<DialogDescription>
				Work on this catalog authenticates with the selected {catalog.connector_provider} connector.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={save} class="space-y-4">
			<label class="grid gap-1 text-sm font-medium">
				Provider connector
				<select
					bind:value={connectorId}
					class="h-9 rounded-md border border-input bg-transparent px-3 text-sm"
				>
					<option value="">No connector</option>
					{#each candidates as connector (connector.id)}
						<option value={connector.id}
							>{connector.name}{connector.enabled ? '' : ' (disabled)'}</option
						>
					{/each}
				</select>
			</label>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Cancel</Button>
				<Button type="submit" disabled={catalogs.saving}>Save connector</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
