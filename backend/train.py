"""Train the Plowtion crop recommender from dataset/Crop_recommendation.csv.

Usage (from the repository root or from backend/):

    python backend/train.py                      # writes model/crop_model.joblib + model/metrics.json
    python backend/train.py --out-dir /tmp/model # write somewhere else (used by CI)
    python backend/train.py --min-accuracy 0.95  # exit non-zero if CV accuracy is below the threshold

The script is deterministic (fixed random seeds, no timestamps in the outputs), so
re-running it on the same data and library versions reproduces the same metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
DATASET_PATH = BACKEND_DIR / "dataset" / "Crop_recommendation.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "model"

MODEL_VERSION = "2.0.0"
FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
TARGET = "label"
CV_FOLDS = 5
SEED = 42


def build_pipeline() -> Pipeline:
    # Small forest with bounded depth keeps the artifact well under 5 MB while
    # remaining accurate on this dataset.
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=12,
                    min_samples_leaf=2,
                    random_state=SEED,
                    n_jobs=1,
                ),
            ),
        ]
    )


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing columns: {missing}")
    df = df[FEATURES + [TARGET]].dropna()
    df[TARGET] = df[TARGET].str.strip().str.lower()
    return df


def crop_profiles(df: pd.DataFrame) -> dict[str, dict[str, dict[str, float]]]:
    """Per-crop summary statistics (mean/min/max) for every feature.

    Used by /predict-conditions to report the typical growing conditions for a crop.
    """
    profiles: dict[str, dict[str, dict[str, float]]] = {}
    for crop, group in df.groupby(TARGET):
        profiles[crop] = {
            feat: {
                "mean": round(float(group[feat].mean()), 3),
                "min": round(float(group[feat].min()), 3),
                "max": round(float(group[feat].max()), 3),
            }
            for feat in FEATURES
        }
    return profiles


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(out_dir: Path) -> dict:
    df = load_dataset()
    X, y = df[FEATURES], df[TARGET]

    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=SEED)
    scores = cross_validate(
        build_pipeline(), X, y, cv=cv, scoring={"accuracy": "accuracy", "f1_macro": "f1_macro"}
    )
    acc = scores["test_accuracy"]
    f1 = scores["test_f1_macro"]

    pipeline = build_pipeline().fit(X, y)

    artifact = {
        "model_version": MODEL_VERSION,
        "sklearn_version": sklearn.__version__,
        "features": FEATURES,
        "classes": [str(c) for c in pipeline.classes_],
        "pipeline": pipeline,
        "crop_profiles": crop_profiles(df),
    }

    metrics = {
        "model_version": MODEL_VERSION,
        "model_type": "Pipeline(StandardScaler, RandomForestClassifier)",
        "sklearn_version": sklearn.__version__,
        "dataset": "backend/dataset/Crop_recommendation.csv",
        "dataset_sha256": sha256_of(DATASET_PATH),
        "n_samples": int(len(df)),
        "n_classes": int(y.nunique()),
        "features": FEATURES,
        "cv": {
            "strategy": f"StratifiedKFold(n_splits={CV_FOLDS}, shuffle=True, random_state={SEED})",
            "accuracy_mean": round(float(np.mean(acc)), 4),
            "accuracy_std": round(float(np.std(acc)), 4),
            "f1_macro_mean": round(float(np.mean(f1)), 4),
            "f1_macro_std": round(float(np.std(f1)), 4),
            "accuracy_per_fold": [round(float(v), 4) for v in acc],
            "f1_macro_per_fold": [round(float(v), 4) for v in f1],
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "crop_model.joblib"
    joblib.dump(artifact, model_path, compress=3)
    metrics["artifact"] = model_path.name
    metrics["artifact_size_bytes"] = model_path.stat().st_size
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="output directory (default: model/)")
    parser.add_argument(
        "--min-accuracy", type=float, default=None, help="fail if mean CV accuracy is below this value"
    )
    args = parser.parse_args(argv)

    metrics = train(args.out_dir)
    cv = metrics["cv"]
    print(
        f"{CV_FOLDS}-fold stratified CV on {metrics['n_samples']} rows, {metrics['n_classes']} classes\n"
        f"  accuracy : {cv['accuracy_mean']:.4f} +/- {cv['accuracy_std']:.4f}\n"
        f"  macro-F1 : {cv['f1_macro_mean']:.4f} +/- {cv['f1_macro_std']:.4f}\n"
        f"  artifact : {args.out_dir / metrics['artifact']} ({metrics['artifact_size_bytes'] / 1e6:.2f} MB)"
    )
    if args.min_accuracy is not None and cv["accuracy_mean"] < args.min_accuracy:
        print(f"FAIL: accuracy {cv['accuracy_mean']:.4f} < required {args.min_accuracy}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
