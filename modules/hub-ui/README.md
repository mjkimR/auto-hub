# Hub UI (Svelte 5)

Frontend management console for **Auto-Hub Scheduler Manager**, built with:

- **Framework**: Svelte 5 (Runes mode), SvelteKit 2 SPA mode
- **Bundler**: Vite 8
- **Styling**: Tailwind CSS v4, shadcn-svelte (bits-ui)
- **API Client**: openapi-typescript + openapi-fetch
- **Validation**: Zod + sveltekit-superforms

---

## Getting Started

### Development Server

Runs on port 5173 and proxies `/api` calls to the Python backend on `http://127.0.0.1:8389`:

```bash
just dev-run hub-ui
# Or from repo root:
npm --prefix modules/hub-ui run dev
```

### Static Type Check

Runs `svelte-check` against the TypeScript configuration:

```bash
just check hub-ui
# Or directly:
npm --prefix modules/hub-ui run check
```

### Code Formatting & Linting

```bash
just lint hub-ui
# Or fix formatting:
npm --prefix modules/hub-ui run format
```

### OpenAPI Client Generation

Regenerates `src/lib/api/schema.d.ts` directly from the FastAPI backend schema:

```bash
just gen-ui-api
```
