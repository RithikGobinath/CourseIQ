"""Fuzzy-match Madgrades instructor names to RMP instructor records.

Madgrades and RMP share no common instructor ID, so this is the join key
for bringing RMP ratings into the training features. Uses token_sort_ratio
so word order ("Last First" vs "First Last") doesn't matter, and keeps only
matches above a confidence threshold - everything else is left unmatched
rather than forced to a wrong professor.
"""
from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz, process

MIN_MATCH_SCORE = 85.0  # 0-100; below this we'd rather have a missing match than a wrong one


def match_instructors(madgrades_names: list[str], rmp_df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of madgrades_instructor_name, rmp_id, match_score.

    rmp_df must have columns: rmp_id, first_name, last_name.
    """
    rmp_full_names = (rmp_df["first_name"] + " " + rmp_df["last_name"]).tolist()
    rmp_ids = rmp_df["rmp_id"].tolist()

    rows = []
    for name in set(madgrades_names):
        if not name:
            continue
        match = process.extractOne(name, rmp_full_names, scorer=fuzz.token_sort_ratio)
        if match is None:
            rows.append({"madgrades_instructor_name": name, "rmp_id": None, "match_score": None})
            continue

        _, score, idx = match
        rows.append(
            {
                "madgrades_instructor_name": name,
                "rmp_id": rmp_ids[idx] if score >= MIN_MATCH_SCORE else None,
                "match_score": score,
            }
        )

    return pd.DataFrame(rows)
