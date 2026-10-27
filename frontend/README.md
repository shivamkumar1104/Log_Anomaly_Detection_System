# Anomaly Detect frontend

Next.js App Router frontend for the Python FastAPI log analysis backend. Users can adjust
the expected anomaly rate and alert grouping window; detector selection is automatic and
there is no model selector.

No external AI service or API key is used. Analysis runs locally in the backend.

## Local development

From the repository root, install frontend packages and copy the environment example:

```powershell
npm --prefix frontend ci
Copy-Item frontend\.env.local.example frontend\.env.local
Push-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Pop-Location
```

Create the backend environment file from the repository root:

```powershell
Copy-Item backend\.env.example backend\.env
```

In one terminal, start FastAPI from the `backend` folder:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn log_anomaly.api.app:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

In a second terminal:

```powershell
npm --prefix frontend run dev
```

Open http://localhost:3000. The backend base URL can be changed with
`NEXT_PUBLIC_API_BASE_URL`. Keep the API bound to localhost unless authentication,
authorization, and deployment security are configured.

## Checks

```powershell
npm --prefix frontend run lint
npm --prefix frontend run build
```
