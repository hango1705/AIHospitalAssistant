from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppStore:
    def __init__(
        self,
        db_path: Path | str = Path("data/app/app.sqlite3"),
        token_ttl_minutes: int = 480,
        default_admin_email: str = "admin",
        default_admin_password: str = "admin",
        default_admin_full_name: str = "Administrator",
    ) -> None:
        self.db_path = Path(db_path)
        self.token_ttl_minutes = token_ttl_minutes
        self.default_admin_email = default_admin_email.strip().lower()
        self.default_admin_password = default_admin_password
        self.default_admin_full_name = default_admin_full_name.strip() or "Administrator"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    patient_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    department TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS kb_update_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id INTEGER NOT NULL,
                    note TEXT NOT NULL,
                    status TEXT NOT NULL,
                    logs TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (admin_user_id) REFERENCES users(id)
                );
                """
            )
            self._ensure_column(connection, "tokens", "expires_at", "TEXT")
            self._ensure_column(connection, "kb_update_jobs", "logs", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "kb_update_jobs", "started_at", "TEXT")
            self._ensure_column(connection, "kb_update_jobs", "completed_at", "TEXT")
            fallback_expiry = self._token_expiry_iso()
            connection.execute(
                "UPDATE tokens SET expires_at = ? WHERE expires_at IS NULL OR expires_at = ''",
                (fallback_expiry,),
            )
            existing_admin = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (self.default_admin_email,),
            ).fetchone()
            if existing_admin is None:
                connection.execute(
                    """
                    INSERT INTO users (email, full_name, password_hash, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.default_admin_email,
                        self.default_admin_full_name,
                        self._hash_password(self.default_admin_password),
                        "admin",
                        utc_now_iso(),
                    ),
                )

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _hash_password(self, password: str, salt: str | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
        return f"{salt}:{digest}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            salt, expected = stored_hash.split(":", 1)
        except ValueError:
            return False
        actual = self._hash_password(password, salt).split(":", 1)[1]
        return hmac.compare_digest(actual, expected)

    def _token_expiry_iso(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(minutes=self.token_ttl_minutes)).isoformat()

    def create_user(self, email: str, full_name: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (email, full_name, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_email, full_name.strip(), self._hash_password(password), "patient", utc_now_iso()),
            )
            user_id = int(cursor.lastrowid)
        return self.get_user(user_id) or {}

    def authenticate(self, email: str, password: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            if row is None or not self._verify_password(password, str(row["password_hash"])):
                return None
            token = secrets.token_urlsafe(32)
            expires_at = self._token_expiry_iso()
            connection.execute(
                "INSERT INTO tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, int(row["id"]), utc_now_iso(), expires_at),
            )
            user = self._public_user(row)
            user["token"] = token
            return user

    def get_user(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._public_user(row) if row else None

    def get_user_by_token(self, token: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.*, tokens.expires_at AS token_expires_at FROM users
                JOIN tokens ON tokens.user_id = users.id
                WHERE tokens.token = ?
                """,
                (token,),
            ).fetchone()
            if row is None:
                return None
            expires_at = self._parse_datetime(str(row["token_expires_at"]))
            if expires_at is None or expires_at <= datetime.now(timezone.utc):
                connection.execute("DELETE FROM tokens WHERE token = ?", (token,))
                return None
            return self._public_user(row) if row else None

    def delete_token(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM tokens WHERE token = ?", (token,))

    def _parse_datetime(self, value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _public_user(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "email": str(row["email"]),
            "full_name": str(row["full_name"]),
            "role": str(row["role"]),
        }

    def save_chat_message(
        self,
        user_id: int,
        conversation_id: str,
        role: str,
        text: str,
        sources_json: str = "[]",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_messages (user_id, conversation_id, role, text, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, conversation_id, role, text, sources_json, utc_now_iso()),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
                (utc_now_iso(), conversation_id, user_id),
            )

    def ensure_conversation(self, user_id: int, conversation_id: str, title: str) -> dict:
        now = utc_now_iso()
        normalized_title = title.strip()[:80] or "Cuộc trò chuyện"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conversation_id, user_id, normalized_title, now, now),
                )
            else:
                connection.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
                    (now, conversation_id, user_id),
                )
        return self.get_conversation(user_id, conversation_id) or {}

    def get_conversation(self, user_id: int, conversation_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        return self._conversation(row) if row else None

    def list_conversations(self, user_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._conversation(row) for row in rows]

    def list_conversation_messages(self, user_id: int, conversation_id: str, limit: int = 200) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM chat_messages
                WHERE user_id = ? AND conversation_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (user_id, conversation_id, limit),
            ).fetchall()
        return [self._chat_message(row) for row in rows]

    def delete_conversation(self, user_id: int, conversation_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chat_messages WHERE user_id = ? AND conversation_id = ?", (user_id, conversation_id))
            connection.execute("DELETE FROM conversations WHERE user_id = ? AND id = ?", (user_id, conversation_id))

    def _conversation(self, row: sqlite3.Row) -> dict:
        return {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def list_chat_history(self, user_id: int, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM chat_messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._chat_message(row) for row in reversed(rows)]

    def clear_chat_history(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))

    def _chat_message(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "conversation_id": str(row["conversation_id"]),
            "role": str(row["role"]),
            "text": str(row["text"]),
            "sources_json": str(row["sources_json"]),
            "created_at": str(row["created_at"]),
        }

    def create_appointment(self, user_id: int, patient_name: str, phone: str, department: str, appointment_date: str, reason: str) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO appointments (user_id, patient_name, phone, department, appointment_date, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (user_id, patient_name, phone, department, appointment_date, reason, utc_now_iso()),
            )
            appointment_id = int(cursor.lastrowid)
        return self.get_appointment(user_id, appointment_id) or {}

    def get_appointment(self, user_id: int, appointment_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM appointments WHERE id = ? AND user_id = ?",
                (appointment_id, user_id),
            ).fetchone()
        return self._appointment(row) if row else None

    def list_appointments(self, user_id: int) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM appointments WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [self._appointment(row) for row in rows]

    def list_all_appointments(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM appointments ORDER BY id DESC").fetchall()
        return [self._appointment(row) for row in rows]

    def update_appointment_status(self, appointment_id: int, status: str) -> dict | None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE appointments SET status = ? WHERE id = ?",
                (status, appointment_id),
            )
            row = connection.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        return self._appointment(row) if row else None

    def _appointment(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "patient_name": str(row["patient_name"]),
            "phone": str(row["phone"]),
            "department": str(row["department"]),
            "appointment_date": str(row["appointment_date"]),
            "reason": str(row["reason"]),
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
        }

    def create_kb_update_job(self, admin_user_id: int, note: str) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO kb_update_jobs (admin_user_id, note, status, created_at)
                VALUES (?, ?, 'queued', ?)
                """,
                (admin_user_id, note, utc_now_iso()),
            )
            job_id = int(cursor.lastrowid)
        return self.get_kb_update_job(job_id) or {}

    def get_kb_update_job(self, job_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM kb_update_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._kb_job(row) if row else None

    def update_kb_update_job(self, job_id: int, status: str | None = None, append_log: str | None = None) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM kb_update_jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            next_status = status or str(row["status"])
            logs = str(row["logs"] or "")
            if append_log:
                logs = f"{logs}\n[{utc_now_iso()}] {append_log}".strip()
            started_at = str(row["started_at"]) if row["started_at"] else None
            completed_at = str(row["completed_at"]) if row["completed_at"] else None
            if next_status == "running" and started_at is None:
                started_at = utc_now_iso()
            if next_status in {"success", "failed"} and completed_at is None:
                completed_at = utc_now_iso()
            connection.execute(
                """
                UPDATE kb_update_jobs
                SET status = ?, logs = ?, started_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (next_status, logs, started_at, completed_at, job_id),
            )
        return self.get_kb_update_job(job_id)

    def list_kb_update_jobs(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM kb_update_jobs ORDER BY id DESC").fetchall()
        return [self._kb_job(row) for row in rows]

    def _kb_job(self, row: sqlite3.Row) -> dict:
        return {
            "id": int(row["id"]),
            "admin_user_id": int(row["admin_user_id"]),
            "note": str(row["note"]),
            "status": str(row["status"]),
            "logs": str(row["logs"] or ""),
            "created_at": str(row["created_at"]),
            "started_at": str(row["started_at"]) if row["started_at"] else None,
            "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
        }
