import type { Component } from 'svelte';
import { dailyQuotaSummary, type AICatalog, type AICatalogsState } from './ai-catalogs.svelte';
import CodexRefreshPolicyDialog from './CodexRefreshPolicyDialog.svelte';
import DailyQuotaPolicyDialog from './DailyQuotaPolicyDialog.svelte';

/** Props every catalog dialog receives; the dialog calls `onclose` once it has closed. */
export type CatalogDialogProps = {
	catalog: AICatalog;
	catalogs: AICatalogsState;
	onclose: () => void;
};

/** Per-kind UI for a catalog's quota policy. A kind without an entry shows no policy editor. */
export type CatalogKindUi = {
	policyLabel: string;
	policyDialog: Component<CatalogDialogProps>;
	summary?: (catalog: AICatalog) => string;
};

export const catalogKinds: Partial<Record<AICatalog['kind'], CatalogKindUi>> = {
	codex: { policyLabel: 'Refresh policy', policyDialog: CodexRefreshPolicyDialog },
	jules: {
		policyLabel: 'Quota policy',
		policyDialog: DailyQuotaPolicyDialog,
		summary: dailyQuotaSummary
	}
};
