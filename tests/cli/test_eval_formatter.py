from __future__ import annotations

from app.cli.support.eval_formatter import format_opensre_llm_eval


def test_format_opensre_llm_eval_skipped() -> None:
    text = format_opensre_llm_eval({"skipped": True, "reason": "no rubric"})
    assert "skipped" in text.lower()
    assert "no rubric" in text


def test_format_opensre_llm_eval_full_payload() -> None:
    text = format_opensre_llm_eval(
        {
            "overall_pass": True,
            "score_0_100": 92,
            "summary": "Root cause matches rubric.",
            "rubric_items": [
                {"id": "rca", "satisfied": True, "explanation": "matches"},
                {"name": "evidence", "passed": False},
            ],
        }
    )
    assert "92/100" in text
    assert "overall_pass: True" in text
    assert "rca: pass" in text
    assert "evidence: fail" in text
    assert "Root cause matches rubric." in text
