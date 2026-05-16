# Cloud Deployment Blueprint

This is the intended Google Cloud shape for the paid async-run platform. Do not create all of this before the local ACVR1/FOP run is scientifically credible.

## Minimal Services

- Frontend: Cloud Run service or Vercel.
- API: Cloud Run service.
- Worker: Cloud Run Job for short async runs.
- Heavy worker: Google Cloud Batch for long or high-memory runs.
- Database: Cloud SQL Postgres.
- Artifacts: Cloud Storage bucket.
- Secrets: Secret Manager.
- Queue: Postgres `runs` table first; Pub/Sub later.
- Billing: Stripe Checkout or credits ledger.

## Run Lifecycle

1. User creates an objective.
2. API validates run config: agents, budget, runtime, strictness, human review.
3. API estimates cost.
4. User pays or spends internal credits.
5. API creates `runs.status = queued`.
6. Cloud Run Job or Batch task executes `python -m app.services.queue_worker`.
7. Worker marks run `running`, executes the state machine, persists traces/tool calls/evidence/board posts.
8. User returns to `/runs/{run_id}` and `/reports/{run_id}`.

## First GCP Resources

```powershell
gcloud projects create bio-auto-scientist-dev
gcloud config set project bio-auto-scientist-dev
gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
```

Create:

- Artifact Registry repo for Docker images.
- Cloud SQL Postgres instance.
- Cloud Storage bucket for reports and raw tool outputs.
- Secret Manager entries for database URL, LLM keys, ToolUniverse keys, and Stripe keys.

## Deployment Commands

Build and push images after configuring Artifact Registry:

```powershell
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/bio-auto-scientist/api:latest -f infra/docker/api.Dockerfile .
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/bio-auto-scientist/worker:latest -f infra/docker/worker.Dockerfile .
```

Deploy API:

```powershell
gcloud run deploy bio-auto-scientist-api `
  --image REGION-docker.pkg.dev/PROJECT/bio-auto-scientist/api:latest `
  --region REGION `
  --allow-unauthenticated `
  --set-env-vars PYTHONPATH=/app,TOOL_MODE=mock
```

Create worker job:

```powershell
gcloud run jobs create bio-auto-scientist-worker `
  --image REGION-docker.pkg.dev/PROJECT/bio-auto-scientist/worker:latest `
  --region REGION `
  --set-env-vars PYTHONPATH=/app,TOOL_MODE=mock
```

Execute worker job:

```powershell
gcloud run jobs execute bio-auto-scientist-worker --region REGION
```

## Payment/Credits Model

Start with internal credits in the database. Add Stripe only after:

- runs can be queued reliably,
- estimates are visible before submission,
- failed runs produce a useful failure record,
- costs are logged per run.

Suggested first pricing dimensions:

- base platform fee,
- agent count,
- reserved runtime,
- tool budget,
- strictness multiplier,
- optional GPU/model scorer surcharge.

