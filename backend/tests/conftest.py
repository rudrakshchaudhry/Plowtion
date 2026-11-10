import socket

import mongomock
import pytest

from app import create_app
from plowtion.chat import ChatClient
from plowtion.config import Config
from plowtion.storage import Storage
from plowtion.weather import WeatherClient


class NetworkBlocked(OSError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Block DNS lookups and outbound connections so no test can reach the network."""

    def guard(*args, **kwargs):
        raise NetworkBlocked("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket, "getaddrinfo", guard)


@pytest.fixture
def config():
    return Config()  # defaults only: no Mongo URI, no LLM key, no SageMaker


@pytest.fixture
def mongo_db():
    return mongomock.MongoClient()["farmnest_test"]


@pytest.fixture
def make_app(config, mongo_db):
    def factory(**overrides):
        kwargs = {
            "storage": Storage(mongo_db),
            "chat_client": ChatClient(None, "https://llm.invalid", "test-model"),
            "weather_client": WeatherClient("https://weather.invalid/v1/forecast", timeout=1),
        }
        kwargs.update(overrides)
        app = create_app(config, **kwargs)
        app.config.update(TESTING=True)
        return app

    return factory


@pytest.fixture
def client(make_app):
    return make_app().test_client()
