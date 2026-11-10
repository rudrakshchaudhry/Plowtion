import json

import train


def test_dataset_columns():
    df = train.load_dataset()
    assert list(df.columns) == train.FEATURES + [train.TARGET]
    assert df[train.TARGET].nunique() == 22


def test_committed_metrics_match_artifact_version():
    metrics = json.loads((train.DEFAULT_OUT_DIR / "metrics.json").read_text())
    assert metrics["model_version"] == train.MODEL_VERSION
    assert metrics["cv"]["accuracy_mean"] >= 0.95
    assert metrics["cv"]["f1_macro_mean"] >= 0.95
