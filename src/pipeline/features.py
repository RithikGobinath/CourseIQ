"""Build the course-offering-instructor feature table and target label.

Grain: one row per (course_uuid, term_code, instructor_name), aggregated up
from the section-level rows in `grade_distributions` (an instructor's
multiple sections in the same term are summed together).

Target: the modal grade bucket (A/AB/B/BC/C/D/F) - the single most common
grade awarded in that course offering. GPA is derived here from the raw
grade counts (UW-Madison grade points), since Madgrades' /grades endpoint
returns counts, not a precomputed GPA.
"""
from __future__ import annotations

import pandas as pd

GRADE_POINTS = {"a_count": 4.0, "ab_count": 3.5, "b_count": 3.0, "bc_count": 2.5, "c_count": 2.0, "d_count": 1.0, "f_count": 0.0}
GRADE_LABELS = {"a_count": "A", "ab_count": "AB", "b_count": "B", "bc_count": "BC", "c_count": "C", "d_count": "D", "f_count": "F"}
GRADED_COLUMNS = list(GRADE_POINTS)  # excludes S/U/CR/N/P/I/NW/NR/other - not GPA-bearing

TERM_SEMESTERS = {2: "Fall", 4: "Spring", 6: "Summer"}


def decode_term_code(term_code: int) -> tuple[int, str]:
    """Decode a Madgrades/UW term_code into (calendar_year, semester).

    Format confirmed against UW-Madison's registrar term code table:
    digit 1 = century (1 -> 1900s+100 = 2000s), digits 2-3 = academic year
    the term falls within (labeled by the year it ends), digit 4 = semester
    (2=Fall, 4=Spring, 6=Summer). Fall's calendar year is one less than the
    academic year's ending year.
    """
    century_digit = term_code // 1000
    academic_year_end = 1900 + century_digit * 100 + (term_code // 10) % 100
    semester = TERM_SEMESTERS[term_code % 10]
    calendar_year = academic_year_end - 1 if semester == "Fall" else academic_year_end
    return calendar_year, semester


def compute_gpa(row: pd.Series) -> float | None:
    graded_total = sum(row[col] for col in GRADED_COLUMNS)
    if not graded_total:
        return None
    return sum(row[col] * points for col, points in GRADE_POINTS.items()) / graded_total


def modal_grade(row: pd.Series) -> str | None:
    counts = {GRADE_LABELS[col]: row[col] for col in GRADED_COLUMNS}
    if sum(counts.values()) == 0:
        return None
    return max(counts, key=counts.get)


def aggregate_offerings(grades_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse section-level rows to one row per course_uuid x term_code x instructor."""
    group_cols = ["course_uuid", "term_code", "instructor_name"]
    count_cols = GRADED_COLUMNS + ["s_count", "u_count", "cr_count", "n_count", "p_count", "i_count", "nw_count", "nr_count", "other_count"]
    agg = grades_df.groupby(group_cols, as_index=False)[count_cols].sum()

    agg["gpa"] = agg.apply(compute_gpa, axis=1)
    agg["grade_label"] = agg.apply(modal_grade, axis=1)
    agg[["year", "semester"]] = agg["term_code"].apply(lambda t: pd.Series(decode_term_code(t)))
    return agg


def build_feature_table(
    courses_df: pd.DataFrame, grades_df: pd.DataFrame, rmp_df: pd.DataFrame, match_df: pd.DataFrame
) -> pd.DataFrame:
    """Join offering-level grades with course metadata and matched RMP ratings."""
    offerings = aggregate_offerings(grades_df)
    offerings = offerings.dropna(subset=["grade_label"])

    df = offerings.merge(courses_df, left_on="course_uuid", right_on="uuid", how="left")
    df = df.merge(match_df, left_on="instructor_name", right_on="madgrades_instructor_name", how="left")
    df = df.merge(rmp_df, on="rmp_id", how="left")

    df["enrollment"] = df[count_cols_present(df)].sum(axis=1)
    return df


def count_cols_present(df: pd.DataFrame) -> list[str]:
    all_count_cols = GRADED_COLUMNS + ["s_count", "u_count", "cr_count", "n_count", "p_count", "i_count", "nw_count", "nr_count", "other_count"]
    return [c for c in all_count_cols if c in df.columns]


def time_based_split(df: pd.DataFrame, test_years: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the most recent `test_years` academic years as the test set.

    A random split would leak information (the same course/instructor pair
    appears across terms with similar grade patterns), so splitting on time
    is the only way to get an honest read on generalization to future terms.
    """
    cutoff = df["year"].max() - test_years + 1
    train = df[df["year"] < cutoff]
    test = df[df["year"] >= cutoff]
    return train, test
