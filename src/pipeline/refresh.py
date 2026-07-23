"""Entrypoint for the scheduled refresh job.

Runs the full ingest -> GCS -> BigQuery cycle in one process: pull the
latest Madgrades and RMP data, version it in GCS, then reload the BigQuery
tables. This is what the Cloud Run job (see infra/) executes on a schedule
so the dataset stays current without a manual rerun.
"""
from __future__ import annotations

from src.ingest import madgrades_client, rmp_client
from src.pipeline import gcs_to_bq


def run() -> None:
    print("== Refreshing Madgrades data ==")
    madgrades_client.run()

    print("== Refreshing RMP data ==")
    rmp_client.run()

    print("== Reloading BigQuery tables ==")
    gcs_to_bq.run()

    print("== Refresh complete ==")


if __name__ == "__main__":
    run()
