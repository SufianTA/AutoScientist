# Cloud Deployment Blueprint

This is an optional bring-your-own-cloud deployment shape. The primary product is a local open-source framework; cloud execution is a backend option for runs that need days of background work or larger machines.

## Minimal Services

- Frontend: Cloud Run service or Vercel.
- API: Cloud Run service.
- Worker: Cloud Run Job for short async runs.
- Heavy worker: Google Cloud Batch for long or high-memory runs.
- Database: Cloud SQL Postgres.
- Artifacts: Cloud Storage bucket.
- Secrets: Secret Manager.
- Queue: Postgres `runs` table first; Pub/Sub later.
- Identity: user authenticates with their own cloud provider outside the local framework.

## Run Lifecycle

1. User creates an objective.
2. API validates run config: agents, budget, runtime, strictness, human review.
3. API estimates resource units.
4. API creates `runs.status = queued`.
5. Local worker, Cloud Run Job, or Batch task executes `python -m app.services.queue_worker`.
6. Worker marks run `running`, executes the state machine, persists traces/tool calls/evidence/board posts.
7. User returns to `/runs/{run_id}` and `/reports/{run_id}`.

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
- Secret Manager entries for database URL, LLM keys, ToolUniverse keys, and custom model keys.

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

## Local-First Model

Do not build payments into the core framework. Users run locally or bring their own cloud account. The framework should provide:

- resource estimates,
- exact job specs,
- reproducible tool and model configs,
- durable traces and board posts,
- optional cloud backend adapters.
