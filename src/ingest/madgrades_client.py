"""Client for the Madgrades API (api.madgrades.com).

Pulls UW-Madison course metadata and historical grade distributions.
Requires a MADGRADES_API_TOKEN - request one at https://madgrades.com/data.

Response shapes below are confirmed against live API responses (the Rails
app camelizes JSON keys, which isn't visible in the jbuilder source alone):

GET /v1/courses (paginated):
    {currentPage, totalPages, totalCount, nextPageUrl,
     results: [{uuid, number, name, names, subjects: [{name, abbreviation, code}], url}]}

GET /v1/courses/{uuid}/grades - the actual source of GPA + per-instructor
grade distributions:
    {courseUuid,
     cumulative: {total, aCount, abCount, bCount, bcCount, cCount, dCount,
                  fCount, sCount, uCount, crCount, nCount, pCount, iCount,
                  nwCount, nrCount, otherCount},
     courseOfferings: [{
         termCode,
         cumulative: {...same grade count fields},
         sections: [{sectionNumber, instructors: [{id, name}, ...], ...same grade count fields}]
     }]}
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

import requests

from src.ingest.gcs_utils import upload_dataset

BASE_URL = "https://api.madgrades.com/v1"
RAW_DIR = Path("data/raw/madgrades")


class MadgradesClient:
    def __init__(self, api_token: str | None = None, session: requests.Session | None = None):
        self.api_token = api_token or os.environ["MADGRADES_API_TOKEN"]
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Token token={self.api_token}"})

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def iter_courses(self, page_size: int = 100):
        """Yield every course, following the API's nextPageUrl pagination."""
        url = f"{BASE_URL}/courses"
        params = {"per_page": page_size}
        while url:
            data = self._get(url, params=params)
            yield from data["results"]
            url = data.get("nextPageUrl")
            params = None  # nextPageUrl already carries its own query string
            if url:
                time.sleep(0.2)  # be polite to the API

    def get_course_grades(self, course_uuid: str) -> dict:
        """Cumulative + per-term + per-section-instructor grade distribution for one course."""
        return self._get(f"{BASE_URL}/courses/{course_uuid}/grades")


def fetch_all_courses(client: MadgradesClient, out_dir: Path = RAW_DIR) -> Path:
    """Pull every course's metadata and write raw JSON to disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    courses = list(client.iter_courses())

    out_path = out_dir / "courses.json"
    out_path.write_text(json.dumps(courses, indent=2))
    print(f"Wrote {len(courses)} courses to {out_path}")
    return out_path


def fetch_all_grade_distributions(
    client: MadgradesClient, courses: list[dict], out_dir: Path = RAW_DIR
) -> Path:
    """Pull grade distributions (incl. GPA and per-instructor breakdowns) for every course.

    One request per course, so this is the slow, rate-limited step for 5,600+ courses.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    distributions = []
    for i, course in enumerate(courses, start=1):
        try:
            distributions.append(client.get_course_grades(course["uuid"]))
        except requests.HTTPError as exc:
            print(f"Skipping {course.get('number')} ({course['uuid']}): {exc}")
        if i % 50 == 0:
            print(f"  fetched grades for {i}/{len(courses)} courses")
        time.sleep(0.2)

    out_path = out_dir / "grade_distributions.json"
    out_path.write_text(json.dumps(distributions, indent=2))
    print(f"Wrote grade distributions for {len(distributions)} courses to {out_path}")
    return out_path


def run(upload: bool = True) -> None:
    client = MadgradesClient()
    courses_path = fetch_all_courses(client)
    courses = json.loads(courses_path.read_text())
    grades_path = fetch_all_grade_distributions(client, courses)

    if upload and os.environ.get("GCS_BUCKET_RAW"):
        run_date = date.today().strftime("%Y%m%d")
        upload_dataset(courses_path, dataset="madgrades", run_date=run_date)
        upload_dataset(grades_path, dataset="madgrades", run_date=run_date)


if __name__ == "__main__":
    run()
