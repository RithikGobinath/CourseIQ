"""Upload raw ingestion output to GCS with date-based versioning.

Layout: gs://<bucket>/<dataset>/v<YYYYMMDD>/<filename>
Each ingestion run gets its own dated prefix so raw pulls are never
overwritten - downstream pipeline steps pin to a specific version.
"""
from __future__ import annotations

import os
from pathlib import Path

from google.cloud import storage


def upload_dataset(local_path: Path, dataset: str, run_date: str, bucket_name: str | None = None) -> str:
    """Upload a local file to gs://<bucket>/<dataset>/v<run_date>/<filename>.

    run_date should be an YYYYMMDD string, passed in by the caller (the
    ingestion script) rather than computed here, so this stays deterministic
    and testable.
    """
    bucket_name = bucket_name or os.environ["GCS_BUCKET_RAW"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blob_path = f"{dataset}/v{run_date}/{local_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(local_path))

    gcs_uri = f"gs://{bucket_name}/{blob_path}"
    print(f"Uploaded {local_path} -> {gcs_uri}")
    return gcs_uri


def latest_version(dataset: str, bucket_name: str | None = None) -> str | None:
    """Return the most recent vYYYYMMDD prefix for a dataset, or None if empty."""
    bucket_name = bucket_name or os.environ["GCS_BUCKET_RAW"]
    client = storage.Client()
    prefixes = client.list_blobs(bucket_name, prefix=f"{dataset}/", delimiter="/")
    list(prefixes)  # populate .prefixes
    versions = sorted(p.removeprefix(f"{dataset}/") for p in prefixes.prefixes)
    return versions[-1].rstrip("/") if versions else None


def download_dataset(dataset: str, filename: str, dest_dir: Path, version: str | None = None, bucket_name: str | None = None) -> Path:
    """Download <dataset>/<version>/<filename> from GCS, defaulting to the latest version."""
    bucket_name = bucket_name or os.environ["GCS_BUCKET_RAW"]
    version = version or latest_version(dataset, bucket_name)
    if version is None:
        raise FileNotFoundError(f"No versions of dataset {dataset!r} found in gs://{bucket_name}")

    client = storage.Client()
    blob = client.bucket(bucket_name).blob(f"{dataset}/{version}/{filename}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    blob.download_to_filename(str(dest_path))
    print(f"Downloaded gs://{bucket_name}/{blob.name} -> {dest_path}")
    return dest_path
