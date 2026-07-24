import pandas as pd

from src.pipeline.match_instructors import match_instructors


def test_matches_across_case_difference():
    # Madgrades names are ALL CAPS, RMP names are Title Case - this is the
    # exact bug that silently produced a 4/21302 match rate before the fix.
    rmp_df = pd.DataFrame(
        {
            "rmp_id": ["r1", "r2"],
            "first_name": ["Stephanie", "John"],
            "last_name": ["Kann", "Archambault"],
        }
    )
    result = match_instructors(["STEPHANIE KANN", "JOHN ARCHAMBAULT"], rmp_df)
    matched = result.set_index("madgrades_instructor_name")["rmp_id"]

    assert matched["STEPHANIE KANN"] == "r1"
    assert matched["JOHN ARCHAMBAULT"] == "r2"


def test_no_match_below_threshold():
    rmp_df = pd.DataFrame({"rmp_id": ["r1"], "first_name": ["Nisa"], "last_name": ["Karimi"]})
    result = match_instructors(["COMPLETELY DIFFERENT NAME"], rmp_df)
    assert result.iloc[0]["rmp_id"] is None
