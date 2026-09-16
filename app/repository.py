"""SQLite persistence for the synthetic operations MVP.

The repository deliberately stores only fictional demonstration records. Its
method boundaries are designed so SQLite can later be replaced by PostgreSQL.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.synthetic import generate_records


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.lock = threading.RLock()
        self._create_schema()
        self._migrate_legacy_schema()
        self._seed_reference_data()

    def _create_schema(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS hospitals (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
                latitude REAL NOT NULL, longitude REAL NOT NULL,
                accessibility TEXT NOT NULL, email TEXT, phone TEXT,
                emergency_phone TEXT, medical_fields TEXT, synthetic INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, professional_title TEXT NOT NULL,
                specialty TEXT NOT NULL, expertise TEXT NOT NULL, languages TEXT NOT NULL,
                years_experience INTEGER NOT NULL, accepting_new_patients INTEGER NOT NULL,
                hospital_id TEXT NOT NULL REFERENCES hospitals(id), synthetic INTEGER NOT NULL,
                email TEXT, phone TEXT, on_call INTEGER NOT NULL DEFAULT 0, video_room_url TEXT
            );
            CREATE TABLE IF NOT EXISTS slots (
                id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL REFERENCES doctors(id),
                start TEXT NOT NULL, end TEXT NOT NULL, status TEXT NOT NULL, mode TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY, display_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                age INTEGER NOT NULL, suburb TEXT NOT NULL, latitude REAL NOT NULL,
                longitude REAL NOT NULL, conditions TEXT NOT NULL, medications TEXT NOT NULL,
                allergies TEXT NOT NULL, synthetic INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                csrf_hash TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id),
                doctor_id TEXT NOT NULL REFERENCES doctors(id),
                slot_id TEXT NOT NULL UNIQUE REFERENCES slots(id),
                booked_by_user_id TEXT NOT NULL REFERENCES users(id),
                start TEXT NOT NULL, end TEXT NOT NULL, mode TEXT NOT NULL,
                status TEXT NOT NULL, reason TEXT NOT NULL,
                video_room_url TEXT, integration_status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS navigation_runs (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                patient_id TEXT, urgency TEXT NOT NULL, specialties TEXT NOT NULL,
                request_payload TEXT NOT NULL, result_payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_logs (
                id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, user_id TEXT,
                event_type TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
                route TEXT, method TEXT, status_code INTEGER, details TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_slots_doctor_status ON slots(doctor_id, status, start);
            CREATE INDEX IF NOT EXISTS idx_appointments_user ON appointments(booked_by_user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_activity_user_time ON activity_logs(user_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_navigation_user_time ON navigation_runs(user_id, created_at);
        """)
        self.connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _migrate_legacy_schema(self) -> None:
        hospital_columns = {
            "email": "TEXT", "phone": "TEXT", "emergency_phone": "TEXT",
            "medical_fields": "TEXT", "synthetic": "INTEGER NOT NULL DEFAULT 1",
        }
        doctor_columns = {
            "email": "TEXT", "phone": "TEXT", "on_call": "INTEGER NOT NULL DEFAULT 0",
            "video_room_url": "TEXT",
        }
        for name, definition in hospital_columns.items():
            self._ensure_column("hospitals", name, definition)
        for name, definition in doctor_columns.items():
            self._ensure_column("doctors", name, definition)
        self.connection.commit()

    def _seed_reference_data(self) -> None:
        records = generate_records()
        with self.lock:
            self.connection.executemany(
                """INSERT INTO hospitals
                   (id,name,address,latitude,longitude,accessibility,email,phone,
                    emergency_phone,medical_fields,synthetic)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,address=excluded.address,latitude=excluded.latitude,
                     longitude=excluded.longitude,accessibility=excluded.accessibility,
                     email=excluded.email,phone=excluded.phone,
                     emergency_phone=excluded.emergency_phone,
                     medical_fields=excluded.medical_fields,synthetic=excluded.synthetic""",
                [(h["id"], h["name"], h["address"], h["latitude"], h["longitude"],
                  json.dumps(h["accessibility"]), h["email"], h["phone"],
                  h["emergency_phone"], json.dumps(h["medical_fields"]), int(h["synthetic"]))
                 for h in records["hospitals"]],
            )
            self.connection.executemany(
                """INSERT INTO doctors
                   (id,name,professional_title,specialty,expertise,languages,years_experience,
                    accepting_new_patients,hospital_id,synthetic,email,phone,on_call,video_room_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,professional_title=excluded.professional_title,
                     specialty=excluded.specialty,expertise=excluded.expertise,
                     languages=excluded.languages,years_experience=excluded.years_experience,
                     accepting_new_patients=excluded.accepting_new_patients,
                     hospital_id=excluded.hospital_id,synthetic=excluded.synthetic,
                     email=excluded.email,phone=excluded.phone,on_call=excluded.on_call,
                     video_room_url=excluded.video_room_url""",
                [(d["id"], d["name"], d["professional_title"], d["specialty"],
                  json.dumps(d["expertise"]), json.dumps(d["languages"]), d["years_experience"],
                  int(d["accepting_new_patients"]), d["hospital_id"], int(d["synthetic"]),
                  d["email"], d["phone"], int(d["on_call"]), d["video_room_url"])
                 for d in records["doctors"]],
            )
            self.connection.executemany(
                "INSERT OR IGNORE INTO slots VALUES (?, ?, ?, ?, ?, ?)",
                [(s["id"], s["doctor_id"], s["start"], s["end"], s["status"], s["mode"])
                 for s in records["slots"]],
            )
            self.connection.executemany(
                """INSERT OR IGNORE INTO patients
                   (id,display_name,email,age,suburb,latitude,longitude,conditions,medications,
                    allergies,synthetic,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(p["id"], p["display_name"], p["email"], p["age"], p["suburb"],
                  p["latitude"], p["longitude"], json.dumps(p["conditions"]),
                  json.dumps(p["medications"]), json.dumps(p["allergies"]),
                  int(p["synthetic"]), p["created_at"]) for p in records["patients"]],
            )
            self.connection.commit()

    @staticmethod
    def _decode(row: sqlite3.Row, json_fields: tuple[str, ...], bool_fields: tuple[str, ...] = ()) -> dict[str, Any]:
        item = dict(row)
        for field in json_fields:
            item[field] = json.loads(item[field] or "[]")
        for field in bool_fields:
            item[field] = bool(item[field])
        return item

    def providers(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("""
            SELECT d.*, h.name AS hospital_name, h.address, h.latitude, h.longitude,
                   h.accessibility, h.email AS hospital_email, h.phone AS hospital_phone,
                   h.medical_fields
            FROM doctors d JOIN hospitals h ON h.id = d.hospital_id ORDER BY d.name
        """).fetchall()
        return [self._decode(row, ("expertise", "languages", "accessibility", "medical_fields"),
                             ("accepting_new_patients", "synthetic", "on_call")) for row in rows]

    def hospitals(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM hospitals ORDER BY name").fetchall()
        return [self._decode(row, ("accessibility", "medical_fields"), ("synthetic",)) for row in rows]

    def patients(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM patients ORDER BY id").fetchall()
        return [self._decode(row, ("conditions", "medications", "allergies"), ("synthetic",)) for row in rows]

    def patient(self, patient_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return self._decode(row, ("conditions", "medications", "allergies"), ("synthetic",)) if row else None

    def free_slots(self, doctor_id: str, modes: set[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in modes)
        query = "SELECT * FROM slots WHERE doctor_id = ? AND status = 'free' AND start > ? " + f"AND mode IN ({placeholders}) ORDER BY start"
        return [dict(row) for row in self.connection.execute(
            query, [doctor_id, utc_now(), *sorted(modes)]
        )]

    def on_call_doctors(self) -> list[dict[str, Any]]:
        return [provider for provider in self.providers() if provider["on_call"]]

    def create_appointment(self, patient_id: str, slot_id: str, user_id: str, reason: str) -> dict[str, Any]:
        with self.lock:
            patient = self.connection.execute("SELECT id FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if not patient:
                raise ValueError("Synthetic patient was not found")
            slot = self.connection.execute("""
                SELECT s.*, d.video_room_url FROM slots s
                JOIN doctors d ON d.id = s.doctor_id WHERE s.id = ?
            """, (slot_id,)).fetchone()
            if not slot or slot["status"] != "free":
                raise ValueError("That fictional appointment slot is no longer available")
            appointment_id = f"APT-{uuid.uuid4().hex[:12].upper()}"
            now = utc_now()
            video_url = slot["video_room_url"] if slot["mode"] == "telehealth" else None
            self.connection.execute("UPDATE slots SET status = 'booked' WHERE id = ?", (slot_id,))
            self.connection.execute("""
                INSERT INTO appointments
                (id,patient_id,doctor_id,slot_id,booked_by_user_id,start,end,mode,status,
                 reason,video_room_url,integration_status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (appointment_id, patient_id, slot["doctor_id"], slot_id, user_id,
                  slot["start"], slot["end"], slot["mode"], "confirmed", reason,
                  video_url, "synthetic_hospital_confirmed", now, now))
            self.connection.commit()
        return self.appointment(appointment_id) or {}

    def appointment(self, appointment_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("""
            SELECT a.*, p.display_name AS patient_name, d.name AS doctor_name,
                   d.email AS doctor_email, h.name AS hospital_name, h.email AS hospital_email
            FROM appointments a JOIN patients p ON p.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id JOIN hospitals h ON h.id = d.hospital_id
            WHERE a.id = ?
        """, (appointment_id,)).fetchone()
        return dict(row) if row else None

    def appointments(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute("""
            SELECT a.*, p.display_name AS patient_name, d.name AS doctor_name,
                   d.email AS doctor_email, h.name AS hospital_name, h.email AS hospital_email
            FROM appointments a JOIN patients p ON p.id = a.patient_id
            JOIN doctors d ON d.id = a.doctor_id JOIN hospitals h ON h.id = d.hospital_id
            WHERE a.booked_by_user_id = ? ORDER BY a.start
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def record_navigation(self, user_id: str, patient_id: str | None, response: Any, payload: Any) -> None:
        with self.lock:
            self.connection.execute("""
                INSERT INTO navigation_runs
                (id,user_id,patient_id,urgency,specialties,request_payload,result_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (response.request_id, user_id, patient_id, response.triage.urgency,
                  json.dumps(response.recommended_specialties), payload.model_dump_json(),
                  response.model_dump_json(), utc_now()))
            self.connection.commit()

    def log_activity(
        self, event_type: str, user_id: str | None = None, entity_type: str | None = None,
        entity_id: str | None = None, route: str | None = None, method: str | None = None,
        status_code: int | None = None, details: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.connection.execute("INSERT INTO activity_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"LOG-{uuid.uuid4().hex[:16].upper()}", utc_now(), user_id, event_type,
                 entity_type, entity_id, route, method, status_code,
                 json.dumps(details or {}, separators=(",", ":"))))
            self.connection.commit()

    def activity(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute("""
            SELECT id, occurred_at, event_type, entity_type, entity_id, route, method,
                   status_code, details FROM activity_logs WHERE user_id = ? OR user_id IS NULL
            ORDER BY occurred_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item["details"])
            output.append(item)
        return output

    def summary(self, user_id: str) -> dict[str, int]:
        def count(table: str, where: str = "", params: tuple = ()) -> int:
            return int(self.connection.execute(f"SELECT COUNT(*) FROM {table} {where}", params).fetchone()[0])
        return {
            "hospitals": count("hospitals"), "doctors": count("doctors"), "patients": count("patients"),
            "medical_fields": len({field for h in self.hospitals() for field in h["medical_fields"]}),
            "appointments": count("appointments", "WHERE booked_by_user_id = ?", (user_id,)),
            "navigation_runs": count("navigation_runs", "WHERE user_id = ?", (user_id,)),
        }

    def close(self) -> None:
        self.connection.close()

    def create_user(self, user_id: str, email: str, display_name: str, password_hash: str, created_at: str) -> dict[str, Any]:
        with self.lock:
            self.connection.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                                    (user_id, email, display_name, password_hash, created_at))
            self.connection.commit()
        return self.get_user_by_email(email) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def create_session(self, token_hash: str, user_id: str, csrf_hash: str, created_at: str, expires_at: str) -> None:
        with self.lock:
            self.connection.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                                    (token_hash, user_id, csrf_hash, created_at, expires_at))
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
