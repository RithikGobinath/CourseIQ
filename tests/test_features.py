import pandas as pd

from src.pipeline.features import compute_gpa, decode_term_code, modal_grade


def test_decode_term_code_fall():
    assert decode_term_code(1092) == (2008, "Fall")
    assert decode_term_code(1242) == (2023, "Fall")


def test_decode_term_code_spring():
    assert decode_term_code(1224) == (2022, "Spring")


def test_compute_gpa_all_a():
    row = pd.Series({"a_count": 10, "ab_count": 0, "b_count": 0, "bc_count": 0, "c_count": 0, "d_count": 0, "f_count": 0})
    assert compute_gpa(row) == 4.0


def test_compute_gpa_mixed():
    row = pd.Series({"a_count": 5, "ab_count": 0, "b_count": 5, "bc_count": 0, "c_count": 0, "d_count": 0, "f_count": 0})
    assert compute_gpa(row) == 3.5


def test_modal_grade_picks_max():
    row = pd.Series({"a_count": 3, "ab_count": 1, "b_count": 10, "bc_count": 2, "c_count": 0, "d_count": 0, "f_count": 0})
    assert modal_grade(row) == "B"
