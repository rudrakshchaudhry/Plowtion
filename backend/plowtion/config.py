"""Runtime configuration, read exclusively from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _default_model_path() -> Path:
    # Repository layout: <repo>/model/crop_model.joblib. In the Docker image the
    # model directory is copied next to the backend code (/app/model).
    for candidate in (REPO_ROOT / "model" / "crop_model.joblib", BACKEND_DIR / "model" / "crop_model.joblib"):
        if candidate.exists():
            return candidate
    return REPO_ROOT / "model" / "crop_model.joblib"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


@dataclass
class Config:
    model_path: Path = field(default_factory=_default_model_path)
    zip_data_path: Path = BACKEND_DIR / "dataset" / "zip-code.csv"

    mongo_uri: str | None = None
    mongo_db_name: str = "farmnest"

    # Optional remote inference. When unset the local model is used.
    sagemaker_endpoint: str | None = None
    aws_region: str | None = None

    # Optional chatbot (any OpenAI-compatible chat completions API, e.g. Perplexity).
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.perplexity.ai"
    llm_model: str = "sonar"

    weather_base_url: str = "https://api.open-meteo.com/v1/forecast"
    http_timeout: float = 5.0

    cors_origins: str = "*"

    # Shared secret for the user-data endpoints (/push-user, /get-users, ...).
    # When unset those endpoints are disabled.
    admin_token: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        model_path = _env("MODEL_PATH")
        return cls(
            model_path=Path(model_path) if model_path else _default_model_path(),
            mongo_uri=_env("MONGO_URI"),
            mongo_db_name=_env("MONGO_DB_NAME", "farmnest"),
            sagemaker_endpoint=_env("SAGEMAKER_ENDPOINT"),
            aws_region=_env("AWS_DEFAULT_REGION") or _env("AWS_REGION"),
            # LLM_API_KEY is preferred; PERPLEXITY_API_KEY is accepted for backwards compatibility.
            llm_api_key=_env("LLM_API_KEY") or _env("PERPLEXITY_API_KEY"),
            llm_base_url=_env("LLM_BASE_URL", "https://api.perplexity.ai"),
            llm_model=_env("LLM_MODEL", "sonar"),
            weather_base_url=_env("WEATHER_BASE_URL", "https://api.open-meteo.com/v1/forecast"),
            http_timeout=float(_env("HTTP_TIMEOUT_SECONDS", "5")),
            cors_origins=_env("CORS_ORIGINS", "*"),
            admin_token=_env("ADMIN_TOKEN"),
        )
