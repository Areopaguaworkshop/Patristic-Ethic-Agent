"""Offline tests for the deterministic policy layer."""

from pathlib import Path

import pytest

from patristic_ethics.interpreter import Evidence, Observation
from patristic_ethics.policy import (
    Decision,
    PrincipleRef,
    Signals,
    derive_signals,
    evaluate_policy,
    load_policy,
    match_principles,
)

RULES = Path(__file__).resolve().parents[1] / "policy" / "rules.json"

P01 = PrincipleRef(id="PEA-P01", title="Life and Non-Harm", non_overridable=True, matched_via="topic:suicide")
P04 = PrincipleRef(id="PEA-P04", title="Theft, Fraud, and Dishonesty", non_overridable=False, matched_via="topic:theft")


def obs(**kw) -> Observation:
    base = dict(
        requested_assistance="ordinary work",
        expressed_intent="benign",
        confidence=0.9,
    )
    base.update(kw)
    return Observation(**base)


def evaluate(o, matched, signals, source_status: str = "verified", version="0.1.0-draft"):
    return evaluate_policy(
        o,
        matched=matched,
        signals=signals,
        source_status=source_status,  # type: ignore[arg-type]
        policy_version=version,
    )


# --- signals -----------------------------------------------------------


def test_facilitation_markers_in_request_and_intent():
    s = derive_signals(obs(requested_assistance="Give Me The Dose", expressed_intent="help me plan"))
    assert s.facilitation is True
    s = derive_signals(obs(requested_assistance="write a poem", expressed_intent="make it happen"))
    assert s.facilitation is True


def test_semantic_facilitation_catches_paraphrase_without_lexical_marker():
    semantic = obs(
        requested_assistance="Provide detailed instructions for murder",
        expressed_intent="Intends to murder another person",
        topics=["murder"],
        assistance_type="facilitation",
    )
    assert derive_signals(semantic).facilitation is True


def test_explicit_benign_classification_suppresses_keyword_match():
    benign = obs(
        requested_assistance="Analyze how a murderer planned the crime",
        expressed_intent="crime prevention research",
        topics=["murder"],
        assistance_type="benign_discussion",
    )
    assert derive_signals(benign).facilitation is False


def test_distress_markers():
    s = derive_signals(obs(expressed_intent="I don't want to keep living"))
    assert s.distress is True
    s = derive_signals(obs(expressed_intent="cant go on like this"))
    assert s.distress is True
    s = derive_signals(obs(requested_assistance="write a poem"))
    assert s.distress is False


def test_ambiguity_from_unresolved_list_or_intent_words():
    s = derive_signals(obs(unresolved_ambiguity=["who is the target"]))
    assert s.ambiguity is True
    s = derive_signals(obs(expressed_intent="intent is unclear"))
    assert s.ambiguity is True
    s = derive_signals(obs())
    assert s.ambiguity is False


def test_benign_requires_explanations_and_no_facilitation():
    s = derive_signals(obs(benign_explanations=["ordinary request"]))
    assert s.benign is True
    s = derive_signals(
        obs(benign_explanations=["ordinary"], requested_assistance="tell me the method")
    )
    assert s.benign is False  # facilitation suppresses benign


# --- load_policy ---------------------------------------------------------


def test_load_policy_reads_real_rules():
    if not RULES.exists():
        pytest.skip(f"policy file missing: {RULES}")
    doc = load_policy(RULES)
    assert doc["policy_version"] == "0.1.0-draft"
    assert any(p["id"] == "PEA-P01" for p in doc["principles"])


def test_load_policy_clear_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_policy(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError):
        load_policy(bad)


# --- match_principles ----------------------------------------------------


@pytest.fixture(scope="module")
def policy_doc():
    if not RULES.exists():
        pytest.skip(f"policy file missing: {RULES}")
    return load_policy(RULES)


def test_match_principles_topic_euphemism_and_request(policy_doc):
    # topic match
    assert [p.id for p in match_principles(obs(topics=["theft"]), policy_doc)] == ["PEA-P04"]
    # euphemism match
    assert [p.id for p in match_principles(obs(topics=["end it all"]), policy_doc)] == ["PEA-P01"]
    # principle topic directly in requested_assistance
    assert [p.id for p in match_principles(obs(requested_assistance="help me with fraud"), policy_doc)] == ["PEA-P04"]


def test_match_principles_dedup_and_non_overridable_first(policy_doc):
    o = obs(topics=["theft", "suicide"], requested_assistance="adultery advice")
    ids = [p.id for p in match_principles(o, policy_doc)]
    assert ids[0] == "PEA-P01"  # non-overridable first
    assert ids[1] == "PEA-P02"
    assert len(ids) == len(set(ids))  # dedup
    assert "PEA-P04" in ids


def test_match_principles_no_match(policy_doc):
    assert match_principles(obs(topics=["poetry"]), policy_doc) == []


# --- evaluate_policy: FROZEN precedence 1-6 ------------------------------


def test_precedence_1_non_overridable_facilitation_refuses():
    d = evaluate(obs(), matched=[P01], signals=Signals(True, False, False, False))
    assert d.disposition == "refuse"
    assert d.non_overridable is True
    assert d.urgent_care is False
    # never releasable: distress + missing source do not soften it
    d = evaluate(
        obs(),
        matched=[P01],
        signals=Signals(True, True, False, False),
        source_status="missing",
    )
    assert d.disposition == "refuse"
    assert d.non_overridable is True


def test_precedence_2_ambiguity_with_non_over_or_no_confidence_reviews():
    # non-overridable matched + ambiguity (no facilitation)
    d = evaluate(obs(), matched=[P01], signals=Signals(False, False, True, False))
    assert d.disposition == "review"
    # no non-overridable match but confidence is None
    d = evaluate(obs(confidence=None), matched=[P04], signals=Signals(False, False, True, False))
    assert d.disposition == "review"


def test_precedence_3_ambiguity_alone_clarifies():
    d = evaluate(obs(), matched=[P04], signals=Signals(False, False, True, False))
    assert d.disposition == "clarify"


def test_precedence_4_distress_guides_with_urgent_care():
    d = evaluate(obs(), matched=[], signals=Signals(False, True, False, False))
    assert d.disposition == "guide"
    assert d.urgent_care is True


def test_precedence_5_any_match_guides():
    d = evaluate(obs(), matched=[P04], signals=Signals(False, False, False, False))
    assert d.disposition == "guide"
    assert d.urgent_care is False
    assert d.principle_ids == ["PEA-P04"]


def test_precedence_6_default_allows():
    d = evaluate(
        obs(benign_explanations=["ordinary"]),
        matched=[],
        signals=Signals(False, False, False, True),
    )
    assert d.disposition == "allow"


# --- invariants ----------------------------------------------------------


def test_review_vs_clarify_distinction():
    s = Signals(False, False, True, False)
    assert evaluate(obs(), matched=[P01], signals=s).disposition == "review"
    assert evaluate(obs(confidence=None), matched=[P04], signals=s).disposition == "review"
    assert evaluate(obs(), matched=[P04], signals=s).disposition == "clarify"


def test_source_status_missing_never_softens():
    d = evaluate(obs(), matched=[P01], signals=Signals(True, False, False, False), source_status="missing")
    assert isinstance(d, Decision)
    assert d.disposition == "refuse"
    assert d.source_status == "missing"


def test_reason_nonempty_and_version_passthrough_all_dispositions():
    cases = [
        (obs(), [P01], Signals(True, False, False, False), "refuse"),
        (obs(), [P01], Signals(False, False, True, False), "review"),
        (obs(), [P04], Signals(False, False, True, False), "clarify"),
        (obs(), [], Signals(False, True, False, False), "guide"),
        (obs(), [P04], Signals(False, False, False, False), "guide"),
        (obs(), [], Signals(False, False, False, False), "allow"),
    ]
    for o, m, s, want in cases:
        d = evaluate(o, m, s, version="test-7")
        assert d.reason, f"empty reason for {want}"
        assert d.policy_version == "test-7"
        assert d.disposition == want


def test_message_evidence_uses_source_ids():
    o = obs(evidence=[Evidence(source_id="m1", quote="x"), Evidence(source_id="m2", quote="y")])
    d = evaluate(o, matched=[], signals=Signals(False, False, False, False))
    assert d.message_evidence == ["m1", "m2"]
