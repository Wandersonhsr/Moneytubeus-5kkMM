from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.utils import utils


class EditorialStore:
    def __init__(self, db_path: str | None = None):
        base = utils.storage_dir("editorial", create=True)
        self.db_path = db_path or os.path.join(base, "editorial.db")
        self._init()

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._db() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def save(self, episode: dict) -> dict:
        with self._db() as db:
            db.execute(
                """INSERT INTO episodes
                   (id, channel, payload, state, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   channel=excluded.channel, payload=excluded.payload,
                   state=excluded.state, updated_at=excluded.updated_at""",
                (
                    episode["id"], episode["channel"],
                    json.dumps(episode, ensure_ascii=False),
                    episode["state"], episode["created_at"], episode["updated_at"],
                ),
            )
        return episode

    def get(self, episode_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute(
                "SELECT payload FROM episodes WHERE id=?", (episode_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def list(self, channel: str | None = None, state: str | None = None) -> list[dict]:
        query = "SELECT payload FROM episodes WHERE 1=1"
        args: list[str] = []
        if channel:
            query += " AND channel=?"
            args.append(channel)
        if state:
            query += " AND state=?"
            args.append(state)
        query += " ORDER BY created_at DESC"
        with self._db() as db:
            rows = db.execute(query, args).fetchall()
        return [json.loads(row["payload"]) for row in rows]


store = EditorialStore()
