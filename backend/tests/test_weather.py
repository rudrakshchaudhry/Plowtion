from unittest.mock import MagicMock

import pytest
import requests

from plowtion.weather import WeatherClient, WeatherUnavailable

SAMPLE = {
    "latitude": 41.6,
    "longitude": -93.6,
    "timezone": "America/Chicago",
    "current": {
        "time": "2026-11-10T09:00",
        "temperature_2m": 7.4,
        "relative_humidity_2m": 81,
        "precipitation": 0.0,
        "wind_speed_10m": 12.3,
    },
    "daily": {
        "time": ["2026-11-10", "2026-11-11"],
        "temperature_2m_max": [11.2, 9.8],
        "temperature_2m_min": [2.1, 0.4],
        "precipitation_sum": [0.0, 3.6],
    },
}


def fake_session(response=None, exc=None):
    session = MagicMock(spec=requests.Session)
    if exc is not None:
        session.get.side_effect = exc
    else:
        resp = MagicMock()
        resp.json.return_value = response
        resp.raise_for_status.return_value = None
        session.get.return_value = resp
    return session


def test_forecast_success():
    session = fake_session(SAMPLE)
    client = WeatherClient("https://weather.invalid/v1/forecast", timeout=2.5, session=session)
    data = client.forecast(41.6, -93.6, days=2)

    assert data["current"]["temperature_c"] == 7.4
    assert data["current"]["relative_humidity_pct"] == 81
    assert data["daily"][1] == {
        "date": "2026-11-11",
        "temperature_max_c": 9.8,
        "temperature_min_c": 0.4,
        "precipitation_mm": 3.6,
    }
    _, kwargs = session.get.call_args
    assert kwargs["timeout"] == 2.5
    assert kwargs["params"]["latitude"] == 41.6
    assert kwargs["params"]["forecast_days"] == 2


def test_forecast_timeout():
    client = WeatherClient(session=fake_session(exc=requests.Timeout("slow")))
    with pytest.raises(WeatherUnavailable, match="timed out"):
        client.forecast(0, 0)


def test_forecast_connection_error():
    client = WeatherClient(session=fake_session(exc=requests.ConnectionError("down")))
    with pytest.raises(WeatherUnavailable):
        client.forecast(0, 0)


def test_forecast_malformed_payload():
    client = WeatherClient(session=fake_session({"unexpected": True}))
    with pytest.raises(WeatherUnavailable, match="unexpected"):
        client.forecast(0, 0)


def test_weather_endpoint_success(make_app):
    client = make_app(weather_client=WeatherClient(session=fake_session(SAMPLE))).test_client()
    res = client.get("/weather?lat=41.6&lon=-93.6&days=2")
    assert res.status_code == 200
    assert res.get_json()["data"]["source"] == "open-meteo.com"


def test_weather_endpoint_timeout_returns_503(make_app):
    client = make_app(weather_client=WeatherClient(session=fake_session(exc=requests.Timeout()))).test_client()
    res = client.get("/weather?lat=41.6&lon=-93.6")
    assert res.status_code == 503
    assert "timed out" in res.get_json()["error"]


def test_weather_endpoint_validation(client):
    assert client.get("/weather?lat=100&lon=0").status_code == 400
    assert client.get("/weather?lon=0").status_code == 400
    assert client.get("/weather?lat=0&lon=0&days=30").status_code == 400


def test_weather_real_session_is_blocked_offline():
    # Sanity check for the no-network guard in conftest: a real HTTP call must fail
    # (and is translated into WeatherUnavailable) rather than reaching the internet.
    with pytest.raises(WeatherUnavailable):
        WeatherClient("https://api.open-meteo.com/v1/forecast", timeout=1).forecast(0, 0)
