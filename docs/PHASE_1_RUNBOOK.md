# Denmark Academy Phase 1 Runbook

## Local startup

```powershell
docker compose -f infra/compose/docker-compose.local.yml up --build
```

API:

```text
http://localhost:8000
```

Health:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
```

Run migrations:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/admin/db/migrate
```

Dry-run ingestion against the mounted workspace:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/admin/ingestion/manifests `
  -ContentType "application/json" `
  -Body '{"root_path":"/data/material","dry_run":true}'
```

Full ingestion:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/admin/ingestion/runs `
  -ContentType "application/json" `
  -Body '{"root_path":"/data/material","upsert_qdrant":true}'
```

Search retrieval:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/admin/retrieval/search `
  -ContentType "application/json" `
  -Body '{"track":"pr","query":"grundloven","limit":5}'
```

## Local CLI dry-run without Docker

```powershell
$env:PYTHONPATH="packages"
python -m apps.worker_ingestion.main . --dry-run
```

## Notes

- Official questions are immutable at PostgreSQL trigger level.
- AI explanations are drafts until approved through the admin approval endpoint.
- The current embedding provider is deterministic and local. It proves the Qdrant plumbing; replace it with a production embedding provider before learner-facing semantic UX.

