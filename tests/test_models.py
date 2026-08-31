from copy import deepcopy

import pytest
from pydantic import ValidationError

from table_nine.domain.models import (
    CORE_BEAT_IDS,
    ApprovalStatus,
    BeatBoard,
    CharacterCard,
    ContentDisposition,
    Inquiry,
    ScriptElement,
    ScriptElementKind,
)


def test_default_board_preserves_nine_constitutional_beats(traffic_cone_document):
    board = traffic_cone_document.beat_board

    assert tuple(beat.id for beat in board.beats) == CORE_BEAT_IDS
    assert [beat.core_order for beat in board.beats] == list(range(9))
    assert sum(beat.target_words for beat in board.beats) == 1825


def test_board_rejects_missing_constitutional_beat(traffic_cone_document):
    beats = deepcopy(traffic_cone_document.beat_board.beats[:-1])

    with pytest.raises(ValidationError, match="nine constitutional beats"):
        BeatBoard(beats=beats)


def test_inquiry_rejects_unknown_selected_hinge(traffic_cone_document):
    with pytest.raises(ValidationError, match="must identify a hinge candidate"):
        Inquiry(
            hinge_candidates=traffic_cone_document.inquiry.hinge_candidates,
            selected_hinge_id="not-a-candidate",
        )


def test_silence_is_an_explicit_timed_element():
    silence = ScriptElement(
        id="held-silence",
        kind=ScriptElementKind.SILENCE,
        duration_seconds=2.5,
        disposition=ContentDisposition.SILENCE,
    )

    assert silence.duration_seconds == 2.5


def test_silence_cannot_be_treated_as_missing_dialogue():
    with pytest.raises(ValidationError, match="silence disposition"):
        ScriptElement(
            id="invalid-silence",
            kind=ScriptElementKind.SILENCE,
            duration_seconds=1.0,
        )


def test_stage_direction_requires_visible_content():
    with pytest.raises(ValidationError, match="stage_direction requires text"):
        ScriptElement(
            id="empty-direction",
            kind=ScriptElementKind.STAGE_DIRECTION,
        )


def test_character_card_validates_turn_range():
    with pytest.raises(ValidationError, match="must increase"):
        CharacterCard(
            id="test-uncle",
            display_name="Test Uncle",
            preferred_turn_word_range=(55, 8),
        )


def test_readiness_requires_human_custody_fields(traffic_cone_document):
    issues = traffic_cone_document.readiness_issues()

    assert "No intellectual hinge has been selected." in issues
    assert "The provisional finding is empty." in issues
    assert "The station assignment is empty." in issues
    assert "The permanent archive addition is empty." in issues

    first_hinge = traffic_cone_document.inquiry.hinge_candidates[0]
    traffic_cone_document.inquiry.selected_hinge_id = first_hinge.id
    first_hinge.content.approval = ApprovalStatus.HUMAN_APPROVED

    assert "No intellectual hinge has been selected." not in traffic_cone_document.readiness_issues()
