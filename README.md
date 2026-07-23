# CourseIQ

Grade outcome classifier for UW–Madison courses, built on top of [Madgrades](https://madgrades.com) grade history and RateMyProfessor instructor ratings.

## Status

Early scaffolding — data ingestion, pipeline, and model code are being built out incrementally. See commit history for progress.

## Stack

- Python
- XGBoost + MLflow for training/tracking
- Google Cloud Storage for versioned raw/processed datasets
- BigQuery for querying and feature aggregation
- Docker for reproducible training runs
