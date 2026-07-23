"""Client for RateMyProfessors' public GraphQL endpoint.

RMP has no official API. This talks to the same GraphQL endpoint their
website uses, scoped to a single school (UW-Madison), and paginates through
every instructor's rating summary. No login/token is required - RMP's web
client authenticates with a static, publicly-known basic auth value.

Be a polite citizen: this only pulls aggregate rating fields already shown
on public profile pages, not individual review text, and throttles requests.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"
# Static token RMP's own web client uses for unauthenticated GraphQL requests.
_AUTH = base64.b64encode(b"test:test").decode()
UW_MADISON_SCHOOL_NAME = "University of Wisconsin - Madison"
RAW_DIR = Path("data/raw/rmp")

SEARCH_SCHOOL_QUERY = """
query NewSearchSchoolsQuery($query: SchoolSearchQuery!) {
  newSearch {
    schools(query: $query) {
      edges { node { id name } }
    }
  }
}
"""

SEARCH_TEACHERS_QUERY = """
query TeacherSearchQuery($query: TeacherSearchQuery!, $after: String) {
  newSearch {
    teachers(query: $query, first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          id
          firstName
          lastName
          department
          avgRating
          avgDifficulty
          wouldTakeAgainPercent
          numRatings
        }
      }
    }
  }
}
"""


class RMPClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Basic {_AUTH}",
                "Content-Type": "application/json",
            }
        )

    def _graphql(self, query: str, variables: dict) -> dict:
        resp = self.session.post(
            GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=30
        )
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(body["errors"])
        return body["data"]

    def find_school_id(self, name: str = UW_MADISON_SCHOOL_NAME) -> str:
        data = self._graphql(SEARCH_SCHOOL_QUERY, {"query": {"text": name}})
        edges = data["newSearch"]["schools"]["edges"]
        if not edges:
            raise ValueError(f"No school found matching {name!r}")
        return edges[0]["node"]["id"]

    def iter_teachers(self, school_id: str):
        """Yield every instructor rating summary for a school, paginated."""
        after = None
        while True:
            data = self._graphql(
                SEARCH_TEACHERS_QUERY,
                {"query": {"text": "", "schoolID": school_id}, "after": after},
            )
            teachers = data["newSearch"]["teachers"]
            for edge in teachers["edges"]:
                yield edge["node"]

            page_info = teachers["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            after = page_info["endCursor"]
            time.sleep(0.3)  # be polite to the endpoint


def fetch_all_ratings(client: RMPClient, out_dir: Path = RAW_DIR) -> Path:
    """Pull every UW-Madison instructor's rating summary and write raw JSON."""
    out_dir.mkdir(parents=True, exist_ok=True)
    school_id = client.find_school_id()
    teachers = list(client.iter_teachers(school_id))

    out_path = out_dir / "instructor_ratings.json"
    out_path.write_text(json.dumps(teachers, indent=2))
    print(f"Wrote {len(teachers)} instructor ratings to {out_path}")
    return out_path


if __name__ == "__main__":
    client = RMPClient()
    fetch_all_ratings(client)
