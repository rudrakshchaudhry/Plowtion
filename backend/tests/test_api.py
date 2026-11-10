from datetime import date

import pytest

from plowtion.chat import ChatClient
from plowtion.storage import Storage

# First row of dataset/Crop_recommendation.csv (label: rice)
RICE_ROW = {"N": 90, "P": 42, "K": 43, "temperature": 20.88, "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["model"]["loaded"] is True
    assert body["model"]["version"]
    assert body["inference"] == "local"
    assert body["chat"] == "not_configured"
    assert body["database"] == "connected"


def test_health_without_database(make_app):
    body = make_app(storage=Storage(None)).test_client().get("/health").get_json()
    assert body["database"] == "not_configured"


def test_predict_happy_path(client):
    res = client.post("/predict", json=RICE_ROW)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["crop"] == "rice"
    assert 0 < data["confidence"] <= 1
    assert data["top"][0]["crop"] == "rice"
    assert data["source"] == "local"


def test_predict_accepts_lowercase_keys(client):
    payload = {k.lower(): v for k, v in RICE_ROW.items()}
    assert client.post("/predict", json=payload).status_code == 200


def test_predict_missing_field(client):
    payload = dict(RICE_ROW)
    del payload["rainfall"]
    res = client.post("/predict", json=payload)
    assert res.status_code == 400
    assert res.get_json()["details"] == {"rainfall": "is required"}


@pytest.mark.parametrize(
    "field,value",
    [("ph", 15), ("humidity", -1), ("N", 9999), ("temperature", "hot"), ("K", None), ("P", True), ("rainfall", "nan")],
)
def test_predict_rejects_bad_values(client, field, value):
    res = client.post("/predict", json={**RICE_ROW, field: value})
    assert res.status_code == 400
    assert field in res.get_json()["details"]


def test_predict_rejects_non_object_body(client):
    assert client.post("/predict", data="not json", content_type="text/plain").status_code == 400
    assert client.post("/predict", json=[1, 2, 3]).status_code == 400


def test_schedule_for_sample_crop(client):
    res = client.post("/schedule", json={"crop": "Maize", "start_date": "2026-04-01"})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["crop"] == "maize"
    assert data["anchor_date"] == "2026-04-01"
    # maize: 70-100 days to harvest
    assert data["harvest_start"] == "2026-06-10"
    assert data["harvest_end"] == "2026-07-10"
    names = [s["stage"] for s in data["stages"]]
    assert names[0] == "Preparation" and names[-1] == "Harvest window"
    starts = [date.fromisoformat(s["start"]) for s in data["stages"]]
    assert starts == sorted(starts)
    for stage in data["stages"]:
        assert stage["start"] <= stage["end"]


def test_schedule_validation(client):
    assert client.post("/schedule", json={"crop": "dragonfruit"}).status_code == 400
    assert client.post("/schedule", json={"crop": "rice", "start_date": "tomorrow"}).status_code == 400
    assert client.post("/schedule", json={}).status_code == 400


def test_chat_not_configured(client):
    res = client.post("/chat", json={"message": "When should I plant maize?"})
    assert res.status_code == 503
    body = res.get_json()
    assert body["code"] == "chat_not_configured"


def test_chat_configured_uses_provider(make_app, monkeypatch):
    chat = ChatClient("test-key", "https://llm.invalid", "test-model")
    monkeypatch.setattr(chat, "ask", lambda message: f"echo: {message}")
    res = make_app(chat_client=chat).test_client().post("/chat", json={"message": "hi"})
    assert res.status_code == 200
    assert res.get_json()["data"]["reply"] == "echo: hi"


def test_soil_by_zip(client):
    res = client.get("/get-soil-by-zip/10001")
    assert res.status_code == 200
    assert res.get_json()["data"]["zipcode"] == 10001
    assert client.get("/get-soil-by-zip/abc").status_code == 400
    assert client.get("/get-soil-by-zip/00000").status_code == 404


def test_predict_conditions_saves_when_db_available(client, mongo_db):
    payload = {"crop_name": "rice", "zipcode": "10001", "n": 27.4, "p": 13.1, "k": 77.2, "ph": 5.3}
    res = client.post("/predict-conditions", json=payload)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert set(data["predicted_conditions"]) == {"temperature", "humidity", "rainfall"}
    assert "Harvest window" in data["schedule"]
    assert data["saved"] is True
    assert mongo_db["user_conditions"].count_documents({}) == 1
    listed = client.get("/get-user-conditions").get_json()
    assert listed["count"] == 1


def test_predict_conditions_works_without_db(make_app):
    client = make_app(storage=Storage(None)).test_client()
    res = client.post("/predict-conditions", json={"crop_name": "maize", "n": 70, "p": 40, "k": 20, "ph": 6.2})
    assert res.status_code == 200
    assert res.get_json()["data"]["saved"] is False
    # storage-only endpoints report 503 instead of crashing
    assert client.get("/get-users").status_code == 503
    assert client.post("/push-user", json={"email": "a@example.com"}).status_code == 503


def test_predict_conditions_validation(client):
    assert client.post("/predict-conditions", json={"n": 1, "p": 1, "k": 1, "ph": 6}).status_code == 400
    res = client.post("/predict-conditions", json={"crop_name": "rice", "n": 1, "p": 1, "k": 1, "ph": 20})
    assert res.status_code == 400


def test_user_roundtrip(client):
    res = client.post("/push-user", json={"email": "farmer@example.com", "name": "Farmer"})
    assert res.status_code == 200
    user_id = res.get_json()["user_id"]
    assert client.get("/get-users").get_json()["count"] == 1
    assert client.delete(f"/delete-user/{user_id}").status_code == 200
    assert client.delete(f"/delete-user/{user_id}").status_code == 404
    assert client.delete("/delete-user/not-an-id").status_code == 400


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


def test_chat_client_parses_provider_response(monkeypatch):
    import plowtion.chat as chat_mod

    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return _FakeResponse({"choices": [{"message": {"content": "Plant after the last frost."}}]})

    monkeypatch.setattr(chat_mod.requests, "post", fake_post)
    client = ChatClient("test-key", "https://llm.invalid/", "test-model")
    assert client.ask("When to plant maize?") == "Plant after the last frost."
    assert captured["url"] == "https://llm.invalid/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "test-model"


def test_chat_provider_error_returns_502(make_app, monkeypatch):
    import plowtion.chat as chat_mod

    monkeypatch.setattr(chat_mod.requests, "post", lambda *a, **k: _FakeResponse({}, status=401))
    client = make_app(chat_client=ChatClient("bad-key", "https://llm.invalid", "m")).test_client()
    res = client.post("/chat", json={"message": "hi"})
    assert res.status_code == 502
    assert "bad-key" not in res.get_data(as_text=True)
