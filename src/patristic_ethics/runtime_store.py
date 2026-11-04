"""Runtime review/audit store (plan section 5.5; M3 items 3-4).

Separate LOCAL runtime SQLite database for pending reviews and event
audit — never the read-only corpus db.

AGENT-FACING vs OPERATOR BOUNDARY (the core security property):

Agent-facing surface (safe to call from the agent process):
    open_review, get_review, get_review_status, try_record_event,
    claim_dispatch, mark_dispatched, reassess_required, expire_stale,
    stuck_attempts.
There is deliberately NO approve/deny method, and no public function
accepts an approval boolean anywhere.

Operator-facing:
    resolve_review(review_id, decision, operator_token, ...).
Authorization is an out-of-band operator token read from the env var
PEA_OPERATOR_TOKEN, set only in the operator process. The token value
is never stored in the db (resolved_by records the role, not the
secret).

BOUNDARY CAVEAT (documented limitation, not a completed boundary):
the env-token check is a PLACEHOLDER for an OS-identity / sandbox
boundary. Plan section 5.5: "a shell-capable agent must not be able to
approve itself"; merely another filename, a CLI switch, or a secret
readable by the agent is insufficient. A shell-capable agent that can
read the operator's environment or write this db file can defeat this
placeholder. Merely knowing the db path must not be sufficient:
deployment must run the resolver under a separate OS identity /
sandbox so the agent process can neither read PEA_OPERATOR_TOKEN nor
write runtime.db. Until that separation is demonstrated, the
controlled profile keeps shell and other approval-altering paths
disabled.

DISPATCH SEMANTICS: at-most-once, never a promise of exactly-once
effects. claim_dispatch atomically flips approved/none -> attempted
only when the current action, context, policy version, and expiry match
the review (one UPDATE, rowcount==1 wins). If the process dies after claiming,
NO function auto-retries the attempt — stuck_attempts() is operator
inspection only, and re-dispatching requires operator judgment plus a
NEW review (open_review + reassessment). Expired reviews resolve to
denied only with a note; re-opening always goes through open_review.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

__all__ = [
    "OperatorBoundaryError",
    "ReviewNotAllowed",
    "RuntimeStore",
    "digest",
]

_TOKEN_ENV = "PEA_OPERATOR_TOKEN"


class OperatorBoundaryError(PermissionError):
    """Operator authorization missing or invalid."""


class ReviewNotAllowed(Exception):
    """A refuse / non-overridable decision can never open a review."""


def digest(obj: Any) -> str:
    """Canonical-JSON sha256 hex digest (sorted keys, compact separators)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id           TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    stage              TEXT NOT NULL,
    action             TEXT NOT NULL,
    disposition        TEXT NOT NULL,
    principle_ids_json TEXT NOT NULL,
    policy_version     TEXT NOT NULL,
    corpus_version     TEXT NOT NULL,
    latency_ms         REAL,
    created_at         REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    review_id       TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    action_digest   TEXT NOT NULL,
    context_digest  TEXT NOT NULL,
    policy_version  TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK(status IN ('pending','approved','denied','expired')),
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL,
    resolved_at     REAL,
    resolved_by     TEXT,
    resolution_note TEXT,
    dispatch_state  TEXT NOT NULL DEFAULT 'none'
                    CHECK(dispatch_state IN ('none','attempted','dispatched')),
    claimed_at      REAL,
    action_json     TEXT NOT NULL DEFAULT '{}',
    context_json    TEXT NOT NULL DEFAULT '{}',
    reason          TEXT NOT NULL DEFAULT ''
);
"""


class RuntimeStore:
    """Local runtime store for review state and event audit."""

    def __init__(self, db_path: Any):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.conn.executescript(_SCHEMA)
        self._migrate_reviews()

    def _migrate_reviews(self) -> None:
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(reviews)")}
        # SQLite forbids bind parameters in ALTER TABLE, so each statement is a literal.
        if "action_json" not in columns:
            self.conn.execute("ALTER TABLE reviews ADD COLUMN action_json TEXT NOT NULL DEFAULT '{}'")
        if "context_json" not in columns:
            self.conn.execute("ALTER TABLE reviews ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")
        if "reason" not in columns:
            self.conn.execute("ALTER TABLE reviews ADD COLUMN reason TEXT NOT NULL DEFAULT ''")

    @property
    def conn(self) -> sqlite3.Connection:
        """Give each worker its own SQLite handle; connections stay thread-local."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            self._local.conn = conn
        return conn

    # --- events (agent-facing; audit only) -----------------------------

    def try_record_event(
        self,
        event_id: str,
        session_id: str,
        stage: str,
        action: str,
        disposition: str,
        principle_ids: list[str] | None = None,
        policy_version: str = "",
        corpus_version: str = "",
        latency_ms: float | None = None,
        created_at: float | None = None,
    ) -> bool:
        """Insert one audit event; False on duplicate event_id (hook-retry safe).

        The UNIQUE/PK event_id plus INSERT OR IGNORE make retries
        idempotent at the database level, even across store instances.
        """
        with self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO events (event_id, session_id, stage,"
                " action, disposition, principle_ids_json, policy_version,"
                " corpus_version, latency_ms, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    session_id,
                    stage,
                    action,
                    disposition,
                    json.dumps(principle_ids or []),
                    policy_version,
                    corpus_version,
                    latency_ms,
                    created_at if created_at is not None else time.time(),
                ),
            )
        return cur.rowcount == 1

    # --- reviews: lifecycle (agent-facing) -------------------------------

    def open_review(
        self,
        session_id: str,
        action: Any,
        context: Any,
        policy_version: str,
        ttl_s: float = 3600.0,
        non_overridable: bool = False,
        reason: str = "",
    ) -> str:
        """Open a pending review bound to digests + policy version + expiry.

        non_overridable=True (callers pass decision.non_overridable)
        raises ReviewNotAllowed: a refuse decision is never reviewable.
        """
        if non_overridable:
            raise ReviewNotAllowed(
                "non-overridable decisions cannot open a review"
            )
        if ttl_s <= 0:
            raise ValueError("review ttl_s must be positive")
        now = time.time()
        action_digest, context_digest = digest(action), digest(context)
        existing = self.conn.execute(
            "SELECT review_id FROM reviews WHERE session_id = ? AND action_digest = ?"
            " AND context_digest = ? AND policy_version = ? AND status = 'pending'"
            " AND expires_at > ? ORDER BY created_at LIMIT 1",
            (session_id, action_digest, context_digest, policy_version, now),
        ).fetchone()
        if existing is not None:
            return existing["review_id"]
        review_id = uuid.uuid4().hex
        with self.conn:
            self.conn.execute(
                "INSERT INTO reviews (review_id, session_id, action_digest,"
                " context_digest, policy_version, status, created_at,"
                " expires_at, dispatch_state, action_json, context_json, reason)"
                " VALUES (?,?,?,?,?,?,?,?, 'none',?,?,?)",
                (
                    review_id,
                    session_id,
                    action_digest,
                    context_digest,
                    policy_version,
                    "pending",
                    now,
                    now + ttl_s,
                    json.dumps(action, sort_keys=True, separators=(",", ":")),
                    json.dumps(context, sort_keys=True, separators=(",", ":")),
                    reason,
                ),
            )
        return review_id

    def get_review(self, review_id: str) -> dict | None:
        """Full review row (operator/diagnostic read)."""
        row = self.conn.execute(
            "SELECT * FROM reviews WHERE review_id = ?", (review_id,)
        ).fetchone()
        return self._review_row(row) if row is not None else None

    def get_review_status(self, review_id: str) -> dict | None:
        """Agent-facing limited view: status, review_id, expires_at only.

        Never exposes resolved_by or resolution_note.
        """
        row = self.conn.execute(
            "SELECT status, expires_at FROM reviews WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "review_id": review_id,
            "status": row["status"],
            "expires_at": row["expires_at"],
        }

    def list_reviews(self, status: str | None = None) -> list[dict]:
        """Operator view of reviews, including the exact material under review."""
        if status is None:
            rows = self.conn.execute(
                "SELECT * FROM reviews ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM reviews WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [self._review_row(row) for row in rows]

    @staticmethod
    def _review_row(row: sqlite3.Row) -> dict:
        result = dict(row)
        for column, key in (("action_json", "action"), ("context_json", "context")):
            try:
                result[key] = json.loads(result.pop(column))
            except (TypeError, json.JSONDecodeError):
                result[key] = None
        return result

    def claim_matching_approval(
        self, session_id: str, action: Any, context: Any, policy_version: str
    ) -> str | None:
        """Atomically claim one exact, unexpired approval for a rechecked retry."""
        now = time.time()
        row = self.conn.execute(
            "SELECT review_id FROM reviews WHERE session_id = ? AND status = 'approved'"
            " AND dispatch_state = 'none' AND expires_at > ? AND action_digest = ?"
            " AND context_digest = ? AND policy_version = ? ORDER BY created_at LIMIT 1",
            (session_id, now, digest(action), digest(context), policy_version),
        ).fetchone()
        if row is None:
            return None
        review_id = row["review_id"]
        with self.conn:
            cur = self.conn.execute(
                "UPDATE reviews SET dispatch_state = 'attempted', claimed_at = ?"
                " WHERE review_id = ? AND status = 'approved' AND dispatch_state = 'none'"
                " AND expires_at > ?",
                (now, review_id, now),
            )
        return review_id if cur.rowcount == 1 else None

    def expire_stale(self, now: float | None = None) -> int:
        """Flip pending rows past expires_at to 'expired'; return count."""
        if now is None:
            now = time.time()
        with self.conn:
            cur = self.conn.execute(
                "UPDATE reviews SET status = 'expired'"
                " WHERE status = 'pending' AND expires_at <= ?",
                (now,),
            )
        return cur.rowcount

    def reassess_required(
        self,
        review_id: str,
        current_action: Any,
        current_context: Any,
        current_policy_version: str,
    ) -> bool:
        """True when action/context digests or policy version differ.

        Approved ambiguous cases are rechecked this way: changed context
        invalidates the prior approval. A missing review is True
        (fail closed — there is no prior approval to trust).
        """
        row = self.conn.execute(
            "SELECT action_digest, context_digest, policy_version"
            " FROM reviews WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        if row is None:
            return True
        return (
            digest(current_action) != row["action_digest"]
            or digest(current_context) != row["context_digest"]
            or current_policy_version != row["policy_version"]
        )

    # --- reviews: operator resolution (OUT-OF-BAND) ----------------------

    def resolve_review(
        self,
        review_id: str,
        decision: str,
        operator_token: str,
        note: str = "",
        now: float | None = None,
    ) -> dict:
        """Operator-only resolution. Requires the out-of-band token.

        Rules: pending -> approved/denied freely; expired -> denied only
        with a note (never approved — re-open via open_review); already
        resolved rows raise. The caller's token is compared to the
        PEA_OPERATOR_TOKEN env secret in constant time; the secret is
        never persisted.
        """
        if now is None:
            now = time.time()
        expected = os.environ.get(_TOKEN_ENV, "")
        if not expected:
            raise OperatorBoundaryError(
                "operator token not configured;"
                " agent processes cannot resolve reviews"
            )
        if not isinstance(operator_token, str) or not hmac.compare_digest(
            operator_token, expected
        ):
            raise OperatorBoundaryError("invalid operator token")
        if decision not in ("approved", "denied"):
            raise ValueError(f"invalid decision: {decision!r}")

        # Expire stale authorization before resolving; a caller's timer
        # cannot extend it.
        with self.conn:
            self.conn.execute(
                "UPDATE reviews SET status = 'expired'"
                " WHERE review_id = ? AND status IN ('pending','approved')"
                " AND expires_at <= ?",
                (review_id, now),
            )
            row = self.conn.execute(
                "SELECT status FROM reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"review not found: {review_id}")
        status = row["status"]
        if status in ("approved", "denied"):
            raise ValueError(f"review already resolved as {status}")
        if status == "expired":
            if decision != "denied":
                raise ValueError(
                    "cannot approve an expired review;"
                    " re-open via open_review"
                )
            if not note:
                raise ValueError(
                    "resolving an expired review to denied requires a note"
                )

        with self.conn:
            cur = self.conn.execute(
                "UPDATE reviews SET status = ?, resolved_at = ?,"
                " resolved_by = 'operator', resolution_note = ?"
                " WHERE review_id = ? AND status = ?"
                " AND (status != 'pending' OR expires_at > ?)",
                (decision, now, note, review_id, status, now),
            )
        if cur.rowcount != 1:
            raise ValueError("review expired or changed while resolving")
        return self.get_review(review_id)  # type: ignore[return-value]

    # --- dispatch (release path; at-most-once) ----------------------------

    def claim_dispatch(
        self,
        review_id: str,
        current_action: Any,
        current_context: Any,
        current_policy_version: str,
    ) -> bool:
        """Atomically claim dispatch only for the reviewed action and context.

        True exactly once per review. No auto-retry after a crash — a
        stuck 'attempted' row is operator-visible via stuck_attempts only.
        A changed action, context, or policy version cannot use old approval;
        the caller must reassess and open a new review.
        """
        now = time.time()
        action_digest = digest(current_action)
        context_digest = digest(current_context)
        with self.conn:
            self.conn.execute(
                "UPDATE reviews SET status = 'expired'"
                " WHERE review_id = ? AND status = 'approved' AND expires_at <= ?",
                (review_id, now),
            )
            self.conn.execute(
                "UPDATE reviews SET status = 'expired'"
                " WHERE review_id = ? AND status = 'pending' AND expires_at <= ?",
                (review_id, now),
            )
            cur = self.conn.execute(
                "UPDATE reviews SET dispatch_state = 'attempted',"
                " claimed_at = ? WHERE review_id = ?"
                " AND status = 'approved' AND dispatch_state = 'none'"
                " AND expires_at > ? AND action_digest = ?"
                " AND context_digest = ? AND policy_version = ?",
                (
                    now,
                    review_id,
                    now,
                    action_digest,
                    context_digest,
                    current_policy_version,
                ),
            )
        return cur.rowcount == 1

    def mark_dispatched(self, review_id: str) -> bool:
        """Record successful dispatch ('attempted' -> 'dispatched')."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE reviews SET dispatch_state = 'dispatched'"
                " WHERE review_id = ? AND dispatch_state = 'attempted'",
                (review_id,),
            )
        return cur.rowcount == 1

    def stuck_attempts(self, now: float | None = None, older_than_s: float = 300.0) -> list:
        """Operator inspection only: attempts claimed but never dispatched.

        This list feeds operator decisions; nothing here auto-retries.
        """
        if now is None:
            now = time.time()
        rows = self.conn.execute(
            "SELECT review_id, session_id, claimed_at FROM reviews"
            " WHERE status = 'approved' AND dispatch_state = 'attempted'"
            " AND claimed_at IS NOT NULL AND claimed_at <= ?",
            (now - older_than_s,),
        ).fetchall()
        return [dict(r) for r in rows]
