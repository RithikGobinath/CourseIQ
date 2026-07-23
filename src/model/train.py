"""Train the grade-outcome classifier: majority-class baseline + tuned XGBoost.

Reads the feature table (see src/pipeline/features.py), fits both models on
a time-based train/test split, and logs params/metrics/artifacts for every
run to MLflow so tuning runs are comparable and the best model can be
promoted from the registry.
"""
from __future__ import annotations

import os

import mlflow
import optuna
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

CATEGORICAL_FEATURES = ["subject_code", "semester"]
NUMERIC_FEATURES = ["number", "enrollment", "avg_rating", "avg_difficulty", "would_take_again_percent", "num_ratings"]
TARGET = "grade_label"


def build_design_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder]:
    X = pd.get_dummies(df[CATEGORICAL_FEATURES], dummy_na=True)
    X[NUMERIC_FEATURES] = df[NUMERIC_FEATURES]
    return X, X.columns.tolist()


def majority_class_baseline(y_train: pd.Series, y_test: pd.Series) -> float:
    majority = y_train.mode().iloc[0]
    predictions = pd.Series(majority, index=y_test.index)
    return accuracy_score(y_test, predictions)


def objective(trial: optuna.Trial, X_train, y_train, X_valid, y_valid, num_classes: int) -> float:
    params = {
        "objective": "multi:softmax",
        "num_class": num_classes,
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 600),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
    }
    model = XGBClassifier(**params, eval_metric="mlogloss")
    model.fit(X_train, y_train)
    return accuracy_score(y_valid, model.predict(X_valid))


def train(feature_df: pd.DataFrame, n_trials: int = 30) -> None:
    from src.pipeline.features import time_based_split

    train_df, test_df = time_based_split(feature_df, test_years=1)
    X_train_raw, feature_cols = build_design_matrix(train_df)
    X_test_raw, _ = build_design_matrix(test_df)
    X_test_raw = X_test_raw.reindex(columns=feature_cols, fill_value=0)

    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(train_df[TARGET])
    y_test = label_encoder.transform(test_df[TARGET])

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("courseiq-grade-classifier")

    baseline_acc = majority_class_baseline(pd.Series(y_train), pd.Series(y_test))
    with mlflow.start_run(run_name="majority-class-baseline"):
        mlflow.log_metric("accuracy", baseline_acc)
    print(f"Baseline (majority class) accuracy: {baseline_acc:.3f}")

    study = optuna.create_study(direction="maximize")
    study.optimize(
        lambda t: objective(t, X_train_raw, y_train, X_test_raw, y_test, len(label_encoder.classes_)),
        n_trials=n_trials,
    )

    with mlflow.start_run(run_name="xgboost-tuned"):
        mlflow.log_params(study.best_params)
        best_model = XGBClassifier(
            **study.best_params,
            objective="multi:softmax",
            num_class=len(label_encoder.classes_),
            eval_metric="mlogloss",
        )
        best_model.fit(X_train_raw, y_train)
        preds = best_model.predict(X_test_raw)

        acc = accuracy_score(y_test, preds)
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("baseline_accuracy", baseline_acc)
        mlflow.log_metric("lift_over_baseline", acc - baseline_acc)
        mlflow.log_dict(
            classification_report(y_test, preds, target_names=label_encoder.classes_, output_dict=True),
            "classification_report.json",
        )
        mlflow.log_dict(
            {"confusion_matrix": confusion_matrix(y_test, preds).tolist(), "labels": label_encoder.classes_.tolist()},
            "confusion_matrix.json",
        )
        mlflow.xgboost.log_model(best_model, artifact_path="model", registered_model_name="courseiq-grade-classifier")

        print(f"Tuned XGBoost accuracy: {acc:.3f} (baseline {baseline_acc:.3f}, lift {acc - baseline_acc:+.3f})")


if __name__ == "__main__":
    feature_table_path = os.environ.get("FEATURE_TABLE_PATH", "data/processed/features.parquet")
    train(pd.read_parquet(feature_table_path))
