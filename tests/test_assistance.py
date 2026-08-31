from datetime import datetime, timezone

import pytest

from table_nine.domain.models import ApprovalStatus, Provenance, SuggestionStatus
from table_nine.providers.mock import DeterministicMockProvider
from table_nine.services.assistance import (
    AssistanceError,
    apply_beat_option,
    apply_hinge_option,
    generate_beat_suggestion,
    generate_hinge_suggestion,
)
from table_nine.services.editing import LockedContentError
from table_nine.services.script_codec import parse_script_text


NOW = datetime(2026, 8, 16, 10, 30, tzinfo=timezone.utc)


def test_hinge_suggestions_are_logged_and_never_selected(traffic_cone_document):
    document = traffic_cone_document
    original_closure = document.closure.model_copy(deep=True)
    provider = DeterministicMockProvider()

    suggestion = generate_hinge_suggestion(document, provider, now=NOW)

    assert suggestion.provider == "mock"
    assert len(suggestion.options) == 3
    assert document.inquiry.selected_hinge_id is None
    assert document.closure == original_closure

    candidate = apply_hinge_option(
        document,
        suggestion_id=suggestion.id,
        option_id="option-1",
    )
    assert candidate.content.provenance == Provenance.MACHINE_SUGGESTION
    assert candidate.content.approval == ApprovalStatus.SUGGESTED
    assert candidate.content.locked is False
    assert document.inquiry.selected_hinge_id is None
    assert suggestion.status == SuggestionStatus.PARTIALLY_APPLIED


def test_applying_beat_draft_changes_only_target_beat(traffic_cone_document):
    document = traffic_cone_document
    provider = DeterministicMockProvider()
    untouched = [beat.model_copy(deep=True) for beat in document.beat_board.beats[1:]]

    suggestion = generate_beat_suggestion(
        document,
        provider,
        beat_id="cold-open",
        instruction="Keep it compact.",
        now=NOW,
    )
    assert document.beat_board.beats[0].script == []

    apply_beat_option(
        document,
        suggestion_id=suggestion.id,
        option_id="option-1",
    )

    target = document.beat_board.beats[0]
    assert target.script
    assert all(item.provenance == Provenance.MACHINE_SUGGESTION for item in target.script)
    assert all(item.approval == ApprovalStatus.SUGGESTED for item in target.script)
    assert document.beat_board.beats[1:] == untouched
    assert suggestion.status == SuggestionStatus.APPLIED

    with pytest.raises(AssistanceError, match="only once"):
        apply_beat_option(
            document,
            suggestion_id=suggestion.id,
            option_id="option-2",
        )


def test_locked_beat_is_rejected_before_provider_call(traffic_cone_document):
    document = traffic_cone_document
    document.beat_board.beats[0].locked = True

    with pytest.raises(LockedContentError, match="unlock beat"):
        generate_beat_suggestion(
            document,
            DeterministicMockProvider(),
            beat_id="cold-open",
        )

    assert document.suggestions == []


def test_locked_script_element_prevents_replacement(traffic_cone_document):
    document = traffic_cone_document
    beat = document.beat_board.beats[0]
    beat.script = parse_script_text("UNCLE_ONE: Keep this.", beat_id=beat.id)
    beat.script[0].locked = True

    with pytest.raises(LockedContentError, match="locked script elements"):
        generate_beat_suggestion(
            document,
            DeterministicMockProvider(),
            beat_id=beat.id,
        )


def test_revision_requires_existing_script(traffic_cone_document):
    with pytest.raises(AssistanceError, match="requires an existing script"):
        generate_beat_suggestion(
            traffic_cone_document,
            DeterministicMockProvider(),
            beat_id="cold-open",
            revision=True,
        )
