<script lang="ts">
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Code2, SlidersHorizontal, AlertCircle } from '@lucide/svelte';

	interface JsonSchemaProperty {
		type?: string;
		title?: string;
		description?: string;
		default?: unknown;
		enum?: string[];
		format?: string;
		items?: { type?: string; enum?: string[] };
	}

	interface JsonSchema {
		title?: string;
		description?: string;
		type?: string;
		properties?: Record<string, JsonSchemaProperty>;
		required?: string[];
	}

	let {
		schema = null,
		value = $bindable({}),
		disabled = false
	}: {
		schema?: JsonSchema | null;
		value?: Record<string, unknown>;
		disabled?: boolean;
	} = $props();

	let isRawMode = $state(false);
	let rawJson = $state('');
	let rawError = $state<string | null>(null);

	// Sync raw JSON when switching to raw mode
	function enableRawMode() {
		rawJson = JSON.stringify(value, null, 2);
		rawError = null;
		isRawMode = true;
	}

	function enableFormMode() {
		try {
			const parsed = JSON.parse(rawJson);
			if (typeof parsed === 'object' && parsed !== null) {
				value = parsed;
				rawError = null;
				isRawMode = false;
			} else {
				rawError = 'Root value must be an object';
			}
		} catch (err) {
			rawError = err instanceof Error ? err.message : 'Invalid JSON format';
		}
	}

	function handleRawChange(e: Event & { currentTarget: HTMLTextAreaElement }) {
		rawJson = e.currentTarget.value;
		try {
			const parsed = JSON.parse(rawJson);
			if (typeof parsed === 'object' && parsed !== null) {
				value = parsed;
				rawError = null;
			}
		} catch {
			// typing in progress
		}
	}

	function getFieldValue(key: string, prop: JsonSchemaProperty): unknown {
		if (value[key] !== undefined) return value[key];
		if (prop.default !== undefined) return prop.default;
		if (prop.type === 'boolean') return false;
		if (prop.type === 'integer' || prop.type === 'number') return 0;
		if (prop.type === 'array') return [];
		return '';
	}

	function updateFieldValue(key: string, val: unknown) {
		value = { ...value, [key]: val };
	}
</script>

<div class="space-y-4 rounded-xl border border-border/80 bg-card/50 p-4 backdrop-blur-sm">
	<!-- Schema Form Header / Mode Switcher -->
	<div class="flex items-center justify-between border-b border-border/60 pb-2">
		<div class="flex items-center gap-2">
			<SlidersHorizontal class="size-4 text-primary" />
			<span class="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
				Payload Configuration
			</span>
		</div>
		<div class="flex items-center gap-1.5">
			{#if isRawMode}
				<Button
					type="button"
					variant="outline"
					size="sm"
					class="h-7 gap-1.5 text-xs"
					onclick={enableFormMode}
				>
					<SlidersHorizontal class="size-3" />
					Form View
				</Button>
			{:else}
				<Button
					type="button"
					variant="ghost"
					size="sm"
					class="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
					onclick={enableRawMode}
				>
					<Code2 class="size-3" />
					Raw JSON
				</Button>
			{/if}
		</div>
	</div>

	<!-- Mode Body -->
	{#if isRawMode}
		<div class="space-y-2">
			{#if rawError}
				<div class="flex items-center gap-2 text-xs font-medium text-destructive">
					<AlertCircle class="size-3.5" />
					<span>{rawError}</span>
				</div>
			{/if}
			<textarea
				class="min-h-[160px] w-full rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
				value={rawJson}
				oninput={handleRawChange}
				{disabled}
				spellcheck="false"></textarea>
		</div>
	{:else if schema?.properties && Object.keys(schema.properties).length > 0}
		<div class="space-y-4">
			{#each Object.entries(schema.properties) as [key, prop] (key)}
				{@const isRequired = schema.required?.includes(key)}
				{@const currentVal = getFieldValue(key, prop)}

				<div class="space-y-1.5">
					<div class="flex items-center justify-between">
						<label
							for="field-{key}"
							class="flex items-center gap-1.5 text-xs font-semibold text-foreground"
						>
							<span>{prop.title || key}</span>
							{#if isRequired}
								<span class="text-destructive">*</span>
							{/if}
							<Badge variant="secondary" class="px-1 py-0 font-mono text-[9px] uppercase">
								{prop.type || 'any'}
							</Badge>
						</label>
					</div>

					{#if prop.description}
						<p class="text-[11px] leading-snug text-muted-foreground">
							{prop.description}
						</p>
					{/if}

					<!-- String with Enum -->
					{#if prop.enum && prop.enum.length > 0}
						<select
							id="field-{key}"
							class="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs focus:border-primary focus:outline-none"
							value={String(currentVal || '')}
							onchange={(e) => updateFieldValue(key, e.currentTarget.value)}
							{disabled}
						>
							<option value="" disabled>Select option...</option>
							{#each prop.enum as opt (opt)}
								<option value={opt}>{opt}</option>
							{/each}
						</select>

						<!-- Boolean Switch -->
					{:else if prop.type === 'boolean'}
						<label class="flex cursor-pointer items-center gap-2.5 pt-1">
							<input
								id="field-{key}"
								type="checkbox"
								class="size-4 rounded border-border text-primary focus:ring-primary"
								checked={Boolean(currentVal)}
								onchange={(e) => updateFieldValue(key, e.currentTarget.checked)}
								{disabled}
							/>
							<span class="text-xs text-muted-foreground">
								Enable {prop.title || key}
							</span>
						</label>

						<!-- Number / Integer -->
					{:else if prop.type === 'integer' || prop.type === 'number'}
						<Input
							id="field-{key}"
							type="number"
							value={Number(currentVal ?? 0)}
							oninput={(e: Event & { currentTarget: HTMLInputElement }) =>
								updateFieldValue(key, Number(e.currentTarget.value))}
							class="h-9 text-xs"
							{disabled}
						/>

						<!-- Standard String / Text -->
					{:else}
						<Input
							id="field-{key}"
							type="text"
							placeholder={prop.default ? `Default: ${prop.default}` : ''}
							value={String(currentVal ?? '')}
							oninput={(e: Event & { currentTarget: HTMLInputElement }) =>
								updateFieldValue(key, e.currentTarget.value)}
							class="h-9 text-xs"
							{disabled}
						/>
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<div
			class="rounded-lg border border-dashed border-border/80 p-4 text-center text-xs text-muted-foreground"
		>
			No payload schema parameters required for this task.
		</div>
	{/if}
</div>
