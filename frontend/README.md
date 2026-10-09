# AdFlow dashboard

For the local Compose demo, install dependencies and build the production bundle here,
then prepare and start the project from the repository root. Open
<http://127.0.0.1:5174>. Compose packages the Vite bundle into a small Node runtime
container. The dashboard serves the bundle and proxies only GET requests under `/api/*`
and `/health/*` to the backend service. It includes no management controls.

For frontend development, run the FastAPI backend at `http://127.0.0.1:8000`, then from
this directory:

```powershell
npm ci
npm run dev
```

Vite proxies `/api` and `/health` to the backend. The dashboard is read-only and uses the
typed summary endpoints; it never downloads raw events. Polling pauses while hidden or
manually paused, prevents overlapping requests, and retains the last successful response
with a stale label if a refresh fails.

```powershell
npm run lint
$env:NODE_OPTIONS='--max-old-space-size=2048'
npm run build
```
