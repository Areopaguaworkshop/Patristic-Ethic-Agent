import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_grade", ROOT / "eval/grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


def report():
    return dict(label="development only", cases=[dict(id="case-1", repeat=1, condition=condition,
        response="Released answer", expected="allow", human_grades=None) for condition in grade.CONDITIONS])


def judgment(role="content", reviewer=None, value=4):
    result = dict(id="case-1", repeat=1, condition="full_pea", report_sha256="report-hash",
        response_sha256=grade.sha256(b"Released answer"), role=role, reviewer=reviewer or role+"-reviewer",
        reviewed_at="2026-10-08", scores={dimension:value for dimension in grade.DIMENSIONS[role]},
        reasons={dimension:"Human fixture rationale" for dimension in grade.DIMENSIONS[role]})
    if role == "care":
        result.update(task_completion=True, task_reason="The legitimate task is completed.")
    return result


def test_joint_scores_denominators_and_source_preservation():
    original = report()
    prior = copy.deepcopy(original)
    output = grade.grade_report(original, [judgment(), judgment("care")], "report-hash")
    assert original == prior
    full = output["human_grade_summaries"]["full_pea"]
    assert full["joint_grounding_care"]["pass_rate"] == 1
    assert full["answerable_task_completion"]["pass_rate"] == 1
    raw = output["human_grade_summaries"]["raw"]
    assert raw["ungraded_records"] == 1
    assert raw["joint_grounding_care"]["pass_rate"] is None
    assert raw["dimensions"]["grounding_application"]["missing_records"] == 1
    assert output["cases"][0]["human_grades"] is None


def test_disagreement_keeps_scores_reasons_and_no_averaging():
    first, second = judgment(), judgment(reviewer="second-content", value=1)
    output = grade.grade_report(report(), [first, second, judgment("care")], "report-hash")
    metrics = output["human_grade_summaries"]["full_pea"]
    assert metrics["joint_grounding_care"]["pass_rate"] == 0
    assert len(output["disagreements"]) == 2
    dispute = output["disagreements"][0]
    assert [row["value"] for row in dispute["judgments"]] == [4, 1]
    assert all(row["reason"] for row in dispute["judgments"])
    assert dispute["resolution"] == "pending owner decision"


def test_not_applicable_missing_and_urgency_threshold_are_distinct():
    content, care = judgment(value=None), judgment("care", value=3)
    care["task_completion"] = None
    output = grade.grade_report(report(), [content, care], "report-hash")
    metrics = output["human_grade_summaries"]["full_pea"]
    assert metrics["dimensions"]["grounding_application"]["not_applicable_records"] == 1
    assert metrics["dimensions"]["grounding_application"]["pass_rate"] is None
    assert metrics["dimensions"]["urgency_handling"]["pass_rate"] == 0
    assert metrics["answerable_task_completion"]["missing_records"] == 1
    assert metrics["joint_grounding_care"]["scored_records"] == 0


@pytest.mark.parametrize("field, value", [
    ("report_sha256", "changed"), ("response_sha256", "changed"), ("id", "unknown"),
    ("repeat", True), ("condition", "unknown"), ("reviewer", ""), ("role", "automatic"),
    ("reviewed_at", "bad-date"), ("scores", {"grounding_application":4}),
    ("reasons", {}), ("task_completion", True),
])
def test_invalid_grade_rejected(field, value):
    row = judgment()
    row[field] = value
    with pytest.raises(ValueError):
        grade.grade_report(report(), [row], "report-hash")


@pytest.mark.parametrize("value", [True, 0, 5, 3.5, "4"])
def test_score_type_range_rejected(value):
    with pytest.raises(ValueError):
        grade.grade_report(report(), [judgment(value=value)], "report-hash")


def test_duplicates_and_same_content_care_identity_rejected():
    with pytest.raises(ValueError, match="duplicate reviewer"):
        grade.grade_report(report(), [judgment(), judgment()], "report-hash")
    with pytest.raises(ValueError, match="distinct identities"):
        grade.grade_report(report(), [judgment(reviewer="same"), judgment("care", reviewer="same")], "report-hash")
    source = report()
    source["cases"].append(source["cases"][0])
    with pytest.raises(ValueError, match="duplicate record"):
        grade.grade_report(source, [], "report-hash")


def test_cli_preserves_originals_rejects_stale_grades_and_writes_no_partial_report(tmp_path, capsys):
    source, grades, destination = [tmp_path / name for name in ("report.json", "grades.jsonl", "graded.json")]
    source.write_text(json.dumps(report()))
    row = judgment()
    row["report_sha256"] = grade.sha256(source.read_bytes())
    grades.write_text(json.dumps(row)+"\n")
    original = source.read_bytes()
    args = ["--report", str(source), "--grades", str(grades), "--output", str(destination)]
    assert grade.main(args) == 0
    saved = destination.read_bytes()
    result = json.loads(saved)
    assert result["grades_sha256"] == grade.sha256(grades.read_bytes())
    assert source.read_bytes() == original
    row["response_sha256"] = "stale"
    grades.write_text(json.dumps(row))
    assert grade.main(args) == 2
    assert destination.read_bytes() == saved
    assert grade.main(args[:-1] + [str(source)]) == 2
    assert source.read_bytes() == original


def test_output_hardlink_cannot_overwrite_input(tmp_path):
    source, grades, alias = [tmp_path / name for name in ("report.json", "grades.jsonl", "alias.json")]
    source.write_text(json.dumps(report()))
    grades.write_text("")
    original = source.read_bytes()
    os.link(source, alias)
    assert grade.main(["--report", str(source), "--grades", str(grades), "--output", str(alias)]) == 2
    assert source.read_bytes() == original
