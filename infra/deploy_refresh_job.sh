#!/usr/bin/env bash
# Build the training image, push it to Artifact Registry, deploy it as a
# Cloud Run Job, and wire up a Cloud Scheduler job to trigger it weekly.
#
# Run manually whenever the pipeline code changes; this doesn't run itself.
# Requires: gcloud CLI authenticated, GCP_PROJECT_ID / GCP_REGION set,
# Artifact Registry repo "courseiq" already created.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
REPO="courseiq"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/refresh:latest"
JOB_NAME="courseiq-refresh"
SCHEDULER_NAME="courseiq-weekly-refresh"
SERVICE_ACCOUNT="courseiq-refresh@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Building and pushing ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" .

echo "Deploying Cloud Run job ${JOB_NAME}"
gcloud run jobs deploy "${JOB_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --command "python" \
  --args "-m,src.pipeline.refresh" \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCS_BUCKET_RAW=courseiq-raw,BQ_DATASET=courseiq" \
  --set-secrets "MADGRADES_API_TOKEN=madgrades-api-token:latest" \
  --service-account "${SERVICE_ACCOUNT}" \
  --max-retries 1 \
  --task-timeout 3600

echo "Creating/updating Cloud Scheduler job ${SCHEDULER_NAME}"
gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
  --location "${REGION}" \
  --schedule "0 6 * * 1" \
  --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --http-method POST \
  --oauth-service-account-email "${SERVICE_ACCOUNT}" \
  || gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
  --location "${REGION}" \
  --schedule "0 6 * * 1" \
  --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
  --http-method POST \
  --oauth-service-account-email "${SERVICE_ACCOUNT}"

echo "Done. Job runs every Monday 06:00 in ${REGION}."
