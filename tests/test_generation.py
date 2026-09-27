import json
import pytest
from doculens.config import Settings
from doculens.generation import answer, validate_generation


@pytest.fixture
def results():
    return [
        {
            "id": "chunk",
            "title": "API",
            "version": "1",
            "section": "Rate limits",
            "text": "API rate limits allow 120 requests each minute. HTTP 429 requires waiting for Retry-After.",
            "semantic_score": 0.8,
        }
    ]


def test_evidence_is_verbatim_with_resolvable_citation(tmp_path, results):
    result = answer("What are API rate limits?", results, Settings(tmp_path))
    assert result["mode"] == "evidence" and not result["abstained"]
    for statement in result["statements"]:
        assert statement["text"] in results[0]["text"]
        assert statement["citations"] == ["S1"]


def test_no_evidence_abstains(tmp_path):
    result = answer("Who is the CEO?", [], Settings(tmp_path))
    assert result["abstained"] and result["statements"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"abstained": False, "statements": [{"text": "A claim", "citations": ["S99"]}]},
        {"abstained": False, "statements": [{"text": "A claim", "citations": []}]},
        {"abstained": False, "statements": []},
        {"statements": []},
    ],
)
def test_invalid_generated_answers_rejected(body):
    with pytest.raises(ValueError):
        validate_generation(json.dumps(body), {"S1"})


def test_provider_failure_falls_back_explicitly(tmp_path, results, monkeypatch):
    def fail(*args):
        raise RuntimeError("secret-error-must-not-appear")

    monkeypatch.setattr("doculens.generation.call_provider", fail)
    settings = Settings(tmp_path, provider="openai-compatible", llm_model="example")
    response = answer("API rate limits", results, settings, True)
    assert response["mode"] == "evidence"
    assert response["warning"] and "secret-error" not in str(response)


def test_generated_source_ids_checked_and_mode_labeled(tmp_path, results, monkeypatch):
    monkeypatch.setattr(
        "doculens.generation.call_provider",
        lambda *a: (
            json.dumps(
                {
                    "abstained": False,
                    "statements": [{"text": "The API allows 120 requests per minute.", "citations": ["S1"]}],
                }
            ),
            {"total_tokens": 40},
        ),
    )
    settings = Settings(tmp_path, provider="openai-compatible", llm_model="example")
    response = answer("API rate limits", results, settings, True)
    assert response["mode"] == "generated" and response["usage"]["total_tokens"] == 40


def test_no_external_call_without_user_opt_in(tmp_path, results, monkeypatch):
    def fail(*args):
        raise AssertionError("Provider must not be called")

    monkeypatch.setattr("doculens.generation.call_provider", fail)
    settings = Settings(tmp_path, provider="bedrock", llm_model="example")
    assert answer("API rate limits", results, settings, False)["mode"] == "evidence"


def test_cost_estimate_requires_actual_usage_and_explicit_rates(tmp_path):
    from doculens.generation import estimate_cost

    settings = Settings(tmp_path, input_usd_per_million=2, output_usd_per_million=6)
    assert estimate_cost({"prompt_tokens": 1000, "completion_tokens": 500}, settings) == pytest.approx(0.005)
    assert estimate_cost({"inputTokens": 1000, "outputTokens": 500}, settings) == pytest.approx(0.005)
    assert estimate_cost({"total_tokens": 1500}, settings) is None
    assert estimate_cost({"prompt_tokens": 1000, "completion_tokens": 500}, Settings(tmp_path)) is None
