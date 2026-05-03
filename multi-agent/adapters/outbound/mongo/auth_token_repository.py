"""
MongoCredentialStore — implements :class:`CredentialStore` using MongoDB.

Indexes:
    - Unique lookup: ``(user_id, server_identifier)``
    - TTL cleanup:   ``_expires_at``  — staged credentials auto-delete
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from pymongo import MongoClient, ASCENDING

from mas.core.auth.credentials.models import StoredCredential, TokenStatus
from mas.core.auth.credentials.ports import CredentialStore

logger = logging.getLogger(__name__)

_TTL_FIELD = "_expires_at"


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
        self._coll.create_index(
            _TTL_FIELD,
            expireAfterSeconds=0,
            name="ttl_staged_credentials",
        )

    # ------------------------------------------------------------------

    def upsert(self, credential: StoredCredential) -> None:
        doc = credential.model_dump()
        doc["server_identifier"] = credential.server_identifier.rstrip("/")
        doc["updated_at"] = datetime.now(timezone.utc)
        update: dict = {"$set": doc}
        if not credential.staged:
            update["$unset"] = {_TTL_FIELD: ""}
        self._coll.update_one(
            {"user_id": credential.user_id, "server_identifier": doc["server_identifier"]},
            update,
            upsert=True,
        )

    def find_by_server(
        self, user_id: str, server_identifier: str, scheme_type: str = "",
    ) -> Optional[StoredCredential]:
        normalized = server_identifier.rstrip("/")
        query = {
            "user_id": user_id,
            "server_identifier": normalized,
            "status": TokenStatus.ACTIVE.value,
        }
        if scheme_type:
            query["scheme_type"] = scheme_type
        doc = self._coll.find_one(query)
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

    def stage(self, credential: StoredCredential, ttl_seconds: int = 300) -> None:
        credential.staged = True
        doc = credential.model_dump()
        doc["server_identifier"] = credential.server_identifier.rstrip("/")
        doc["updated_at"] = datetime.now(timezone.utc)
        doc[_TTL_FIELD] = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._coll.update_one(
            {"user_id": credential.user_id, "server_identifier": doc["server_identifier"]},
            {"$set": doc},
            upsert=True,
        )

    def promote(self, user_id: str, server_identifier: str) -> bool:
        normalized = server_identifier.rstrip("/")
        result = self._coll.update_one(
            {"user_id": user_id, "server_identifier": normalized, "staged": True},
            {
                "$set": {"staged": False, "updated_at": datetime.now(timezone.utc)},
                "$unset": {_TTL_FIELD: ""},
            },
        )
        return result.modified_count > 0

    # ------------------------------------------------------------------

    @staticmethod
    def _to_model(doc: dict) -> StoredCredential:
        doc.pop("_id", None)
        doc.pop(_TTL_FIELD, None)
        doc.pop("server_url_normalised", None)
        doc.pop("mcp_server_url", None)
        doc.pop("server_url", None)
        doc.pop("auth_rid", None)
        return StoredCredential.model_validate(doc)
