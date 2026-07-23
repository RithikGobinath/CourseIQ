"""Client for the Madgrades API (api.madgrades.com).

Pulls UW-Madison course metadata and historical grade distributions.
Requires a MADGRADES_API_TOKEN - request one at https://madgrades.com/data.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE_URL = "https://api.madgrades.com/v1"
RAW_DIR = Path("data/raw/madgrades")


class MadgradesClient:
    def __init__(self, api_token: str | None = None, session: requests.Session | None = None):
        self.api_token = api_token or os.environ["MADGRADES_API_TOKEN"]
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Token token={self.api_token}"})

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def iter_courses(self, page_size: int = 100):
        """Yield every course, following pagination."""
        params = {"per_page": page_size, "page": 1}
        while True:
            data = self._get("/courses", params=params)
            yield from data["results"]
            if not data.get("next"):
                break
            params["page"] += 1
            time.sleep(0.2)  # be polite to the API

    def get_course(self, course_uuid: str) -> dict:
        return self._get(f"/courses/{course_uuid}")

    def get_grade_distributions(self, course_uuid: str) -> list[dict]:
        """Grade distributions for every offering (term x instructor) of a course."""
        course = self.get_course(course_uuid)
        return course.get("courseOfferings", [])


def fetch_all_courses(client: MadgradesClient, out_dir: Path = RAW_DIR) -> Path:
    """Pull every course + grade distribution and write raw JSON to disk."""
    out_dir.mkdir(parents=True, exist_ok=True)
    courses = list(client.iter_courses())

    out_path = out_dir / "courses.json"
    out_path.write_text(json.dumps(courses, indent=2))
    print(f"Wrote {len(courses)} courses to {out_path}")
    return out_path


if __name__ == "__main__":
    client = MadgradesClient()
    fetch_all_courses(client)
