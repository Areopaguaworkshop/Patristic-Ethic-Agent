import json

from patristic_ethics.operator import main
from patristic_ethics.runtime_store import RuntimeStore


def test_operator_cli_inspects_and_resolves_review(tmp_path, monkeypatch, capsys):
    db = tmp_path / "runtime.db"
    store = RuntimeStore(db)
    rid = store.open_review("s1", {"tool": "mail", "arguments": {"to": "x"}},
                            {"context_limited": True}, "policy-v1", reason="unclear intent")
    store.conn.close()

    assert main(["--db", str(db), "show", rid]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["action"]["tool"] == "mail"
    assert shown["reason"] == "unclear intent"

    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "private")
    assert main(["--db", str(db), "resolve", rid, "approved", "--note", "reviewed"]) == 0
    resolved = json.loads(capsys.readouterr().out)
    assert resolved["status"] == "approved"
    assert resolved["resolution_note"] == "reviewed"


def test_operator_cli_cannot_resolve_without_configured_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PEA_OPERATOR_TOKEN", raising=False)
    store = RuntimeStore(tmp_path / "runtime.db")
    rid = store.open_review("s1", {}, {}, "policy-v1")
    store.conn.close()
    assert main(["--db", str(tmp_path / "runtime.db"), "resolve", rid,
                 "approved", "--note", "reviewed"]) == 2
    assert "operator token not configured" in capsys.readouterr().err
