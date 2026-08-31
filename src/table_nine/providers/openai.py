from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from table_nine.providers.contracts import (
    BeatSuggestionOutput,
    BeatSuggestionRequest,
    HingeSuggestionOutput,
    HingeSuggestionRequest,
    ProviderConfigurationError,
    ProviderRequestError,
    StructuredResponseError,
)
from table_nine.providers.prompts import (
    beat_draft_messages,
    beat_revision_messages,
    hinge_messages,
)


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, model: str, *, client: Any | None = None) -> None:
        self.model_name = model.strip()
        if not self.model_name:
            raise ProviderConfigurationError("Set a model name before using the OpenAI provider.")

        if client is not None:
            self._client = client
            return
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "Install the project AI dependency before using the OpenAI provider."
            ) from exc
        self._client = OpenAI()

    @staticmethod
    def _refusal_text(response: Any) -> str | None:
        for output_item in getattr(response, "output", []):
            for content_item in getattr(output_item, "content", []):
                if getattr(content_item, "type", None) == "refusal":
                    return getattr(content_item, "refusal", "Request refused")
        return None

    def _parse_structured(
        self,
        messages: list[dict[str, str]],
        response_type: type[ResponseModel],
    ) -> ResponseModel:
        validation_error: Exception | None = None
        request_messages = list(messages)
        for attempt in range(2):
            try:
                response = self._client.responses.parse(
                    model=self.model_name,
                    input=request_messages,
                    text_format=response_type,
                )
            except ValidationError as exc:
                validation_error = exc
            except Exception as exc:
                raise ProviderRequestError(f"OpenAI request failed: {exc}") from exc
            else:
                refusal = self._refusal_text(response)
                if refusal:
                    raise ProviderRequestError(f"OpenAI refused the request: {refusal}")
                try:
                    parsed = getattr(response, "output_parsed", None)
                    if parsed is None:
                        raise ValueError("response did not contain parsed structured output")
                    return response_type.model_validate(parsed)
                except (ValidationError, ValueError) as exc:
                    validation_error = exc

            if attempt == 0:
                request_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous response did not match the required schema. Return a "
                            "complete corrected response using only the required structure."
                        ),
                    }
                )

        raise StructuredResponseError(
            f"OpenAI returned invalid structured output after recovery: {validation_error}"
        )

    def suggest_hinges(self, request: HingeSuggestionRequest) -> HingeSuggestionOutput:
        return self._parse_structured(hinge_messages(request), HingeSuggestionOutput)

    def draft_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput:
        return self._parse_structured(beat_draft_messages(request), BeatSuggestionOutput)

    def revise_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput:
        return self._parse_structured(beat_revision_messages(request), BeatSuggestionOutput)
