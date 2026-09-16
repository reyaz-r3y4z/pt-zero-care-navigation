"""Argon2 password authentication with opaque, revocable cookie sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pwdlib import PasswordHash

from app.repository import Repository


SESSION_HOURS = 8


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    user: dict[str, Any]


class AuthService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.password_hash = PasswordHash.recommended()
        self.dummy_hash = self.password_hash.hash("not-a-real-user-password")

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().casefold()

    def register(self, email: str, display_name: str, password: str) -> IssuedSession:
        normalized = self.normalize_email(email)
        if self.repository.get_user_by_email(normalized):
            raise ValueError("An account with this email already exists")
        try:
            user = self.repository.create_user(
                user_id=str(uuid.uuid4()),
                email=normalized,
                display_name=display_name.strip(),
                password_hash=self.password_hash.hash(password),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with this email already exists") from error
        return self._issue_session(user)

    def login(self, email: str, password: str) -> IssuedSession:
        user = self.repository.get_user_by_email(self.normalize_email(email))
        stored_hash = user["password_hash"] if user else self.dummy_hash
        valid = self.password_hash.verify(password, stored_hash)
        if not user or not valid:
            raise ValueError("Invalid email or password")
        return self._issue_session(user)

    def _issue_session(self, user: dict[str, Any]) -> IssuedSession:
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        created = datetime.now(timezone.utc)
        self.repository.cleanup_expired_sessions(created.isoformat())
        self.repository.create_session(
            token_hash=digest(token),
            user_id=user["id"],
            csrf_hash=digest(csrf_token),
            created_at=created.isoformat(),
            expires_at=(created + timedelta(hours=SESSION_HOURS)).isoformat(),
        )
        return IssuedSession(token, csrf_token, user)

    def authenticate(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        return self.repository.get_session(
            digest(token), datetime.now(timezone.utc).isoformat()
        )

    def verify_csrf(self, session: dict[str, Any], token: str | None) -> bool:
        return bool(token) and hmac.compare_digest(session["csrf_hash"], digest(token))

    def logout(self, token: str) -> None:
        self.repository.delete_session(digest(token))

    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, str]:
        return {
            "id": user["user_id"] if "user_id" in user else user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "created_at": (
                user["user_created_at"] if "user_created_at" in user else user["created_at"]
            ),
        }
