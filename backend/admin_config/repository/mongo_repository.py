"""
MongoDB implementation of admin config repository.

Follows the RAG pattern: receives a ready-to-use pymongo Collection
from the composition root (app_container), rather than creating its own client.
"""
import pymongo
from datetime import datetime, timezone
from typing import Optional

from admin_config.models import AdminConfigEntry
from admin_config.repository.repository import AdminConfigRepository


class MongoAdminConfigRepository(AdminConfigRepository):
    """
    MongoDB-backed admin config storage.

    Collection schema:
      { key: str (unique), value: dict, updated_at: datetime }
    """

    def __init__(self, collection):
        """
        Args:
            collection: A pymongo Collection (e.g. db["admin_config"]).
        """
        self._col = collection

        self._col.create_index(
            [("key", pymongo.ASCENDING)],
            unique=True,
        )

    # ────────────────────────────── Reads ─────────────────────────────────

    def get(self, key: str) -> Optional[AdminConfigEntry]:
        """Load a config entry by section key."""
        doc = self._col.find_one({"key": key})
        if not doc:
            return None
        return self._doc_to_entry(doc)

    # ────────────────────────────── Writes ────────────────────────────────

    def set(self, entry: AdminConfigEntry) -> bool:
        """Upsert a config entry."""
        now = datetime.now(timezone.utc)
        result = self._col.update_one(
            {"key": entry.key},
            {"$set": {
                "value": entry.value,
                "updated_at": now,
            }},
            upsert=True,
        )
        return result.acknowledged

    # ────────────────────────────── Helpers ────────────────────────────────

    @staticmethod
    def _doc_to_entry(doc: dict) -> AdminConfigEntry:
        """Convert a MongoDB document to an AdminConfigEntry."""
        return AdminConfigEntry(
            key=doc["key"],
            value=doc.get("value", {}),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
        )
