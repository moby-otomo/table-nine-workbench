from types import SimpleNamespace

import pytest

from table_nine.providers.contracts import (
    EpisodeContext,
    HingeSuggestionRequest,
    StructuredResponseError,
)
from table_nine.providers.openai import OpenAIProvider


VALID_HINGES = {
    "options": [
        {
            "title": f"Candidate {index}",
            "content": f"Question {index}?",
            "causal_chain": ["observation", "inference", "problem"],
        }
        for index in range(1, 4)
    ]
}


def _request() -> HingeSuggestionRequest:
    return HingeSuggestionRequest(
        context=EpisodeContext(
            episode_id="example-episode",
            working_title="Example",
            featured_uncle="Example Uncle",
            observed_behavior="Observed behavior",
            central_artifact="Artifact",
            human_stakes="Stakes",
            ai_era_problem="Problem",
            opening_question="Opening question?",
            selected_hinge="",
            case_evidence=[],
            cast={"uncle_one": "One", "uncle_two": "Two", "archivist_robot": "Robot"},
        )
    )


class FakeResponses:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=next(self.outputs), output=[])


def test_openai_adapter_recovers_once_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    responses = FakeResponses([{"options": []}, VALID_HINGES])
    provider = OpenAIProvider("configured-at-runtime", client=SimpleNamespace(responses=responses))

    output = provider.suggest_hinges(_request())

    assert len(output.options) == 3
    assert len(responses.calls) == 2
    assert responses.calls[0]["model"] == "configured-at-runtime"
    assert responses.calls[0]["text_format"].__name__ == "HingeSuggestionOutput"
    assert len(responses.calls[1]["input"]) == 3


def test_openai_adapter_reports_repeated_invalid_structure():
    responses = FakeResponses([{"options": []}, {"options": []}])
    provider = OpenAIProvider("configured-at-runtime", client=SimpleNamespace(responses=responses))

    with pytest.raises(StructuredResponseError, match="after recovery"):
        provider.suggest_hinges(_request())
