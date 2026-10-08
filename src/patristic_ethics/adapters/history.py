"""Bounded hook-observed history; never claims a complete host transcript."""

import os
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

MAX_MESSAGES = 40
MAX_CHARS = 16000


def _connect():
    path = Path(os.environ["PEA_HISTORY_DB"])
    # Explicit operator-configured path only; never use a payload transcript path.
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    conn = sqlite3.connect(path, timeout=1)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS observed (id INTEGER PRIMARY KEY, host TEXT, session TEXT, role TEXT, text TEXT, truncated INTEGER)")
        if "event_key" not in {r[1] for r in conn.execute("PRAGMA table_info(observed)")}:
            conn.execute("ALTER TABLE observed ADD COLUMN event_key TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS observed_event ON observed(host, session, event_key)")
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def collect(envelope: dict) -> None:
    if not os.environ.get("PEA_HISTORY_DB"):
        return
    history = envelope["history"]
    history["complete"] = False
    history.setdefault("collection_errors", []).append("hook-observed history only; earlier, bypassed and compacted host messages may be missing")
    host, session = envelope["host"]["name"], envelope["session"]["id"]
    if not session or session == "unknown":
        history["collection_errors"].append("history requires a known session id")
        return
    try:
        conn = _connect()
        try:
            rows = conn.execute("SELECT id, role, text, truncated FROM observed WHERE host=? AND session=? ORDER BY id DESC LIMIT ?", (host, session, MAX_MESSAGES + 1)).fetchall()
        finally:
            conn.close()
        chosen, size = [], 0
        if any(not isinstance(seq, int) or role not in {"user", "assistant"}
               or not isinstance(text, str) or truncated not in (0, 1)
               for seq, role, text, truncated in rows):
            raise ValueError("invalid stored history")
        for row in rows[:MAX_MESSAGES]:
            if size + len(row[2]) > MAX_CHARS:
                break
            chosen.append(row)
            size += len(row[2])
        if len(chosen) != len(rows) or any(r[3] for r in chosen):
            history.setdefault("omitted_ranges", []).append("hook history bounded to 40 messages / 16000 characters; earlier or overlong content omitted")
        envelope["messages"] = [dict(role=role, source_id=f"hook-{host}-{seq}", seq=seq,
                                     text=text, origin=role) for seq, role, text, _ in reversed(chosen)]
        history["modalities"] = ["text"]
    except (OSError, sqlite3.Error, ValueError):
        history["collection_errors"].append("hook history store unavailable")


def remember(envelope: dict, action: str) -> None:
    if not os.environ.get("PEA_HISTORY_DB") or not isinstance(action, str):
        return
    if envelope["stage"] == "input" and action in {"proceed", "guide"}:
        role, text = "user", envelope["request"]
    elif envelope["stage"] == "output" and envelope.get("_hook_event") == "Stop":
        role, text = "assistant", envelope["candidate_response"]
    else:
        return
    host, session = envelope["host"]["name"], envelope["session"]["id"]
    if not session or session == "unknown" or not text:
        return
    event_id = envelope.get("_hook_event_id")
    event_key = None
    if isinstance(event_id, str) and event_id:
        event_key = hashlib.sha256(json.dumps([event_id, role, text], ensure_ascii=False).encode()).hexdigest()
    try:
        conn = _connect()
        try:
            with conn:
                conn.execute("INSERT OR IGNORE INTO observed(host,session,role,text,truncated,event_key) VALUES(?,?,?,?,?,?)", (host, session, role, text[:MAX_CHARS], len(text) > MAX_CHARS, event_key))
                conn.execute("DELETE FROM observed WHERE host=? AND session=? AND id NOT IN (SELECT id FROM observed WHERE host=? AND session=? ORDER BY id DESC LIMIT ?)", (host, session, host, session, MAX_MESSAGES + 1))
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        # Storage failure cannot convert an assessment into permission to proceed.
        print("PEA hook history could not be persisted; future context may be incomplete.", file=sys.stderr)
