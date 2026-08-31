from __future__ import annotations

from table_nine.providers.contracts import (
    BeatOptionOutput,
    BeatSuggestionOutput,
    BeatSuggestionRequest,
    HingeOptionOutput,
    HingeSuggestionOutput,
    HingeSuggestionRequest,
)


class DeterministicMockProvider:
    provider_name = "mock"
    model_name = "deterministic-stage-d"

    def suggest_hinges(self, request: HingeSuggestionRequest) -> HingeSuggestionOutput:
        context = request.context
        artifact = (context.central_artifact or "the central artifact").strip().rstrip(".")
        artifact_mid_sentence = artifact[:1].lower() + artifact[1:]
        behaviour = context.observed_behavior or "the observed behaviour"
        problem = context.ai_era_problem or "the AI-era problem"
        return HingeSuggestionOutput(
            options=[
                HingeOptionOutput(
                    title="Signal without context",
                    content=(
                        f"When {artifact_mid_sentence} outlives its context, are people responding to "
                        "evidence or completing a story around it?"
                    ),
                    causal_chain=[behaviour, "context falls away", "inference becomes instruction", problem],
                ),
                HingeOptionOutput(
                    title="Cheap authority",
                    content=(
                        f"Does {artifact_mid_sentence} reveal how little material authority needs when people "
                        "are already prepared to obey a plausible signal?"
                    ),
                    causal_chain=[artifact, "plausible signal", "voluntary compliance", problem],
                ),
                HingeOptionOutput(
                    title="Coordination by projection",
                    content=(
                        "Can a shared misreading still coordinate people usefully, and what changes "
                        "when machines produce those misreadings at scale?"
                    ),
                    causal_chain=[behaviour, "shared projection", "temporary coordination", problem],
                ),
            ]
        )

    def draft_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput:
        beat = request.beat
        artifact = (request.context.central_artifact or "case file").strip().rstrip(".")
        return BeatSuggestionOutput(
            options=[
                BeatOptionOutput(
                    title="Conservative pass",
                    script=(
                        f"[hold on {artifact} 1.5]\n"
                        "UNCLE_ONE: We should begin with what is actually here.\n"
                        f"ARCHIVIST_ROBOT: Selected beat: {beat.title}. Evidence remains provisional.\n"
                        "[pause 1]\n"
                        "UNCLE_TWO: Good. Provisional things are less likely to invoice us."
                    ),
                    rationale="Starts from visible evidence and gives the robot a bounded procedural move.",
                ),
                BeatOptionOutput(
                    title="Stranger pass",
                    script=(
                        f"[hold on {artifact} 2]\n"
                        "UNCLE_TWO: It has the confidence of an object that has never been questioned.\n"
                        "[silence 1.5]\n"
                        "ARCHIVIST_ROBOT: Confidence is not currently admissible as provenance.\n"
                        "UNCLE_ONE: That has not stopped anyone else."
                    ),
                    rationale="Keeps the inquiry legible while opening with a more oblique comic claim.",
                ),
            ]
        )

    def revise_beat(self, request: BeatSuggestionRequest) -> BeatSuggestionOutput:
        beat = request.beat
        instruction = request.instruction.strip() or "tighten the exchange"
        return BeatSuggestionOutput(
            options=[
                BeatOptionOutput(
                    title="Conservative revision",
                    script=(
                        "UNCLE_ONE: Let us keep the claim smaller than the evidence.\n"
                        "ARCHIVIST_ROBOT: A welcome departure from local precedent.\n"
                        "[pause 1]\n"
                        f"UNCLE_TWO: Fine. For {beat.title.lower()}, smaller first."
                    ),
                    rationale=f"Applies the instruction conservatively: {instruction}.",
                ),
                BeatOptionOutput(
                    title="Stranger revision",
                    script=(
                        "[silence 1.5]\n"
                        "UNCLE_TWO: The evidence appears to be waiting for us to become less certain.\n"
                        "ARCHIVIST_ROBOT: I can schedule that.\n"
                        "UNCLE_ONE: Put us down for immediately."
                    ),
                    rationale=f"Uses a sharper turn while retaining the beat purpose: {instruction}.",
                ),
            ]
        )
