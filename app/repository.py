"""Small SQLite repository; replaceable by PostgreSQL in production."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.synthetic import generate_records


class Repository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._create_schema()
        self._seed_if_empty()

    def _create_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS hospitals (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
                latitude REAL NOT NULL, longitude REAL NOT NULL, accessibility TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, professional_title TEXT NOT NULL,
                specialty TEXT NOT NULL, expertise TEXT NOT NULL, languages TEXT NOT NULL,
                years_experience INTEGER NOT NULL, accepting_new_patients INTEGER NOT NULL,
                hospital_id TEXT NOT NULL REFERENCES hospitals(id), synthetic INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS slots (
                id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL REFERENCES doctors(id),
                start TEXT NOT NULL, end TEXT NOT NULL, status TEXT NOT NULL, mode TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                csrf_hash TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
        """)
        self.connection.commit()

    def _seed_if_empty(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
        if count:
            return
        records = generate_records()
        self.connection.executemany(
            "INSERT INTO hospitals VALUES (?, ?, ?, ?, ?, ?)",
            [(h["id"], h["name"], h["address"], h["latitude"], h["longitude"],
              json.dumps(h["accessibility"])) for h in records["hospitals"]],
        )
        self.connection.executemany(
            "INSERT INTO doctors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(d["id"], d["name"], d["professional_title"], d["specialty"],
              json.dumps(d["expertise"]), json.dumps(d["languages"]), d["years_experience"],
              int(d["accepting_new_patients"]), d["hospital_id"], int(d["synthetic"]))
             for d in records["doctors"]],
        )
        self.connection.executemany(
            "INSERT INTO slots VALUES (?, ?, ?, ?, ?, ?)",
            [(s["id"], s["doctor_id"], s["start"], s["end"], s["status"], s["mode"])
             for s in records["slots"]],
        )
        self.connection.commit()

    def providers(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("""
            SELECT d.*, h.name AS hospital_name, h.address, h.latitude, h.longitude,
                   h.accessibility
            FROM doctors d JOIN hospitals h ON h.id = d.hospital_id
        """).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for field in ("expertise", "languages", "accessibility"):
                item[field] = json.loads(item[field])
            item["accepting_new_patients"] = bool(item["accepting_new_patients"])
            output.append(item)
        return output

    def free_slots(self, doctor_id: str, modes: set[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in modes)
        query = (
            "SELECT * FROM slots WHERE doctor_id = ? AND status = 'free' "
            f"AND mode IN ({placeholders}) ORDER BY start"
        )
        return [dict(row) for row in self.connection.execute(query, [doctor_id, *sorted(modes)])]

    def close(self) -> None:
        self.connection.close()

    def create_user(
        self, user_id: str, email: str, display_name: str, password_hash: str, created_at: str
    ) -> dict[str, Any]:
        with self.lock:
            self.connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                (user_id, email, display_name, password_hash, created_at),
            )
            self.connection.commit()
        return self.get_user_by_email(email) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def create_session(
        self, token_hash: str, user_id: str, csrf_hash: str, created_at: str, expires_at: str
    ) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (token_hash, user_id, csrf_hash, created_at, expires_at),
            )
            self.connection.commit()

    def get_session(self, token_hash: str, now: str) -> dict[str, Any] | None:
        row = self.connection.execute("""
            SELECT s.*, u.email, u.display_name, u.created_at AS user_created_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
        """, (token_hash, now)).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self.lock:
            self.connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            self.connection.commit()

    def cleanup_expired_sessions(self, now: str) -> None:
        with self.lock:
            self.connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            self.connection.commit()
