import createClient, { type Client } from 'openapi-fetch';
import { API_KEY_HEADER, apiBaseUrl } from '$lib/config';
import { session } from '$lib/stores/session.svelte';
import type { paths } from './schema';

export class ApiError extends Error {
	constructor(
		readonly status: number,
		readonly path: string,
		message?: string
	) {
		super(message ?? `${path} failed with status ${status}`);
		this.name = 'ApiError';
	}
}

export function createApiClient(): Client<paths> {
	const client = createClient<paths>({
		baseUrl:
			apiBaseUrl() ||
			(typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8389')
	});

	// Register middleware for headers and 401 handling
	client.use({
		onRequest({ request }) {
			if (session.apiKey) {
				request.headers.set(API_KEY_HEADER, session.apiKey);
			}
			return request;
		},
		onResponse({ response }) {
			if (response.status === 401) {
				session.logout();
			}
			return response;
		}
	});

	return client;
}

export const api = createApiClient();
