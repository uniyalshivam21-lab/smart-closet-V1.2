"""
SQLite database utilities and repository layer.

We keep database access behind a small repository API to:
- Encapsulate SQL details.
- Make it easier to swap out the DB or migrate schema.
- Support unit testing without touching hardware or ML.

Relational Schema (conceptual UML)
----------------------------------
TABLE clothing_items
    - id            INTEGER PRIMARY KEY AUTOINCREMENT
    - slot          INTEGER NOT NULL
    - type          TEXT NOT NULL   -- e.g. "shirt", "pants", "jacket"
    - color_hint    TEXT            -- optional, from CV
    - last_worn_ts  TEXT            -- ISO timestamp
    - usage_count   INTEGER DEFAULT 0
    - created_ts    TEXT NOT NULL
    - updated_ts    TEXT NOT NULL

TABLE usage_history
    - id            INTEGER PRIMARY KEY AUTOINCREMENT
    - clothing_id   INTEGER NOT NULL REFERENCES clothing_items(id)
    - worn_ts       TEXT NOT NULL
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_connection(db_path: Path) -> sqlite3.Connection:
    """
    Create a SQLite connection with safe defaults.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """
    Create tables if they do not already exist.
    """
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS clothing_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot INTEGER NOT NULL,
            type TEXT NOT NULL,
            color_hint TEXT,
            last_worn_ts TEXT,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_ts TEXT NOT NULL,
            updated_ts TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clothing_id INTEGER NOT NULL,
            worn_ts TEXT NOT NULL,
            FOREIGN KEY (clothing_id) REFERENCES clothing_items(id)
        );
        """
    )
    conn.commit()


@dataclass
class ClothingItem:
    """
    Simple dataclass representation of a clothing item row.
    """

    id: int
    slot: int
    type: str
    color_hint: Optional[str]
    last_worn_ts: Optional[str]
    usage_count: int
    created_ts: str
    updated_ts: str


class ClothingRepository:
    """
    Repository responsible for CRUD operations on clothing items.

    Sequence (add_or_update during scan):
    -------------------------------------
    1. Look up existing item by slot.
    2. If exists:
         - Update its type (if changed) and updated_ts.
       Else:
         - Insert new row with usage_count = 0.
    3. Return the resulting record as dict for JSON serialization.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_or_update_item(self, slot: int, clothing_type: str) -> Dict[str, Any]:
        cur = self._conn.cursor()

        cur.execute("SELECT * FROM clothing_items WHERE slot = ?", (slot,))
        row = cur.fetchone()
        now = self._now()

        if row:
            cur.execute(
                """
                UPDATE clothing_items
                SET type = ?, updated_ts = ?
                WHERE slot = ?
                """,
                (clothing_type, now, slot),
            )
            self._conn.commit()
            item_id = row["id"]
        else:
            cur.execute(
                """
                INSERT INTO clothing_items (slot, type, created_ts, updated_ts)
                VALUES (?, ?, ?, ?)
                """,
                (slot, clothing_type, now, now),
            )
            self._conn.commit()
            item_id = cur.lastrowid

        return self.get_item(item_id)

    def get_item(self, item_id: int) -> Dict[str, Any]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM clothing_items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Item with id {item_id} not found")
        item = ClothingItem(
            id=row["id"],
            slot=row["slot"],
            type=row["type"],
            color_hint=row["color_hint"],
            last_worn_ts=row["last_worn_ts"],
            usage_count=row["usage_count"],
            created_ts=row["created_ts"],
            updated_ts=row["updated_ts"],
        )
        return asdict(item)

    def list_clothes(self) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM clothing_items ORDER BY slot ASC, created_ts ASC"
        )
        rows = cur.fetchall()
        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "slot": row["slot"],
                    "type": row["type"],
                    "color_hint": row["color_hint"],
                    "last_worn_ts": row["last_worn_ts"],
                    "usage_count": row["usage_count"],
                    "created_ts": row["created_ts"],
                    "updated_ts": row["updated_ts"],
                }
            )
        return items

    def log_usage(self, item_id: int) -> None:
        """
        Record that an item was delivered / worn, and increment usage count.
        """
        now = self._now()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO usage_history (clothing_id, worn_ts) VALUES (?, ?)",
            (item_id, now),
        )
        cur.execute(
            """
            UPDATE clothing_items
            SET last_worn_ts = ?, usage_count = usage_count + 1, updated_ts = ?
            WHERE id = ?
            """,
            (now, now, item_id),
        )
        self._conn.commit()

