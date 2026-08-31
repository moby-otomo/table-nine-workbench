from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from table_nine.domain.models import (
    ApprovalStatus,
    EpisodeDocument,
    HingeCandidate,
    MachineSuggestion,
    Provenance,
    SuggestionKind,
    SuggestionOption,
    SuggestionStatus,
)
from table_nine.providers.contracts import (
    BeatContext,
    BeatSuggestionRequest,
    EpisodeContext,
    HingeSuggestionRequest,
    ModelProvider,
)
from table_nine.services.editing import LockedContentError
from table_nine.services.script_codec import parse_script_text, render_script_text


class AssistanceError(ValueError):
    """Raised when a suggestion cannot be generated or applied safely."""


def _episode_context(document: EpisodeDocument) -> EpisodeContext:
    selected_hinge = document.selected_hinge()
    return EpisodeContext(
        episode_id=document.episode.id,
        working_title=document.episode.working_title,
        featured_uncle=document.episode.featured_uncle,
        observed_behavior=document.episode.observed_behavior.value,
        central_artifact=document.episode.central_artifact.value,
        human_stakes=document.episode.human_stakes.value,
        ai_era_problem=document.episode.ai_era_problem.value,
        opening_question=document.inquiry.opening_question.value,
        selected_hinge=selected_hinge.content.value if selected_hinge else "",
        case_evidence=[field.value for field in document.inquiry.case_evidence if field.value.strip()],
        cast={
            "uncle_one": document.cast.seated_uncle_1.display_name,
            "uncle_two": document.cast.seated_uncle_2.display_name,
            "archivist_robot": document.cast.archivist_robot.display_name,
        },
    )


def _beat(document: EpisodeDocument, beat_id: str):
    try:
        return next(beat for beat in document.beat_board.beats if beat.id == beat_id)
    except StopIteration as exc:
        raise AssistanceError(f"Unknown beat: {beat_id}") from exc


def _assert_beat_replaceable(document: EpisodeDocument, beat_id: str) -> None:
    beat = _beat(document, beat_id)
    if beat.locked:
        raise LockedContentError(f"unlock beat {beat_id!r} before requesting or applying a rewrite")
    if any(element.locked for element in beat.script):
        raise LockedContentError(
            f"beat {beat_id!r} contains locked script elements and cannot be replaced"
        )


def _beat_request(
    document: EpisodeDocument,
    beat_id: str,
    instruction: str,
) -> BeatSuggestionRequest:
    beat = _beat(document, beat_id)
    return BeatSuggestionRequest(
        context=_episode_context(document),
        beat=BeatContext(
            beat_id=beat.id,
            title=beat.title,
            purpose=beat.purpose,
            leading_speaker=beat.leading_speaker,
            must_land=beat.must_land,
            temperature=beat.temperature.value if beat.temperature else "",
            target_seconds=beat.target_seconds,
            target_words=beat.target_words,
            artifact_or_visual=beat.artifact_or_visual,
            current_script=render_script_text(beat.script),
        ),
        instruction=instruction.strip(),
    )


def _new_suggestion(
    *,
    kind: SuggestionKind,
    provider: ModelProvider,
    options: list[SuggestionOption],
    target_beat_id: str | None = None,
    instruction: str = "",
    now: datetime | None = None,
) -> MachineSuggestion:
    return MachineSuggestion(
        id=f"suggestion-{uuid4().hex}",
        kind=kind,
        provider=provider.provider_name,
        model=provider.model_name,
        created_at=now or datetime.now(timezone.utc),
        target_beat_id=target_beat_id,
        instruction=instruction.strip(),
        options=options,
    )


def generate_hinge_suggestion(
    document: EpisodeDocument,
    provider: ModelProvider,
    *,
    instruction: str = "",
    now: datetime | None = None,
) -> MachineSuggestion:
    output = provider.suggest_hinges(
        HingeSuggestionRequest(context=_episode_context(document), instruction=instruction.strip())
    )
    suggestion = _new_suggestion(
        kind=SuggestionKind.HINGE_CANDIDATES,
        provider=provider,
        instruction=instruction,
        now=now,
        options=[
            SuggestionOption(
                id=f"option-{index}",
                title=option.title,
                content=option.content,
                rationale=" -> ".join(option.causal_chain),
            )
            for index, option in enumerate(output.options, start=1)
        ],
    )
    document.suggestions.append(suggestion)
    return suggestion


def generate_beat_suggestion(
    document: EpisodeDocument,
    provider: ModelProvider,
    *,
    beat_id: str,
    instruction: str = "",
    revision: bool = False,
    now: datetime | None = None,
) -> MachineSuggestion:
    _assert_beat_replaceable(document, beat_id)
    request = _beat_request(document, beat_id, instruction)
    if revision and not request.beat.current_script.strip():
        raise AssistanceError("a beat revision requires an existing script")
    output = provider.revise_beat(request) if revision else provider.draft_beat(request)
    suggestion = _new_suggestion(
        kind=SuggestionKind.BEAT_REVISION if revision else SuggestionKind.BEAT_DRAFT,
        provider=provider,
        target_beat_id=beat_id,
        instruction=instruction,
        now=now,
        options=[
            SuggestionOption(
                id=f"option-{index}",
                title=option.title,
                content=option.script,
                rationale=option.rationale,
            )
            for index, option in enumerate(output.options, start=1)
        ],
    )
    document.suggestions.append(suggestion)
    return suggestion


def _suggestion(document: EpisodeDocument, suggestion_id: str) -> MachineSuggestion:
    try:
        return next(item for item in document.suggestions if item.id == suggestion_id)
    except StopIteration as exc:
        raise AssistanceError(f"Unknown suggestion: {suggestion_id}") from exc


def _option(suggestion: MachineSuggestion, option_id: str) -> SuggestionOption:
    try:
        return next(item for item in suggestion.options if item.id == option_id)
    except StopIteration as exc:
        raise AssistanceError(f"Unknown suggestion option: {option_id}") from exc


def _record_application(suggestion: MachineSuggestion, option_id: str) -> None:
    if option_id in suggestion.applied_option_ids:
        raise AssistanceError("that suggestion option has already been applied")
    suggestion.applied_option_ids.append(option_id)
    if len(suggestion.applied_option_ids) == len(suggestion.options):
        suggestion.status = SuggestionStatus.APPLIED
    else:
        suggestion.status = SuggestionStatus.PARTIALLY_APPLIED


def apply_hinge_option(
    document: EpisodeDocument,
    *,
    suggestion_id: str,
    option_id: str,
) -> HingeCandidate:
    suggestion = _suggestion(document, suggestion_id)
    if suggestion.kind != SuggestionKind.HINGE_CANDIDATES:
        raise AssistanceError("only hinge suggestions can be added as hinge candidates")
    if suggestion.status == SuggestionStatus.DISMISSED:
        raise AssistanceError("dismissed suggestions cannot be applied")
    option = _option(suggestion, option_id)
    used_ids = {candidate.id for candidate in document.inquiry.hinge_candidates}
    index = 1
    while f"machine-hinge-{index}" in used_ids:
        index += 1
    candidate = HingeCandidate(
        id=f"machine-hinge-{index}",
        content={
            "value": option.content,
            "provenance": Provenance.MACHINE_SUGGESTION,
            "approval": ApprovalStatus.SUGGESTED,
        },
    )
    _record_application(suggestion, option_id)
    document.inquiry.hinge_candidates.append(candidate)
    return candidate


def apply_beat_option(
    document: EpisodeDocument,
    *,
    suggestion_id: str,
    option_id: str,
) -> None:
    suggestion = _suggestion(document, suggestion_id)
    if suggestion.kind not in {SuggestionKind.BEAT_DRAFT, SuggestionKind.BEAT_REVISION}:
        raise AssistanceError("only beat suggestions can be applied to a beat")
    if suggestion.status != SuggestionStatus.PENDING:
        raise AssistanceError("a beat suggestion can be applied only once")
    if suggestion.target_beat_id is None:
        raise AssistanceError("beat suggestion has no target")
    _assert_beat_replaceable(document, suggestion.target_beat_id)
    option = _option(suggestion, option_id)
    parsed = parse_script_text(
        option.content,
        beat_id=suggestion.target_beat_id,
        provenance=Provenance.MACHINE_SUGGESTION,
        approval=ApprovalStatus.SUGGESTED,
    )
    suggestion.applied_option_ids.append(option_id)
    suggestion.status = SuggestionStatus.APPLIED
    _beat(document, suggestion.target_beat_id).script = parsed


def dismiss_suggestion(document: EpisodeDocument, *, suggestion_id: str) -> None:
    suggestion = _suggestion(document, suggestion_id)
    if suggestion.status == SuggestionStatus.APPLIED:
        raise AssistanceError("an applied suggestion cannot be dismissed")
    suggestion.status = SuggestionStatus.DISMISSED
