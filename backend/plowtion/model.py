"""Crop recommender: local scikit-learn model, with optional SageMaker inference."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

log = logging.getLogger(__name__)


class ModelNotAvailable(RuntimeError):
    pass


class CropModel:
    """Wraps the artifact written by ``backend/train.py``."""

    def __init__(self, artifact: dict[str, Any]):
        self.pipeline = artifact["pipeline"]
        self.features: list[str] = list(artifact["features"])
        self.classes: list[str] = list(artifact["classes"])
        self.version: str = artifact.get("model_version", "unknown")
        self.crop_profiles: dict[str, dict[str, dict[str, float]]] = artifact.get("crop_profiles", {})

    @classmethod
    def load(cls, path: Path) -> "CropModel":
        artifact = joblib.load(path)
        if not isinstance(artifact, dict) or "pipeline" not in artifact:
            raise ModelNotAvailable(
                f"{path} is not a Plowtion model artifact; run `python backend/train.py` to create one"
            )
        return cls(artifact)

    def predict(self, values: dict[str, float], top_k: int = 3) -> dict[str, Any]:
        frame = pd.DataFrame([[values[f] for f in self.features]], columns=self.features)
        proba = self.pipeline.predict_proba(frame)[0]
        classes = list(self.pipeline.classes_)
        ranked = sorted(zip(classes, proba), key=lambda item: item[1], reverse=True)[:top_k]
        return {
            "crop": str(ranked[0][0]),
            "confidence": round(float(ranked[0][1]), 4),
            "top": [{"crop": str(c), "probability": round(float(p), 4)} for c, p in ranked],
        }


class SageMakerPredictor:
    """Optional remote predictor, used only when SAGEMAKER_ENDPOINT is configured.

    boto3 is not a required dependency; install it separately to use this path.
    """

    def __init__(self, endpoint: str, region: str | None, features: list[str]):
        import boto3  # imported lazily so the default install does not need it

        self.endpoint = endpoint
        self.features = features
        self.client = boto3.client("sagemaker-runtime", region_name=region)

    def predict(self, values: dict[str, float]) -> dict[str, Any]:
        payload = {"features": self.features, "instances": [[values[f] for f in self.features]]}
        response = self.client.invoke_endpoint(
            EndpointName=self.endpoint,
            ContentType="application/json",
            Accept="application/json",
            Body=json.dumps(payload),
        )
        result = json.loads(response["Body"].read())
        predictions = result.get("predictions") if isinstance(result, dict) else result
        if not predictions:
            raise RuntimeError("SageMaker response did not contain predictions")
        return {"crop": str(predictions[0]), "confidence": None, "top": []}
