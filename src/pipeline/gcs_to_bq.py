"""Load the latest versioned raw data from GCS into BigQuery.

Pulls the newest courses.json / grade_distributions.json / instructor_ratings.json
from GCS, flattens the nested Madgrades grade JSON into one row per
course-offering x section x instructor, fuzzy-matches instructors against
RMP, and writes four clean tables to BigQuery: courses, grade_distributions,
rmp_ratings, instructor_match.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from src.ingest.gcs_utils import download_dataset
from src.pipeline.match_instructors import match_instructors

# Madgrades' JSON is camelCase (confirmed against live responses); these
# snake_case names are what we store in our own tables/DataFrames.
GRADE_COUNT_FIELDS = {
    "total": "total", "aCount": "a_count", "abCount": "ab_count", "bCount": "b_count",
    "bcCount": "bc_count", "cCount": "c_count", "dCount": "d_count", "fCount": "f_count",
    "sCount": "s_count", "uCount": "u_count", "crCount": "cr_count", "nCount": "n_count",
    "pCount": "p_count", "iCount": "i_count", "nwCount": "nw_count", "nrCount": "nr_count",
    "otherCount": "other_count",
}


def flatten_courses(raw_courses: list[dict]) -> pd.DataFrame:
    rows = []
    for course in raw_courses:
        subjects = course.get("subjects") or [{}]
        primary_subject = subjects[0]
        rows.append(
            {
                "uuid": course["uuid"],
                "number": course.get("number"),
                "name": course.get("name"),
                "subject_code": primary_subject.get("code"),
                "subject_name": primary_subject.get("name"),
                "subject_abbreviation": primary_subject.get("abbreviation"),
            }
        )
    return pd.DataFrame(rows)


def flatten_grade_distributions(raw_grades: list[dict]) -> pd.DataFrame:
    """One row per course-offering x section x instructor.

    A section can list multiple co-instructors; each gets its own row
    (sharing that section's grade counts) so per-instructor features can be
    aggregated later without losing the course-level grain.
    """
    rows = []
    for course_grades in raw_grades:
        course_uuid = course_grades.get("courseUuid")
        for offering in course_grades.get("courseOfferings", []):
            term_code = offering.get("termCode")
            for section in offering.get("sections", []):
                instructors = section.get("instructors") or [None]
                # instructors are {"id": ..., "name": ...} dicts, but handle
                # plain strings too in case that ever changes upstream
                names = [i["name"] if isinstance(i, dict) else i for i in instructors]
                for name in names:
                    row = {
                        "course_uuid": course_uuid,
                        "term_code": term_code,
                        "section_number": section.get("sectionNumber"),
                        "instructor_name": name,
                    }
                    row.update({snake: section.get(camel) for camel, snake in GRADE_COUNT_FIELDS.items()})
                    rows.append(row)
    return pd.DataFrame(rows)


def flatten_rmp_ratings(raw_ratings: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rmp_id": r["id"],
                "first_name": r.get("firstName"),
                "last_name": r.get("lastName"),
                "department": r.get("department"),
                "avg_rating": r.get("avgRating"),
                "avg_difficulty": r.get("avgDifficulty"),
                "would_take_again_percent": r.get("wouldTakeAgainPercent"),
                "num_ratings": r.get("numRatings"),
            }
            for r in raw_ratings
        ]
    )


def load_table(client: bigquery.Client, df: pd.DataFrame, table_id: str) -> None:
    job = client.load_table_from_dataframe(
        df, table_id, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()
    print(f"Loaded {len(df)} rows into {table_id}")


def run(tmp_dir: Path = Path("data/raw/_bq_staging")) -> None:
    project_id = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ.get("BQ_DATASET", "courseiq")

    courses_path = download_dataset("madgrades", "courses.json", tmp_dir)
    grades_path = download_dataset("madgrades", "grade_distributions.json", tmp_dir)
    ratings_path = download_dataset("rmp", "instructor_ratings.json", tmp_dir)

    courses_df = flatten_courses(json.loads(courses_path.read_text()))
    grades_df = flatten_grade_distributions(json.loads(grades_path.read_text()))
    rmp_df = flatten_rmp_ratings(json.loads(ratings_path.read_text()))
    match_df = match_instructors(grades_df["instructor_name"].dropna().unique().tolist(), rmp_df)

    bq = bigquery.Client(project=project_id)
    load_table(bq, courses_df, f"{project_id}.{dataset}.courses")
    load_table(bq, grades_df, f"{project_id}.{dataset}.grade_distributions")
    load_table(bq, rmp_df, f"{project_id}.{dataset}.rmp_ratings")
    load_table(bq, match_df, f"{project_id}.{dataset}.instructor_match")


if __name__ == "__main__":
    run()
