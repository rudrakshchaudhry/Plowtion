"""MongoDB access. The database is optional: when MONGO_URI is unset or the server
is unreachable, endpoints that need storage return 503 and everything else works."""

from __future__ import annotations

import logging
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

log = logging.getLogger(__name__)


class StorageUnavailable(RuntimeError):
    pass


class Storage:
    def __init__(self, database: Any | None):
        self._db = database

    @classmethod
    def from_uri(cls, uri: str | None, db_name: str) -> "Storage":
        if not uri:
            log.info("MONGO_URI not set; storage endpoints are disabled")
            return cls(None)
        # MongoClient connects lazily; short timeouts keep requests responsive when
        # the server is down.
        client = MongoClient(uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000, tz_aware=True)
        return cls(client[db_name])

    @property
    def configured(self) -> bool:
        return self._db is not None

    def ping(self) -> bool:
        if self._db is None:
            return False
        try:
            self._db.command("ping")
            return True
        except PyMongoError:
            return False
        except NotImplementedError:  # mongomock does not implement every command
            return True

    def collection(self, name: str):
        if self._db is None:
            raise StorageUnavailable("database is not configured (set MONGO_URI)")
        return self._db[name]
