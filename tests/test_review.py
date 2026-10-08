"""Offline tests for the runtime review store: audit idempotence, review
lifecycle, the agent/operator boundary, dispatch at-most-once, reassessment.

Uses tmp_path dbs and monkeypatched env only; fully offline.
"""

import inspect
from concurrent.futures import ThreadPoolExecutor

import pytest

from patristic_ethics.runtime_store import (
    OperatorBoundaryError,
    ReviewNotAllowed,
    RuntimeStore,
    digest,
)

ACTION = {"tool": "shell", "argv": ["rm", "-rf", "/tmp/x"]}
CONTEXT = {"session": "s1", "recent": ["help me clean tmp files"]}
PV = "0.1.0-draft"


@pytest.fixture()
def store(tmp_path):
    return RuntimeStore(tmp_path / "runtime.db")


def open_pending(store, **kw):
    kw.setdefault("ttl_s", 3600.0)
    return store.open_review("s1", ACTION, CONTEXT, PV, **kw)


def resolve(store, rid, decision, token="tok123", note="", **kw):
    return store.resolve_review(rid, decision, token, note=note, **kw)


def claim(store, rid, action=ACTION, context=CONTEXT, policy_version=PV):
    return store.claim_dispatch(rid, action, context, policy_version)


# --- events: retry-safe audit ----------------------------------------------


def test_event_recorded_once_and_duplicate_returns_false(store):
    assert store.try_record_event("e1", "s1", "assess", "reply", "review", ["PEA-P01"], PV, "c1") is True
    assert store.try_record_event("e1", "s1", "assess", "reply", "review", ["PEA-P01"], PV, "c1") is False
    n = store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert n == 1


def test_store_uses_worker_local_sqlite_connection(store):
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            store.try_record_event,
            "thread-event", "s1", "pre_action", "refuse", "refuse",
        ).result()
    assert result is True
    assert store.conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_id='thread-event'"
    ).fetchone()[0] == 1


def test_event_retry_safe_across_store_instances(store, tmp_path):
    rid = store.try_record_event("e2", "s1", "assess", "reply", "allow", [], PV, "c1")
    # hook retry happens after a crash/restart: new store handle, same db
    other = RuntimeStore(tmp_path / "runtime.db")
    assert other.try_record_event("e2", "s1", "assess", "reply", "allow", [], PV, "c1") is False
    assert rid is True


def test_event_stores_latency_and_principles(store):
    store.try_record_event("e3", "s1", "assess", "reply", "refuse", ["PEA-P01"], PV, "c1", latency_ms=12.5)
    row = store.conn.execute("SELECT * FROM events WHERE event_id='e3'").fetchone()
    assert row["latency_ms"] == 12.5
    assert row["principle_ids_json"] == '["PEA-P01"]'


# --- open/get round-trip and digest canonicality ----------------------------


def test_open_and_get_review_roundtrip(store):
    rid = open_pending(store)
    row = store.get_review(rid)
    assert row["status"] == "pending"
    assert row["session_id"] == "s1"
    assert row["policy_version"] == PV
    assert row["action_digest"] == digest(ACTION)
    assert row["context_digest"] == digest(CONTEXT)
    assert row["expires_at"] > row["created_at"]
    assert row["dispatch_state"] == "none"
    assert row["resolved_by"] is None and row["resolution_note"] is None
    assert row["action"] == ACTION
    assert row["context"] == CONTEXT


def test_matching_pending_review_is_reused(store):
    first = open_pending(store)
    assert open_pending(store) == first
    assert len(store.list_reviews("pending")) == 1


def test_review_ttl_must_be_positive(store):
    with pytest.raises(ValueError, match="ttl_s must be positive"):
        open_pending(store, ttl_s=-1)


def test_digest_stable_across_key_order(store):
    a = {"b": 2, "a": {"y": 1, "x": 2}}
    b = {"a": {"x": 2, "y": 1}, "b": 2}
    assert digest(a) == digest(b)
    rid_a = store.open_review("s1", a, {}, PV)
    rid_b = store.open_review("s1", b, {}, PV)
    rows = [store.get_review(r) for r in (rid_a, rid_b)]
    assert rows[0]["action_digest"] == rows[1]["action_digest"]
    assert rows[0]["review_id"] == rows[1]["review_id"]


def test_get_review_missing_returns_none(store):
    assert store.get_review("nope") is None


# --- expiry ------------------------------------------------------------------


def test_expire_stale_flips_pending_to_expired(store):
    rid = open_pending(store, ttl_s=1.0)
    assert store.expire_stale(now=store.get_review(rid)["created_at"] + 0.5) == 0
    assert store.expire_stale(now=store.get_review(rid)["created_at"] + 2.0) == 1
    assert store.get_review(rid)["status"] == "expired"
    assert store.expire_stale(now=store.get_review(rid)["created_at"] + 3.0) == 0


def test_expired_review_cannot_be_approved(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store, ttl_s=1.0)
    store.expire_stale(now=store.get_review(rid)["created_at"] + 2.0)
    with pytest.raises(ValueError, match="expired"):
        resolve(store, rid, "approved")


def test_expired_to_denied_requires_note(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store, ttl_s=1.0)
    store.expire_stale(now=store.get_review(rid)["created_at"] + 2.0)
    with pytest.raises(ValueError, match="note"):
        resolve(store, rid, "denied")
    row = resolve(store, rid, "denied", note="expired without operator response")
    assert row["status"] == "denied"
    assert row["resolved_by"] == "operator"


def test_expiry_is_enforced_during_approval(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store, ttl_s=1.0)
    expiry = store.get_review(rid)["expires_at"]
    with pytest.raises(ValueError, match="expired"):
        resolve(store, rid, "approved", now=expiry + 1)
    assert store.get_review(rid)["status"] == "expired"
    assert claim(store, rid) is False


def test_approval_expires_before_dispatch(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store, ttl_s=10.0)
    expiry = store.get_review(rid)["expires_at"]
    resolve(store, rid, "approved", now=expiry - 1)
    monkeypatch.setattr("patristic_ethics.runtime_store.time.time", lambda: expiry + 1)
    assert claim(store, rid) is False


# --- non-overridable / refuse -------------------------------------------------


def test_non_overridable_cannot_open_review(store):
    with pytest.raises(ReviewNotAllowed):
        open_pending(store, non_overridable=True)


# --- agent surface ------------------------------------------------------------


def test_agent_surface_has_no_approve_and_no_approval_boolean(store):
    assert not hasattr(store, "approve")
    assert not hasattr(store, "deny")
    agent_facing = ("open_review", "get_review", "get_review_status",
                    "try_record_event", "claim_dispatch", "mark_dispatched",
                    "reassess_required", "expire_stale", "stuck_attempts")
    for name in agent_facing:
        fn = getattr(store, name)
        assert callable(fn), name
        for pname, param in inspect.signature(fn).parameters.items():
            # no parameter may carry an approval/override semantic
            assert "approv" not in pname.lower(), (name, pname)
            assert pname not in ("allow", "release", "override", "force"), (name, pname)
            assert param.annotation is not bool, (name, pname)


def test_agent_facing_methods_cannot_reach_approved_state(store):
    # only the token-gated resolver may SET approved; agent-facing methods
    # may gate on the status in a WHERE clause (claim_dispatch) but never
    # grant it. Docstrings are stripped: only executable code counts.
    import ast as _ast

    tree = _ast.parse(inspect.getsource(__import__("patristic_ethics.runtime_store", fromlist=["x"])))
    for node in tree.body:
        if not isinstance(node, (_ast.FunctionDef,)):
            continue
        body = node.body
        if (body and isinstance(body[0], _ast.Expr)
                and isinstance(body[0].value, _ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]  # drop docstring
        code = "\n".join(_ast.unparse(b) for b in body)
        if node.name == "resolve_review":
            assert "status = ?" in code
            continue
        for line in code.splitlines():
            if "approved" in line:
                # only legal use: literal inside a WHERE clause
                assert "WHERE" in line.upper(), (
                    f"{node.name} writes approved outside a gating WHERE: {line!r}"
                )
                assert line.upper().split("WHERE", 1)[0].find("approved") == -1, line


def test_get_review_status_limited_fields(store, monkeypatch):
    rid = open_pending(store)
    st = store.get_review_status(rid)
    assert set(st) == {"review_id", "status", "expires_at"}
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    resolve(store, rid, "approved", note="operator looked")
    st2 = store.get_review_status(rid)
    assert set(st2) == {"review_id", "status", "expires_at"}
    assert "resolved_by" not in st2 and "resolution_note" not in st2
    assert st2["status"] == "approved"


# --- operator boundary ---------------------------------------------------------


def test_resolve_without_env_token_raises(store, monkeypatch):
    monkeypatch.delenv("PEA_OPERATOR_TOKEN", raising=False)
    rid = open_pending(store)
    with pytest.raises(OperatorBoundaryError, match="not configured"):
        resolve(store, rid, "approved")


def test_resolve_wrong_token_raises(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    with pytest.raises(OperatorBoundaryError):
        resolve(store, rid, "approved", token="wrong")
    assert store.get_review(rid)["status"] == "pending"


def test_resolve_right_token_approves(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    row = resolve(store, rid, "approved", note="checked context")
    assert row["status"] == "approved"
    assert row["resolved_at"] is not None
    assert row["resolved_by"] == "operator"
    assert row["resolution_note"] == "checked context"


def test_resolved_review_cannot_resolve_again(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    resolve(store, rid, "denied", note="no")
    with pytest.raises(ValueError, match="already resolved"):
        resolve(store, rid, "approved")


# --- dispatch ------------------------------------------------------------------


def test_claim_dispatch_exactly_once(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    assert claim(store, rid) is False  # pending: not dispatchable
    resolve(store, rid, "approved")
    assert claim(store, rid) is True
    assert claim(store, rid) is False  # at-most-once
    assert store.mark_dispatched(rid) is True
    assert store.mark_dispatched(rid) is False


def test_dispatch_requires_original_action_context_and_policy(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    resolve(store, rid, "approved")

    assert claim(store, rid, action={**ACTION, "argv": ["different"]}) is False
    assert store.reassess_required(rid, {**ACTION, "argv": ["different"]}, CONTEXT, PV)
    assert claim(store, rid, context={**CONTEXT, "recent": ["changed"]}) is False
    assert store.reassess_required(rid, ACTION, {**CONTEXT, "recent": ["changed"]}, PV)
    assert claim(store, rid, policy_version="0.2.0") is False
    assert store.reassess_required(rid, ACTION, CONTEXT, "0.2.0")

    # The approval remains usable only for the exact reviewed values.
    assert claim(store, rid) is True


def test_matching_approved_retry_claims_once(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    resolve(store, rid, "approved")
    assert store.claim_matching_approval("s1", ACTION, CONTEXT, PV) == rid
    assert store.get_review(rid)["dispatch_state"] == "attempted"
    assert store.claim_matching_approval("s1", ACTION, CONTEXT, PV) is None
    assert store.claim_matching_approval("other", ACTION, CONTEXT, PV) is None
    assert store.claim_matching_approval("s1", ACTION, {"changed": True}, PV) is None


def test_stuck_attempt_not_auto_retried(store, monkeypatch):
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "tok123")
    rid = open_pending(store)
    resolve(store, rid, "approved")
    assert claim(store, rid) is True
    # crash after claim: nothing flips it back; second claim stays False
    assert claim(store, rid) is False
    stuck = store.stuck_attempts(older_than_s=0.0)
    assert [s["review_id"] for s in stuck] == [rid]


# --- reassessment ---------------------------------------------------------------


def test_reassess_required_flags_changes(store):
    rid = open_pending(store)
    assert store.reassess_required(rid, ACTION, CONTEXT, PV) is False
    assert store.reassess_required(rid, {"tool": "other"}, CONTEXT, PV) is True
    assert store.reassess_required(rid, ACTION, {"session": "s1", "recent": []}, PV) is True
    assert store.reassess_required(rid, ACTION, CONTEXT, "0.2.0") is True
    assert store.reassess_required("missing", ACTION, CONTEXT, PV) is True
