"""Plowtion Flask API.

Run locally:  python backend/app.py   (or: gunicorn -b 0.0.0.0:5001 "app:create_app()")
Configuration comes from environment variables; see ../.env.example.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo.errors import PyMongoError

from plowtion.chat import ChatClient, ChatError, ChatNotConfigured
from plowtion.config import Config
from plowtion.model import CropModel, SageMakerPredictor
from plowtion.schedule import SUPPORTED_CROPS, UnknownCrop, generate_schedule, normalize_crop, schedule_to_text
from plowtion.storage import Storage, StorageUnavailable
from plowtion.validation import FEATURE_BOUNDS, ValidationError, parse_number, validate_fields
from plowtion.weather import WeatherClient, WeatherUnavailable

log = logging.getLogger("plowtion")

SOIL_FIELDS = {k: FEATURE_BOUNDS[k] for k in ("N", "P", "K", "ph")}


def error(message: str, status: int, **extra: Any):
    return jsonify({"status": "error", "error": message, **extra}), status


def _load_zip_table(path) -> dict[int, dict[str, float]] | None:
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.ParserError) as exc:
        log.warning("could not load ZIP code data from %s: %s", path, exc)
        return None
    return {
        int(row["ZipCode"]): {
            "nitrogen": float(row["Nitrogen (N)"]),
            "phosphorus": float(row["Phosphorus (P)"]),
            "potassium": float(row["Potassium (K)"]),
            "ph": float(row["pH Level"]),
        }
        for row in df.to_dict("records")
    }


def _load_model(cfg: Config) -> CropModel | None:
    try:
        model = CropModel.load(cfg.model_path)
        log.info("loaded model v%s from %s", model.version, cfg.model_path)
        return model
    except Exception as exc:  # noqa: BLE001 - any failure means "no local model"
        log.error("could not load model from %s: %s", cfg.model_path, exc)
        return None


def _serialize(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["_id"] = str(out["_id"])
    if isinstance(out.get("timestamp"), datetime):
        out["timestamp"] = out["timestamp"].isoformat()
    return out


def create_app(
    config: Config | None = None,
    *,
    storage: Storage | None = None,
    model: CropModel | None = None,
    weather_client: WeatherClient | None = None,
    chat_client: ChatClient | None = None,
) -> Flask:
    if config is None:
        load_dotenv()
        config = Config.from_env()
    cfg = config
    app = Flask(__name__)
    CORS(app, origins=cfg.cors_origins.split(",") if cfg.cors_origins != "*" else "*")

    model = model or _load_model(cfg)
    storage = storage or Storage.from_uri(cfg.mongo_uri, cfg.mongo_db_name)
    weather_client = weather_client or WeatherClient(cfg.weather_base_url, timeout=cfg.http_timeout)
    chat_client = chat_client or ChatClient(cfg.llm_api_key, cfg.llm_base_url, cfg.llm_model)
    zip_table = _load_zip_table(cfg.zip_data_path)

    sagemaker = None
    if cfg.sagemaker_endpoint and model is not None:
        try:
            sagemaker = SageMakerPredictor(cfg.sagemaker_endpoint, cfg.aws_region, model.features)
        except Exception as exc:  # noqa: BLE001 - boto3 missing or misconfigured
            log.warning("SAGEMAKER_ENDPOINT set but SageMaker client unavailable (%s); using local model", exc)

    def json_body() -> Any:
        return request.get_json(silent=True)

    # ------------------------------------------------------------------ health
    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "model": {"loaded": model is not None, "version": model.version if model else None},
                "inference": "sagemaker" if sagemaker else "local",
                "database": "connected" if storage.ping() else ("unavailable" if storage.configured else "not_configured"),
                "chat": "configured" if chat_client.configured else "not_configured",
                "zip_data": zip_table is not None,
            }
        )

    # ------------------------------------------------------- crop recommender
    @app.post("/predict")
    def predict():
        if model is None:
            return error("model not loaded; run `python backend/train.py`", 503)
        try:
            values = validate_fields(json_body(), FEATURE_BOUNDS)
        except ValidationError as exc:
            return error("invalid input", 400, details=exc.errors)

        source = "local"
        result = None
        if sagemaker is not None:
            try:
                result = sagemaker.predict(values)
                source = "sagemaker"
            except Exception as exc:  # noqa: BLE001
                log.warning("SageMaker prediction failed (%s); falling back to local model", exc)
        if result is None:
            result = model.predict(values)
        return jsonify({"status": "success", "data": {**result, "input": values, "source": source, "model_version": model.version}})

    @app.get("/crops")
    def crops():
        return jsonify({"status": "success", "crops": SUPPORTED_CROPS})

    # ---------------------------------------------------------------- schedule
    @app.post("/schedule")
    def schedule():
        body = json_body()
        if not isinstance(body, dict):
            return error("request body must be a JSON object", 400)
        try:
            crop = normalize_crop(body.get("crop"))
        except UnknownCrop as exc:
            return error(str(exc), 400)
        start_raw = body.get("start_date")
        try:
            start = date.fromisoformat(start_raw) if start_raw else date.today()
        except (TypeError, ValueError):
            return error("start_date must be an ISO date (YYYY-MM-DD)", 400)
        profile = model.crop_profiles.get(crop) if model else None
        return jsonify({"status": "success", "data": generate_schedule(crop, start, profile)})

    # ----------------------------------------------------------------- weather
    @app.get("/weather")
    def weather():
        try:
            lat = parse_number(request.args.get("lat"), "lat", (-90, 90))
            lon = parse_number(request.args.get("lon"), "lon", (-180, 180))
            days = int(parse_number(request.args.get("days", "7"), "days", (1, 16)))
        except ValidationError as exc:
            return error("invalid input", 400, details=exc.errors)
        try:
            data = weather_client.forecast(lat, lon, days)
        except WeatherUnavailable as exc:
            return error(str(exc), 503)
        return jsonify({"status": "success", "data": data})

    # -------------------------------------------------------------------- chat
    @app.post("/chat")
    def chat():
        if not chat_client.configured:
            return error("chatbot is not configured: set LLM_API_KEY to enable it", 503, code="chat_not_configured")
        body = json_body()
        message = body.get("message") if isinstance(body, dict) else None
        if not isinstance(message, str) or not message.strip():
            return error("message is required", 400)
        if len(message) > 2000:
            return error("message must be at most 2000 characters", 400)
        try:
            return jsonify({"status": "success", "data": {"reply": chat_client.ask(message.strip())}})
        except ChatNotConfigured as exc:
            return error(str(exc), 503, code="chat_not_configured")
        except ChatError as exc:
            return error(str(exc), 502)

    # -------------------------------------------------------- soil by ZIP code
    @app.get("/get-soil-by-zip/<zipcode>")
    def get_soil_by_zip(zipcode: str):
        if zip_table is None:
            return error("ZIP code data not loaded", 503)
        if not zipcode.isdigit() or len(zipcode) > 5:
            return error("invalid ZIP code format", 400)
        soil = zip_table.get(int(zipcode))
        if soil is None:
            return jsonify({"status": "not_found", "error": f"no data for ZIP code {zipcode}"}), 404
        return jsonify({"status": "success", "data": {"zipcode": int(zipcode), **soil}})

    # ------------------------------------------- growing conditions (frontend)
    @app.post("/predict-conditions")
    def predict_conditions():
        """Typical growing conditions + schedule for a crop, given soil readings.

        Conditions come from the per-crop statistics of the training dataset.
        """
        if model is None:
            return error("model not loaded; run `python backend/train.py`", 503)
        body = json_body()
        if not isinstance(body, dict):
            return error("request body must be a JSON object", 400)
        try:
            crop = normalize_crop(body.get("crop_name"))
        except UnknownCrop as exc:
            return error(str(exc), 400)
        try:
            soil = validate_fields(body, SOIL_FIELDS)
        except ValidationError as exc:
            return error("invalid input", 400, details=exc.errors)

        profile = model.crop_profiles.get(crop)
        if profile is None:
            return error(f"no profile for crop '{crop}'", 400)
        conditions = {k: profile[k]["mean"] for k in ("temperature", "humidity", "rainfall")}
        soil_fit = {}
        for key in SOIL_FIELDS:
            lo, hi = profile[key]["min"], profile[key]["max"]
            soil_fit[key] = {"value": soil[key], "range": [lo, hi], "status": "low" if soil[key] < lo else "high" if soil[key] > hi else "ok"}
        plan = generate_schedule(crop, date.today(), profile)

        soil_conditions = {"nitrogen": soil["N"], "phosphorus": soil["P"], "potassium": soil["K"], "ph": soil["ph"]}
        result = {
            "username": body.get("username"),
            "userID": body.get("userID"),
            "gmail": body.get("gmail"),
            "zipcode": body.get("zipcode"),
            "crop_name": crop,
            "soil_conditions": soil_conditions,
            "predicted_conditions": conditions,
            "soil_fit": soil_fit,
            "schedule": schedule_to_text(plan),
            "schedule_details": plan,
        }

        saved = False
        if storage.configured:
            try:
                storage.collection("user_conditions").insert_one({**result, "timestamp": datetime.now(timezone.utc)})
                saved = True
            except PyMongoError as exc:
                log.warning("could not save prediction: %s", exc)
        result["saved"] = saved
        return jsonify({"status": "success", "message": "Typical growing conditions for the selected crop", "data": result})

    # ------------------------------------------------------- storage endpoints
    @app.errorhandler(StorageUnavailable)
    def storage_unavailable(exc):
        return error(str(exc), 503)

    @app.errorhandler(PyMongoError)
    def mongo_error(exc):
        log.warning("database error: %s", exc)
        return error("database unavailable", 503)

    @app.post("/push-user")
    def push_user():
        body = json_body()
        if not isinstance(body, dict) or not body:
            return error("request body must be a non-empty JSON object", 400)
        body.pop("_id", None)
        inserted = storage.collection("users").insert_one(body)
        return jsonify({"status": "success", "message": "User added", "user_id": str(inserted.inserted_id)})

    @app.get("/get-users")
    def get_users():
        users = [_serialize(u) for u in storage.collection("users").find().limit(500)]
        return jsonify({"status": "success", "users": users, "count": len(users)})

    @app.delete("/delete-user/<user_id>")
    def delete_user(user_id: str):
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            return error("invalid user id", 400)
        if storage.collection("users").delete_one({"_id": oid}).deleted_count == 1:
            return jsonify({"status": "success", "message": f"User {user_id} deleted"})
        return jsonify({"status": "not_found", "error": f"User {user_id} not found"}), 404

    @app.get("/get-user-conditions")
    def get_user_conditions():
        records = storage.collection("user_conditions").find().sort("timestamp", -1).limit(500)
        records = [_serialize(r) for r in records]
        return jsonify({"status": "success", "user_conditions": records, "count": len(records)})

    @app.get("/get-user-condition/<condition_id>")
    def get_user_condition(condition_id: str):
        try:
            oid = ObjectId(condition_id)
        except InvalidId:
            return error("invalid record id", 400)
        record = storage.collection("user_conditions").find_one({"_id": oid})
        if record is None:
            return jsonify({"status": "not_found", "error": f"Record {condition_id} not found"}), 404
        return jsonify({"status": "success", "user_condition": _serialize(record)})

    return app


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=os.getenv("FLASK_DEBUG") == "1")
