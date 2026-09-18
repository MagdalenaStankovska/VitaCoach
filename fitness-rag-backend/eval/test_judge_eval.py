"""Unit tests for judge_eval.py's defensive JSON parsing — pure function,
no app/model/Postgres dependency needed."""
from judge_eval import parse_judge_response


def test_parse_judge_response_valid_json():
    text = '{"faithfulness": 4, "answer_relevance": 5, "context_precision": 0.75, "rationale": "ok"}'
    result = parse_judge_response(text)
    assert result == {"faithfulness": 4, "answer_relevance": 5, "context_precision": 0.75, "rationale": "ok"}


def test_parse_judge_response_strips_markdown_fence():
    text = '```json\n{"faithfulness": 3, "answer_relevance": 3, "context_precision": 0.5}\n```'
    result = parse_judge_response(text)
    assert result["faithfulness"] == 3
    assert result["rationale"] == ""


def test_parse_judge_response_non_json_returns_none():
    assert parse_judge_response("this is not json at all") is None


def test_parse_judge_response_missing_keys_returns_none():
    assert parse_judge_response('{"faithfulness": 4}') is None


def test_parse_judge_response_empty_returns_none():
    assert parse_judge_response("") is None
    assert parse_judge_response(None) is None
