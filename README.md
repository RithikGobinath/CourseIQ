# CourseIQ

Grade outcome classifier for UW–Madison courses, built on [Madgrades](https://madgrades.com) grade history and RateMyProfessor instructor ratings. Predicts the modal grade (A/AB/B/BC/C/D/F) for a course offering using historical GPA trends, course metadata, and instructor rating data.

## Architecture

```
Madgrades API ──┐
                 ├──> GCS (raw, date-versioned) ──> BigQuery (clean tables) ──> features.py ──> train.py (XGBoost + MLflow)
RMP GraphQL ────┘
```

- **Ingestion** (`src/ingest/`) — pulls course/grade data from Madgrades and instructor ratings from RateMyProfessors, writes raw JSON versioned by pull date to GCS (`gs://<bucket>/<dataset>/vYYYYMMDD/...`).
- **Pipeline** (`src/pipeline/`) — flattens the nested Madgrades grade JSON to one row per section-instructor, fuzzy-matches instructor names against RMP (no shared ID between the two sources), loads clean tables into BigQuery, and builds the model-ready feature table.
- **Model** (`src/model/`) — majority-class baseline vs. an Optuna-tuned XGBoost multiclass classifier, both logged to MLflow with a time-based train/test split (holds out the most recent academic year, since a random split would leak repeating course/instructor patterns).
- **Refresh** (`src/pipeline/refresh.py`) — chains ingest → GCS → BigQuery into one entrypoint, deployed as a scheduled Cloud Run Job (see [infra/](infra/)).

## Setup

```bash
pip install -e .
cp .env.example .env   # fill in MADGRADES_API_TOKEN, GCP_PROJECT_ID, etc.
```

Get a Madgrades API token at [madgrades.com/data](https://madgrades.com/data).

### Run locally

```bash
python -m src.ingest.madgrades_client   # pulls courses + grade distributions
python -m src.ingest.rmp_client         # pulls instructor ratings
python -m src.pipeline.gcs_to_bq        # loads BigQuery tables
python -m src.model.train               # trains baseline + XGBoost, logs to MLflow
```

### Run with Docker

```bash
docker compose up mlflow   # tracking server at localhost:5000
docker compose run train
```

### Tests

```bash
pip install -e ".[dev]"
pytest
```

## Scheduled refresh

`infra/deploy_refresh_job.sh` deploys `refresh.py` as a Cloud Run Job triggered weekly by Cloud Scheduler, so the dataset and BigQuery tables stay current without a manual rerun. See [infra/README.md](infra/README.md) for one-time GCP setup.

## Stack

Python · XGBoost · MLflow · Docker · BigQuery · Google Cloud Storage
