export const API_KEY_HEADER = 'X-API-Key';
export const API_KEY_STORAGE = 'scheduler-api-key';

export function apiBaseUrl(): string {
	if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) {
		return import.meta.env.VITE_API_BASE_URL;
	}
	return '';
}
