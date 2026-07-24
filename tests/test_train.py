import pandas as pd

from src.model.train import build_design_matrix, majority_class_baseline


def test_majority_class_baseline_accuracy_unweighted():
    y_train = pd.Series(["A", "A", "A", "B"])
    y_test = pd.Series(["A", "A", "B"])
    w_train = pd.Series([1, 1, 1, 1])
    w_test = pd.Series([1, 1, 1])
    # majority class is "A"; 2 of 3 test rows are "A"
    assert majority_class_baseline(y_train, y_test, w_train, w_test) == 2 / 3


def test_majority_class_baseline_respects_weights():
    # unweighted majority would be "A" (2 rows) but "B"'s single row
    # represents far more enrolled students, so weighted majority is "B"
    y_train = pd.Series(["A", "A", "B"])
    w_train = pd.Series([1, 1, 100])
    y_test = pd.Series(["B", "B", "A"])
    w_test = pd.Series([50, 50, 1])
    # predicting "B" gets both B rows right (weight 100) out of 101 total
    assert majority_class_baseline(y_train, y_test, w_train, w_test) == 100 / 101


def test_build_design_matrix_has_expected_columns():
    df = pd.DataFrame(
        {
            "subject_code": ["266", "266"],
            "semester": ["Fall", "Spring"],
            "number": [300, 300],
            "enrollment": [50, 40],
            "avg_rating": [4.1, None],
            "avg_difficulty": [2.9, None],
            "would_take_again_percent": [80.0, None],
            "num_ratings": [12, None],
        }
    )
    X, columns = build_design_matrix(df)
    assert "number" in X.columns
    assert "avg_rating" in X.columns
    assert any(c.startswith("subject_code_") for c in X.columns)
    assert len(X) == 2
