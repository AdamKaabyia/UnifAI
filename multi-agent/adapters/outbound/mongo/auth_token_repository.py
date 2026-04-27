"""
MongoCredentialStore — implements :class:`CredentialStore` using MongoDB.

Index:
    - For server lookup: ``(user_id, server_identifier)``
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient, ASCENDING

from mas.core.auth.credentials.models import StoredCredential, TokenStatus
from mas.core.auth.credentials.ports import CredentialStore

logger = logging.getLogger(__name__)


class MongoCredentialStore(CredentialStore):

    def __init__(
        self,
        mongodb_ip: str = "127.0.0.1",
        mongodb_port: int = 27017,
        db_name: str = "unifai",
        coll_name: str = "credentials",
    ):
        client = MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
        db = client[db_name]
        self._coll = db[coll_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._coll.create_index(
            [("user_id", ASCENDING), ("server_identifier", ASCENDING)],
            unique=True,
            name="uq_user_server",
        )

    # ------------------------------------------------------------------

    def upsert(self, credential: StoredCredential) -> None:
        doc = credential.model_dump()
        doc["server_identifier"] = credential.server_identifier.rstrip("/")
        doc["updated_at"] = datetime.now(timezone.utc)
        self._coll.update_one(
            {"user_id": credential.user_id, "server_identifier": doc["server_identifier"]},
            {"$set": doc},
            upsert=True,
        )

    def find_by_server(self, user_id: str, server_identifier: str) -> Optional[StoredCredential]:
        normalized = server_identifier.rstrip("/")
        doc = self._coll.find_one({
            "user_id": user_id,
            "server_identifier": normalized,
            "status": TokenStatus.ACTIVE.value,
        })
        return self._to_model(doc) if doc else None

    def delete(self, user_id: str, server_identifier: str) -> None:
        normalized = server_identifier.rstrip("/")
        self._coll.delete_one({"user_id": user_id, "server_identifier": normalized})

    def update_status(self, user_id: str, server_identifier: str, status: str) -> None:
        normalized = server_identifier.rstrip("/")
        self._coll.update_one(
            {"user_id": user_id, "server_identifier": normalized},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _to_model(doc: dict) -> StoredCredential:
        doc.pop("_id", None)
        doc.pop("server_url_normalised", None)
        doc.pop("mcp_server_url", None)
        doc.pop("server_url", None)
        doc.pop("auth_rid", None)
        return StoredCredential.model_validate(doc)
