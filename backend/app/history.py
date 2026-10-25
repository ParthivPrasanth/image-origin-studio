"""Private, bounded local storage for opted-in analysis history.

This module deliberately knows nothing about authentication. Callers must pass
the subject from a verified identity token; client supplied IDs are never used
as filesystem paths.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class HistoryError(Exception):
    """Base class for expected history-store failures."""


class HistoryNotFound(HistoryError):
    """The record is unknown, expired, deleting, or owned by another subject."""


class HistoryQuotaExceeded(HistoryError):
    """A per-owner or shared storage cap prevents a new save."""


class HistoryStorageError(HistoryError):
    """A private database or file operation failed."""


class InvalidHistoryRecord(HistoryError, ValueError):
    """The supplied server result cannot be safely saved as a history record."""


_OBJECT_KEY = re.compile(r"^[0-9a-f]{64}$")
_CURSOR_VERSION = 1
_SCHEMA_VERSION = 1
_EXPIRY_DAYS = 30
_MAX_PAGE_SIZE = 100
_MODEL_KEYS = {"v3_e2", "community_forensics"}


def default_history_root() -> Path:
    """Return the ignored local history directory, with an env override."""
    configured = os.environ.get("IOS_HISTORY_ROOT")
    if configured:
        return Path(configured).expanduser()
    repository_root = Path(__file__).resolve().parents[2]
    return repository_root / ".local" / "history"


class HistoryStore:
    """SQLite metadata and opaque-key original files in one private directory.

    `root` is the history directory itself, for example `.local/history`.
    Every database write uses an immediate transaction so quota checks and row
    creation serialize across threads and processes.
    """

    MAX_ITEMS_PER_OWNER = 10
    MAX_BYTES_PER_OWNER = 50 * 1024 * 1024
    MAX_BYTES_GLOBAL = 500 * 1024 * 1024

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.originals_dir = self.root / "originals"
        self.database_path = self.root / "history.sqlite3"
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                self.originals_dir.mkdir(exist_ok=True)
            else:
                self.originals_dir.mkdir(mode=0o700, exist_ok=True)
            self._restrict_permissions(self.root, directory=True)
            self._restrict_permissions(self.originals_dir, directory=True)
            self._initialize_database()
        except HistoryStorageError:
            raise
        except OSError as exc:
            raise HistoryStorageError("The local history store is unavailable.") from exc

    @staticmethod
    def _restrict_permissions(path: Path, *, directory: bool) -> None:
        # POSIX mode bits can map to restrictive or readonly behavior on
        # Windows. There, rely on the user's inherited directory ACL instead.
        if os.name == "nt":
            return
        try:
            path.chmod(0o700 if directory else 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                str(self.database_path), timeout=30, isolation_level=None
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            raise HistoryStorageError("The local history database is unavailable.") from exc

    def _initialize_database(self) -> None:
        try:
            with closing(self._connect()) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > _SCHEMA_VERSION:
                    raise HistoryStorageError("The local history database version is unsupported.")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history_records (
                        id TEXT PRIMARY KEY,
                        owner_sub TEXT NOT NULL,
                        storage_key TEXT NOT NULL UNIQUE,
                        filename TEXT NOT NULL,
                        mime_type TEXT NOT NULL,
                        byte_count INTEGER NOT NULL CHECK (byte_count > 0),
                        sha256 TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        state TEXT NOT NULL CHECK (state IN ('active', 'deleting')),
                        requested_models_json TEXT NOT NULL,
                        result_json TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS history_owner_order
                       ON history_records(owner_sub, state, created_at DESC, id DESC)"""
                )
                connection.execute(
                    """CREATE INDEX IF NOT EXISTS history_expiry
                       ON history_records(state, expires_at)"""
                )
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.commit()
        except HistoryStorageError:
            raise
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not initialize the local history database.") from exc

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _owner(owner_sub: str) -> str:
        if not isinstance(owner_sub, str) or not owner_sub.strip():
            raise ValueError("A verified owner subject is required.")
        return owner_sub

    @staticmethod
    def _safe_filename(filename: str) -> str:
        if not isinstance(filename, str):
            filename = "upload"
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(
            character for character in filename
            if not unicodedata.category(character).startswith("C")
        ).strip()
        return (filename or "upload")[:255]

    @staticmethod
    def _safe_mime_type(mime_type: str | None) -> str:
        if not isinstance(mime_type, str):
            return "application/octet-stream"
        value = mime_type.strip()[:127]
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            return "application/octet-stream"
        return value

    @staticmethod
    def _serialize_result(
        result: dict[str, Any], data: bytes, requested_models: list[str]
    ) -> str:
        if not isinstance(result, dict):
            raise InvalidHistoryRecord("The analysis result must be a JSON object.")
        models = result.get("models")
        if not isinstance(models, list) or not any(
            isinstance(model, dict)
            and model.get("status") == "success"
            and model.get("model_key") in requested_models
            for model in models
        ):
            raise InvalidHistoryRecord("At least one requested model must succeed before saving.")
        result_input = result.get("input")
        if not isinstance(result_input, dict):
            raise InvalidHistoryRecord("The analysis result is missing input metadata.")
        expected_hash = hashlib.sha256(data).hexdigest()
        if result_input.get("sha256") != expected_hash:
            raise InvalidHistoryRecord("The analysis result does not match the original bytes.")
        try:
            return json.dumps(
                result, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
        except (TypeError, ValueError) as exc:
            raise InvalidHistoryRecord("The analysis result is not valid JSON data.") from exc

    @staticmethod
    def _serialize_models(requested_models: list[str]) -> str:
        if (
            not isinstance(requested_models, list)
            or not requested_models
            or len(requested_models) > len(_MODEL_KEYS)
            or any(not isinstance(model, str) or model not in _MODEL_KEYS
                   for model in requested_models)
            or len(set(requested_models)) != len(requested_models)
        ):
            raise InvalidHistoryRecord("The requested model selection is invalid.")
        return json.dumps(requested_models, separators=(",", ":"))

    def _object_path(self, storage_key: str) -> Path:
        if not _OBJECT_KEY.fullmatch(storage_key):
            raise HistoryStorageError("A stored original has an invalid private key.")
        return self.originals_dir / f"{storage_key}.bin"

    def _write_original(self, storage_key: str, data: bytes) -> Path:
        path = self._object_path(storage_key)
        try:
            with path.open("xb") as output:
                self._restrict_permissions(path, directory=False)
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            return path
        except OSError as exc:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HistoryStorageError("Could not store the private original.") from exc

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        try:
            return {
                "history_id": row["id"],
                "filename": row["filename"],
                "mime_type": row["mime_type"],
                "byte_count": row["byte_count"],
                "original_sha256": row["sha256"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "status": row["state"],
                "requested_models": json.loads(row["requested_models_json"]),
                "result": json.loads(row["result_json"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise HistoryStorageError("The stored history record is invalid.") from exc

    def _quota_in_transaction(
        self, connection: sqlite3.Connection, owner_sub: str
    ) -> dict[str, int | bool]:
        owner_row = connection.execute(
            """SELECT COUNT(*) AS items, COALESCE(SUM(byte_count), 0) AS bytes
               FROM history_records WHERE owner_sub = ?""",
            (owner_sub,),
        ).fetchone()
        global_row = connection.execute(
            "SELECT COALESCE(SUM(byte_count), 0) AS bytes FROM history_records"
        ).fetchone()
        used_items = int(owner_row["items"])
        used_bytes = int(owner_row["bytes"])
        global_bytes = int(global_row["bytes"])
        return {
            "used_items": used_items,
            "max_items": self.MAX_ITEMS_PER_OWNER,
            "used_bytes": used_bytes,
            "max_bytes": self.MAX_BYTES_PER_OWNER,
            "global_full": global_bytes >= self.MAX_BYTES_GLOBAL,
        }

    def quota(self, owner_sub: str) -> dict[str, int | bool]:
        owner_sub = self._owner(owner_sub)
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN")
                quota = self._quota_in_transaction(connection, owner_sub)
                connection.commit()
                return quota
        except HistoryStorageError:
            raise
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not read history quota.") from exc

    def save(
        self,
        owner_sub: str,
        filename: str,
        mime_type: str | None,
        data: bytes,
        result: dict[str, Any],
        requested_models: list[str],
    ) -> dict[str, Any]:
        """Save exact original bytes and a matching successful result snapshot."""
        owner_sub = self._owner(owner_sub)
        if not isinstance(data, bytes) or not data:
            raise InvalidHistoryRecord("The original image bytes are empty or invalid.")
        models_json = self._serialize_models(requested_models)
        result_json = self._serialize_result(result, data, requested_models)
        result_snapshot = json.loads(result_json)
        selected_models = json.loads(models_json)
        now = self._now()
        created_at = self._iso(now)
        expires_at = self._iso(now + timedelta(days=_EXPIRY_DAYS))
        display_filename = self._safe_filename(filename)
        display_mime = self._safe_mime_type(mime_type)
        byte_count = len(data)
        sha256 = hashlib.sha256(data).hexdigest()
        history_id = uuid4().hex
        storage_key = secrets.token_hex(32)
        object_path: Path | None = None
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            quota = self._quota_in_transaction(connection, owner_sub)
            global_row = connection.execute(
                "SELECT COALESCE(SUM(byte_count), 0) AS bytes FROM history_records"
            ).fetchone()
            if quota["used_items"] >= self.MAX_ITEMS_PER_OWNER:
                raise HistoryQuotaExceeded("The account history item limit has been reached.")
            if quota["used_bytes"] + byte_count > self.MAX_BYTES_PER_OWNER:
                raise HistoryQuotaExceeded("The account history storage limit has been reached.")
            if int(global_row["bytes"]) + byte_count > self.MAX_BYTES_GLOBAL:
                raise HistoryQuotaExceeded("The shared history storage limit has been reached.")

            object_path = self._write_original(storage_key, data)
            connection.execute(
                """INSERT INTO history_records (
                       id, owner_sub, storage_key, filename, mime_type, byte_count,
                       sha256, created_at, expires_at, state,
                       requested_models_json, result_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
                (
                    history_id, owner_sub, storage_key, display_filename, display_mime,
                    byte_count, sha256, created_at, expires_at, models_json, result_json,
                ),
            )
            connection.commit()
        except HistoryQuotaExceeded:
            connection.rollback()
            raise
        except HistoryError:
            connection.rollback()
            raise
        except (sqlite3.Error, OSError) as exc:
            connection.rollback()
            if object_path is not None:
                try:
                    object_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise HistoryStorageError("Could not save the private history record.") from exc
        finally:
            connection.close()
        return {
            "history_id": history_id,
            "filename": display_filename,
            "mime_type": display_mime,
            "byte_count": byte_count,
            "original_sha256": sha256,
            "created_at": created_at,
            "expires_at": expires_at,
            "status": "active",
            "requested_models": selected_models,
            "result": result_snapshot,
        }

    @staticmethod
    def _encode_cursor(created_at: str, history_id: str) -> str:
        encoded = json.dumps(
            [_CURSOR_VERSION, created_at, history_id], separators=(",", ":")
        ).encode("utf-8")
        return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[str, str]:
        try:
            if not isinstance(cursor, str) or len(cursor) > 512:
                raise ValueError
            padded = cursor + "=" * (-len(cursor) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
            if (
                not isinstance(decoded, list)
                or len(decoded) != 3
                or decoded[0] != _CURSOR_VERSION
                or not isinstance(decoded[1], str)
                or not isinstance(decoded[2], str)
                or not re.fullmatch(r"[0-9a-f]{32}", decoded[2])
            ):
                raise ValueError
            if datetime.fromisoformat(decoded[1]).tzinfo is None:
                raise ValueError
            return decoded[1], decoded[2]
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("The history page cursor is invalid.") from exc

    def list(
        self, owner_sub: str, cursor: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        owner_sub = self._owner(owner_sub)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"History page size must be between 1 and {_MAX_PAGE_SIZE}.")
        cursor_values = self._decode_cursor(cursor) if cursor is not None else None
        now = self._iso(self._now())
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN")
                query = """SELECT * FROM history_records
                           WHERE owner_sub = ? AND state = 'active' AND expires_at > ?"""
                params: list[Any] = [owner_sub, now]
                if cursor_values:
                    query += " AND (created_at < ? OR (created_at = ? AND id < ?))"
                    params.extend([cursor_values[0], cursor_values[0], cursor_values[1]])
                query += " ORDER BY created_at DESC, id DESC LIMIT ?"
                params.append(limit + 1)
                rows = connection.execute(query, params).fetchall()
                quota = self._quota_in_transaction(connection, owner_sub)
                connection.commit()
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not list private history records.") from exc

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            self._encode_cursor(page_rows[-1]["created_at"], page_rows[-1]["id"])
            if has_more and page_rows
            else None
        )
        return {
            "items": [self._record(row) for row in page_rows],
            "next_cursor": next_cursor,
            "quota": quota,
        }

    def _active_record(self, owner_sub: str, history_id: str) -> sqlite3.Row:
        if not isinstance(history_id, str) or not re.fullmatch(r"[0-9a-f]{32}", history_id):
            raise HistoryNotFound("The history record is unavailable.")
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """SELECT * FROM history_records
                       WHERE id = ? AND owner_sub = ? AND state = 'active'""",
                    (history_id, owner_sub),
                ).fetchone()
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not read the private history record.") from exc
        if row is None or row["expires_at"] <= self._iso(self._now()):
            raise HistoryNotFound("The history record is unavailable.")
        return row

    def get(self, owner_sub: str, history_id: str) -> dict[str, Any]:
        owner_sub = self._owner(owner_sub)
        return self._record(self._active_record(owner_sub, history_id))

    def read_original(self, owner_sub: str, history_id: str) -> bytes:
        owner_sub = self._owner(owner_sub)
        row = self._active_record(owner_sub, history_id)
        path = self._object_path(row["storage_key"])
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise HistoryStorageError("The private original is temporarily unavailable.") from exc
        if len(data) != row["byte_count"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise HistoryStorageError("The private original failed its integrity check.")
        return data

    def _mark_deleting(self, owner_sub: str, history_id: str) -> sqlite3.Row:
        if not isinstance(history_id, str) or not re.fullmatch(r"[0-9a-f]{32}", history_id):
            raise HistoryNotFound("The history record is unavailable.")
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM history_records WHERE id = ? AND owner_sub = ?",
                    (history_id, owner_sub),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise HistoryNotFound("The history record is unavailable.")
                connection.execute(
                    "UPDATE history_records SET state = 'deleting' WHERE id = ? AND owner_sub = ?",
                    (history_id, owner_sub),
                )
                connection.commit()
                return row
        except HistoryNotFound:
            raise
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not mark the history record for deletion.") from exc

    def _remove_deleting(self, row: sqlite3.Row) -> None:
        path = self._object_path(row["storage_key"])
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise HistoryStorageError("Deletion is pending and will be retried.") from exc
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM history_records WHERE id = ? AND state = 'deleting'",
                    (row["id"],),
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise HistoryStorageError("Deletion is pending and will be retried.") from exc

    def delete(self, owner_sub: str, history_id: str) -> dict[str, bool]:
        owner_sub = self._owner(owner_sub)
        row = self._mark_deleting(owner_sub, history_id)
        self._remove_deleting(row)
        return {"deleted": True, "pending": False}

    def delete_account(self, owner_sub: str) -> dict[str, int | bool]:
        """Delete all of an owner's records, retaining failed items for retry."""
        owner_sub = self._owner(owner_sub)
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    "SELECT * FROM history_records WHERE owner_sub = ?", (owner_sub,)
                ).fetchall()
                connection.execute(
                    "UPDATE history_records SET state = 'deleting' WHERE owner_sub = ?",
                    (owner_sub,),
                )
                connection.commit()
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not start account history deletion.") from exc
        deleted = 0
        pending = 0
        for row in rows:
            try:
                self._remove_deleting(row)
                deleted += 1
            except HistoryStorageError:
                pending += 1
        return {"deleted": deleted, "pending": pending, "complete": pending == 0}

    def sweep(self) -> dict[str, int]:
        """Expire records, retry pending deletions, and remove orphaned originals."""
        now = self._iso(self._now())
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                expired = connection.execute(
                    """UPDATE history_records SET state = 'deleting'
                       WHERE state = 'active' AND expires_at <= ?""",
                    (now,),
                ).rowcount
                pending_rows = connection.execute(
                    "SELECT * FROM history_records WHERE state = 'deleting'"
                ).fetchall()
                connection.commit()
        except sqlite3.Error as exc:
            raise HistoryStorageError("Could not start the history cleanup sweep.") from exc

        removed = 0
        errors = 0
        for row in pending_rows:
            try:
                self._remove_deleting(row)
                removed += 1
            except HistoryStorageError:
                errors += 1
        orphaned = self._remove_orphans()
        return {
            "expired_marked": int(expired),
            "removed": removed,
            "pending": errors,
            "orphans_removed": orphaned,
        }

    def _remove_orphans(self) -> int:
        removed = 0
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                referenced = {
                    row[0]
                    for row in connection.execute("SELECT storage_key FROM history_records")
                }
                with os.scandir(self.originals_dir) as entries:
                    for entry in entries:
                        name = entry.name
                        if not name.endswith(".bin"):
                            continue
                        storage_key = name[:-4]
                        if storage_key in referenced or not _OBJECT_KEY.fullmatch(storage_key):
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        try:
                            Path(entry.path).unlink(missing_ok=True)
                            removed += 1
                        except OSError:
                            continue
                connection.commit()
        except (sqlite3.Error, OSError) as exc:
            raise HistoryStorageError("Could not reconcile orphaned private originals.") from exc
        return removed
