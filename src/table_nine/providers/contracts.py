from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EpisodeContext(ProviderModel):
    episode_id: str
    working_title: str
    featured_uncle: str
    observed_behavior: str
    central_artifact: str
    human_stakes: str
    ai_era_problem: str
    opening_question: str
    selected_hinge: str
    case_evidence: list[str]
    cast: dict[str, str]


class BeatContext(ProviderModel):
    beat_id: str
    title: str
    purpose: str
    leading_speaker: str
    must_land: list[str]
    temperature: str
    target_seconds: int
    target_words: int
    artifact_or_visual: str
    current_script: str


class HingeSuggestionRequest(ProviderModel):
    context: EpisodeContext
    instruction: str = ""


class BeatSuggestionRequest(ProviderModel):
    context: EpisodeContext
    beat: BeatContext
    instruction: str = ""


class HingeOptionOutput(ProviderModel):
    title: str
    content: str
    causal_chain: list[str] = Field(min_length=2)


class HingeSuggestionOutput(ProviderModel):
    options: list[HingeOptionOutput] = Field(min_length=3, max_length=3)


class BeatOptionOutput(ProviderModel):
    title: str
    script: str
    rationale: str


class BeatSuggestionOutput(ProviderModel):
    options: list[BeatOptionOutput] = Field(min_length=2, max_length=2)


class ProviderError(RuntimeError):
    """Base error for assistance provider failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is missing required local configuration."""


class ProviderRequestError(ProviderError):
    """Raised when a provider request cannot be completed."""


class StructuredResponseError(ProviderError):
    """Raised when a response cannot be validated after one recovery attempt."""


class ModelProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def suggest_hinges(self, request: HingeSuggestionRequest) -> HingeSuggestionOutput: ...

    def draft_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput: ...

    def revise_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput: ...
