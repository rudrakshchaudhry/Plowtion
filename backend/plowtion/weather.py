"""Minimal Open-Meteo client (https://open-meteo.com). No API key required."""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_URL = "https://api.open-meteo.com/v1/forecast"

CURRENT_VARS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum"


class WeatherUnavailable(RuntimeError):
    """Raised when the weather service cannot be reached or returns bad data."""


class WeatherClient:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 5.0, session: requests.Session | None = None):
        self.base_url = base_url
        self.timeout = timeout
        self.session = session or requests.Session()

    def forecast(self, latitude: float, longitude: float, days: int = 7) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": CURRENT_VARS,
            "daily": DAILY_VARS,
            "forecast_days": days,
            "timezone": "auto",
        }
        try:
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise WeatherUnavailable("weather service timed out") from exc
        except (requests.RequestException, ValueError) as exc:
            raise WeatherUnavailable(f"weather service error: {exc.__class__.__name__}") from exc
        return self._normalize(data)

    @staticmethod
    def _normalize(data: Any) -> dict[str, Any]:
        try:
            current = data["current"]
            daily = data["daily"]
            days = [
                {
                    "date": d,
                    "temperature_max_c": tmax,
                    "temperature_min_c": tmin,
                    "precipitation_mm": rain,
                }
                for d, tmax, tmin, rain in zip(
                    daily["time"],
                    daily["temperature_2m_max"],
                    daily["temperature_2m_min"],
                    daily["precipitation_sum"],
                    strict=True,
                )
            ]
            return {
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "timezone": data.get("timezone"),
                "current": {
                    "time": current.get("time"),
                    "temperature_c": current["temperature_2m"],
                    "relative_humidity_pct": current["relative_humidity_2m"],
                    "precipitation_mm": current["precipitation"],
                    "wind_speed_kmh": current["wind_speed_10m"],
                },
                "daily": days,
                "source": "open-meteo.com",
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherUnavailable("unexpected response from weather service") from exc
