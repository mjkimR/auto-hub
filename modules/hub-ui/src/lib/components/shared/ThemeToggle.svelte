<script lang="ts">
	import { toggleMode } from 'mode-watcher';
	import { Sun, Moon } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button';

	let { class: className = '' } = $props();
</script>

<Button
	variant="outline"
	size="icon"
	onclick={toggleMode}
	class={className}
	aria-label="Toggle theme"
>
	<Sun class="size-4 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
	<Moon class="absolute size-4 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
</Button>
