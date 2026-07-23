# Infra

`deploy_refresh_job.sh` builds the training image, deploys it as a Cloud Run
Job (`courseiq-refresh`), and points a Cloud Scheduler job at it so
`src/pipeline/refresh.py` reruns weekly (Mondays 06:00) without a manual
trigger.

## One-time setup (not scripted - run once by hand)

```bash
gcloud artifacts repositories create courseiq --repository-format=docker --location=us-central1

gcloud iam service-accounts create courseiq-refresh \
  --display-name "CourseIQ scheduled refresh"

# grant the service account access to GCS + BigQuery + Cloud Run invocation
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member "serviceAccount:courseiq-refresh@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role roles/storage.objectAdmin
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member "serviceAccount:courseiq-refresh@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role roles/bigquery.dataEditor
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member "serviceAccount:courseiq-refresh@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role roles/run.invoker

# store the Madgrades token as a secret rather than a plain env var
echo -n "$MADGRADES_API_TOKEN" | gcloud secrets create madgrades-api-token --data-file=-
```

## Redeploy after code changes

```bash
export GCP_PROJECT_ID=your-project-id
./infra/deploy_refresh_job.sh
```
