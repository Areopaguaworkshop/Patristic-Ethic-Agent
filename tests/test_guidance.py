"""Offline tests for guidance composition and the output self-check."""

from dataclasses import dataclass

from patristic_ethics.guidance import (
    Citation,
    OutputCheck,
    assess_output,
    compose_guidance,
    filter_verified,
    revise_once,
)

PEACEMAKERS = "Blessed are the peacemakers, for they shall be called sons of God."


@dataclass
class FakeDecision:
    disposition: str
    principle_ids: "list | None" = None
    reason: str = ""
    message_evidence: "list | None" = None
    source_status: str = "verified"
    urgent_care: bool = False
    non_overridable: bool = False
    policy_version: str = "test"

    def __post_init__(self):
        self.principle_ids = self.principle_ids or []
        self.message_evidence = self.message_evidence or []


@dataclass
class FakeUnit:
    id: str = "mt5.9"
    principle_ids: "list | None" = None
    author: str = "Augustine"
    work: str = "Sermon on the Mount"
    locus: str = "Mt 5:9"
    language: str = "en"
    source_url: str = "https://example.com/mt5"
    rights_status: str = "public-domain"
    review_status: str = "draft-unreviewed"
    text: "str | None" = PEACEMAKERS

    def __post_init__(self):
        self.principle_ids = self.principle_ids or []


DESCS = {"p6": "Sanctity of life"}


# --- compose_guidance: refuse ---


def test_refuse_mentions_principle_and_alternative():
    d = FakeDecision(disposition="refuse", principle_ids=["p6"])
    r = compose_guidance(d, passages=[], principle_descriptions=DESCS)
    assert "p6" in r.text and "Sanctity of life" in r.text
    assert "alternative" in r.text


def test_refuse_no_prohibited_markers_no_shame():
    d = FakeDecision(disposition="refuse", principle_ids=["p6"])
    r = compose_guidance(d, passages=[], principle_descriptions=DESCS)
    for m in ("dose", "method to", "step 1", "instructions", "how to make", "recipe", "untraceable"):
        assert m not in r.text.lower()
    for bad in ("sinner", "shame on"):
        assert bad not in r.text.lower()


# --- guide ---


def test_guide_urgent_care_mentions_human_support():
    d = FakeDecision(disposition="guide", principle_ids=["p6"], urgent_care=True)
    r = compose_guidance(d, passages=[], principle_descriptions=DESCS)
    low = r.text.lower()
    assert "crisis services" in low or "emergency" in low
    assert "trust" in low or "support" in low or "alone" in low


def test_guide_urgent_care_no_shaming():
    d = FakeDecision(disposition="guide", urgent_care=True)
    r = compose_guidance(d, passages=[])
    assert "sinner" not in r.text.lower() and "shame" not in r.text.lower()


def test_guide_plain_contains_virtue_direction():
    d = FakeDecision(disposition="guide", principle_ids=["p6"])
    r = compose_guidance(d, passages=[], principle_descriptions=DESCS)
    assert "Sanctity of life" in r.text


# --- clarify / review / allow ---


def test_clarify_one_question_and_withholding():
    d = FakeDecision(disposition="clarify")
    r = compose_guidance(d, passages=[])
    assert r.text.count("?") <= 2
    assert "hold off" in r.text.lower()


def test_review_mentions_human_assessment():
    d = FakeDecision(disposition="review")
    r = compose_guidance(d, passages=[])
    assert "qualified human" in r.text.lower()


def test_allow_short_no_religious_vocab():
    d = FakeDecision(disposition="allow")
    r = compose_guidance(d, passages=[])
    assert len(r.text) < 200
    assert "commandment" not in r.text.lower()
    assert "scripture" not in r.text.lower()


# --- citations ---


def test_null_text_passage_skipped_nonnull_included():
    d = FakeDecision(disposition="allow", source_status="verified")
    with_text = FakeUnit()
    null_text = FakeUnit(id="x", text=None)
    r = compose_guidance(d, passages=[with_text, null_text])
    assert len(r.citations) == 1
    assert r.citations[0].quote == PEACEMAKERS
    assert r.citations[0].unit_id == "mt5.9"
    assert r.citations[0].review_status == "draft-unreviewed"
    assert "draft material" in r.text


def test_filter_verified_drops_failing_quote():
    c_ok = Citation("mt5.9", "A", "W", None, "u", PEACEMAKERS, "en", "pd")
    c_bad = Citation("mt5.9", "A", "W", None, "u", "not in the text", "en", "pd")
    verify = lambda unit_id, quote: quote == PEACEMAKERS
    out = filter_verified([c_ok, c_bad], verify)
    assert out == [c_ok]


# --- missing sources ---


def test_missing_passages_limited_and_transparent():
    d = FakeDecision(disposition="refuse", principle_ids=["p6"], source_status="missing")
    r = compose_guidance(d, passages=[], principle_descriptions=DESCS)
    assert r.limited is True
    assert r.citations == []
    assert r.source_status == "missing"
    assert "insufficient evidence in this collection" in r.text
    assert "never said" not in r.text  # never claims the Fathers were silent


def test_decision_source_missing_overrides_verified_passages():
    d = FakeDecision(disposition="guide", source_status="missing")
    r = compose_guidance(d, passages=[FakeUnit()])
    assert r.limited is True


# --- assess_output ---


def test_assess_fabricated_quote_flagged():
    d = FakeDecision(disposition="allow")
    p = FakeUnit()
    check = assess_output('As taught by Augustine: "made up quote entirely"', d, [p])
    assert not check.ok and "unsupported_quote" in check.problems


def test_assess_exact_quote_ok():
    d = FakeDecision(disposition="allow")
    p = FakeUnit()
    check = assess_output(f'As taught by Augustine: "{PEACEMAKERS}"', d, [p])
    assert check.ok


def test_assess_prohibited_marker_on_refuse_flagged():
    d = FakeDecision(disposition="refuse")
    check = assess_output("Here is a recipe for it.", d, [])
    assert not check.ok and "prohibited_assistance" in check.problems


def test_assess_same_marker_on_allow_not_flagged():
    d = FakeDecision(disposition="allow")
    check = assess_output("Here is a recipe for pancakes.", d, [])
    assert check.ok


def test_assess_missing_citation_when_quote_no_passages():
    d = FakeDecision(disposition="allow")
    check = assess_output('Augustine wrote "some words here" long ago.', d, [])
    assert "missing_citation" in check.problems


def test_assess_does_not_treat_plain_quoted_text_as_patristic_citation():
    d = FakeDecision(disposition="allow")
    check = assess_output('The program prints "hello world".', d, [])
    assert check.ok


# --- revise_once ---


def test_revise_once_ok_check_not_called():
    calls = []

    def revise(text, problems):
        calls.append(1)
        return "revised"

    out, used = revise_once("orig", OutputCheck(ok=True, problems=[]), revise)
    assert out == "orig" and used is False and calls == []


def test_revise_once_failing_check_called_once():
    calls = []

    def revise(text, problems):
        calls.append(1)
        return "fixed text"

    out, used = revise_once(
        "orig", OutputCheck(ok=False, problems=["prohibited_assistance"]), revise
    )
    assert out == "fixed text" and used is True and len(calls) == 1


def test_revise_once_raising_returns_original():
    def revise(text, problems):
        raise RuntimeError("boom")

    out, used = revise_once(
        "orig", OutputCheck(ok=False, problems=["unsupported_quote"]), revise
    )
    assert out == "orig" and used is False
