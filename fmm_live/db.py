"""SQLite-Speicher. Jede Abfrage ist an eine streamer_id gebunden (Mandantentrennung)."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS streamers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tiktok_user TEXT NOT NULL DEFAULT '',
    token_hash TEXT NOT NULL UNIQUE,
    mod_token_hash TEXT UNIQUE,
    settings TEXT NOT NULL DEFAULT '{}',
    setup_done INTEGER NOT NULL DEFAULT 0,
    bot_active INTEGER NOT NULL DEFAULT 0,
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    last_seen_at REAL,
    client_info TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS live_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    streamer_id INTEGER NOT NULL REFERENCES streamers(id),
    started_at REAL NOT NULL,
    ended_at REAL,
    room_id TEXT,
    comments INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    streamer_id INTEGER NOT NULL REFERENCES streamers(id),
    session_id INTEGER,
    ts REAL NOT NULL,
    viewer_id TEXT NOT NULL DEFAULT '',
    viewer_name TEXT NOT NULL DEFAULT '',
    viewer_handle TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    decision TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    suggestion TEXT NOT NULL DEFAULT '',
    is_test INTEGER NOT NULL DEFAULT 0,
    handled INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_events_streamer ON events(streamer_id, id);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    streamer_id INTEGER NOT NULL REFERENCES streamers(id),
    ts REAL NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_usage_streamer ON usage(streamer_id, ts);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    streamer_id INTEGER,
    ts REAL NOT NULL,
    area TEXT NOT NULL,
    message TEXT NOT NULL
);
"""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(24)


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA secure_delete=ON")  # geloeschte Chat-Daten werden ueberschrieben
            self._conn.executescript(SCHEMA)

    # -- Basis -------------------------------------------------------------
    def _exec(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def _one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        row = self._exec(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [dict(r) for r in self._exec(sql, params).fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- Streamer ----------------------------------------------------------
    def create_streamer(self, name: str, settings: dict) -> tuple[int, str]:
        """Legt einen Streamer an. Gibt (id, Klartext-Zugangstoken) zurueck - nur einmal sichtbar."""
        token = new_token()
        cur = self._exec(
            "INSERT INTO streamers(name, token_hash, settings, created_at) VALUES (?,?,?,?)",
            (name.strip()[:80], hash_token(token), json.dumps(settings), time.time()),
        )
        return int(cur.lastrowid), token

    def rotate_token(self, streamer_id: int) -> str:
        token = new_token()
        self._exec("UPDATE streamers SET token_hash=? WHERE id=?", (hash_token(token), streamer_id))
        return token

    def rotate_mod_token(self, streamer_id: int) -> str:
        token = new_token()
        self._exec("UPDATE streamers SET mod_token_hash=? WHERE id=?", (hash_token(token), streamer_id))
        return token

    def streamer_by_token(self, token: str) -> tuple[dict, str] | None:
        """Liefert (Streamer, Rolle) - Rolle 'streamer' oder 'mod'."""
        if not token:
            return None
        h = hash_token(token)
        row = self._one("SELECT * FROM streamers WHERE token_hash=? AND disabled=0", (h,))
        if row:
            return self._decode(row), "streamer"
        row = self._one("SELECT * FROM streamers WHERE mod_token_hash=? AND disabled=0", (h,))
        if row:
            return self._decode(row), "mod"
        return None

    def get_streamer(self, streamer_id: int) -> dict | None:
        row = self._one("SELECT * FROM streamers WHERE id=?", (streamer_id,))
        return self._decode(row) if row else None

    def list_streamers(self) -> list[dict]:
        return [self._decode(r) for r in self._all("SELECT * FROM streamers ORDER BY id")]

    def update_streamer(self, streamer_id: int, **fields: Any) -> None:
        allowed = {"name", "tiktok_user", "settings", "setup_done", "bot_active", "disabled",
                   "last_seen_at", "client_info"}
        sets, params = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"Feld nicht erlaubt: {key}")
            if key == "settings":
                value = json.dumps(value)
            sets.append(f"{key}=?")
            params.append(value)
        if sets:
            params.append(streamer_id)
            self._exec(f"UPDATE streamers SET {', '.join(sets)} WHERE id=?", params)

    def delete_streamer_data(self, streamer_id: int) -> None:
        """Loescht alle Daten eines Streamers (DSGVO-Loeschanspruch)."""
        for table in ("events", "live_sessions", "usage", "errors"):
            self._exec(f"DELETE FROM {table} WHERE streamer_id=?", (streamer_id,))
        self._exec("DELETE FROM streamers WHERE id=?", (streamer_id,))

    @staticmethod
    def _decode(row: dict) -> dict:
        row = dict(row)
        try:
            row["settings"] = json.loads(row.get("settings") or "{}")
        except json.JSONDecodeError:
            row["settings"] = {}
        row.pop("token_hash", None)
        row["has_mod_link"] = bool(row.pop("mod_token_hash", None))
        return row

    # -- Meta --------------------------------------------------------------
    def meta_get(self, key: str) -> str | None:
        row = self._one("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else None

    def meta_setdefault(self, key: str, value: str) -> str:
        self._exec("INSERT OR IGNORE INTO meta(key, value) VALUES (?,?)", (key, value))
        return self.meta_get(key) or value

    def count_streamers(self) -> int:
        return int(self._one("SELECT COUNT(*) AS n FROM streamers")["n"])

    # -- Live-Sessions -----------------------------------------------------
    def start_session(self, streamer_id: int, room_id: str | None) -> int:
        cur = self._exec(
            "INSERT INTO live_sessions(streamer_id, started_at, room_id) VALUES (?,?,?)",
            (streamer_id, time.time(), room_id),
        )
        return int(cur.lastrowid)

    def end_session(self, session_id: int) -> None:
        self._exec("UPDATE live_sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
                   (time.time(), session_id))

    def close_open_sessions(self) -> None:
        self._exec("UPDATE live_sessions SET ended_at=? WHERE ended_at IS NULL", (time.time(),))

    def bump_session(self, session_id: int, flagged: bool) -> None:
        self._exec("UPDATE live_sessions SET comments=comments+1, flagged=flagged+? WHERE id=?",
                   (1 if flagged else 0, session_id))

    def sessions(self, streamer_id: int, limit: int = 20) -> list[dict]:
        return self._all("SELECT * FROM live_sessions WHERE streamer_id=? ORDER BY id DESC LIMIT ?",
                         (streamer_id, limit))

    # -- Events ------------------------------------------------------------
    def add_event(self, streamer_id: int, ev: dict) -> int:
        cur = self._exec(
            """INSERT INTO events(streamer_id, session_id, ts, viewer_id, viewer_name, viewer_handle,
               text, decision, category, reason, source, suggestion, is_test)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (streamer_id, ev.get("session_id"), ev.get("ts", time.time()), ev.get("viewer_id", ""),
             ev.get("viewer_name", ""), ev.get("viewer_handle", ""), ev["text"][:500], ev["decision"],
             ev.get("category", ""), ev.get("reason", "")[:300], ev.get("source", ""),
             ev.get("suggestion", "")[:300], 1 if ev.get("is_test") else 0),
        )
        return int(cur.lastrowid)

    def events(self, streamer_id: int, *, after_id: int = 0, only_flagged: bool = False,
               session_id: int | None = None, limit: int = 200) -> list[dict]:
        sql = "SELECT * FROM events WHERE streamer_id=? AND id>?"
        params: list[Any] = [streamer_id, after_id]
        if only_flagged:
            sql += " AND decision NOT IN ('ok')"
        if session_id is not None:
            sql += " AND session_id=?"
            params.append(session_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return list(reversed(self._all(sql, params)))

    def mark_handled(self, streamer_id: int, event_id: int) -> bool:
        cur = self._exec("UPDATE events SET handled=1 WHERE id=? AND streamer_id=?", (event_id, streamer_id))
        return cur.rowcount > 0

    def purge_old(self, retention_days: int) -> int:
        cutoff = time.time() - retention_days * 86400
        n = self._exec("DELETE FROM events WHERE ts<?", (cutoff,)).rowcount
        self._exec("DELETE FROM errors WHERE ts<?", (cutoff,))
        if n:
            with self._lock:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return n

    # -- Kosten ------------------------------------------------------------
    def add_usage(self, streamer_id: int, model: str, tin: int, tout: int, cost: float) -> None:
        self._exec("INSERT INTO usage(streamer_id, ts, model, input_tokens, output_tokens, cost_usd) "
                   "VALUES (?,?,?,?,?,?)", (streamer_id, time.time(), model, tin, tout, cost))

    def usage_summary(self, streamer_id: int | None = None, since: float = 0) -> list[dict]:
        sql = ("SELECT streamer_id, COUNT(*) AS calls, SUM(input_tokens) AS input_tokens, "
               "SUM(output_tokens) AS output_tokens, ROUND(SUM(cost_usd), 4) AS cost_usd "
               "FROM usage WHERE ts>=?")
        params: list[Any] = [since]
        if streamer_id is not None:
            sql += " AND streamer_id=?"
            params.append(streamer_id)
        sql += " GROUP BY streamer_id"
        return self._all(sql, params)

    # -- Fehler ------------------------------------------------------------
    def add_error(self, streamer_id: int | None, area: str, message: str) -> None:
        self._exec("INSERT INTO errors(streamer_id, ts, area, message) VALUES (?,?,?,?)",
                   (streamer_id, time.time(), area[:40], message[:500]))

    def errors(self, streamer_id: int | None = None, limit: int = 50) -> list[dict]:
        if streamer_id is None:
            return self._all("SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,))
        return self._all("SELECT * FROM errors WHERE streamer_id=? ORDER BY id DESC LIMIT ?",
                         (streamer_id, limit))
