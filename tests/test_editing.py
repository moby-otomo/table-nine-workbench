import pytest

from table_nine.domain.models import ContentDisposition, ScriptElement, ScriptElementKind
from table_nine.services.editing import LockedContentError, assert_locked_content_preserved


def _beat(document, beat_id="specimen-examination"):
    return next(beat for beat in document.beat_board.beats if beat.id == beat_id)


def test_locked_beat_cannot_change(traffic_cone_document):
    original = traffic_cone_document.model_copy(deep=True)
    _beat(original).locked = True
    candidate = original.model_copy(deep=True)
    _beat(candidate).purpose = "Changed while locked"

    with pytest.raises(LockedContentError, match="content-neutral save"):
        assert_locked_content_preserved(original, candidate)


def test_locked_beat_can_be_unlocked_without_content_change(traffic_cone_document):
    original = traffic_cone_document.model_copy(deep=True)
    _beat(original).locked = True
    candidate = original.model_copy(deep=True)
    _beat(candidate).locked = False

    assert_locked_content_preserved(original, candidate)


def test_unlock_and_edit_must_be_separate_saves(traffic_cone_document):
    original = traffic_cone_document.model_copy(deep=True)
    _beat(original).locked = True
    candidate = original.model_copy(deep=True)
    _beat(candidate).locked = False
    _beat(candidate).purpose = "Changed during unlock"

    with pytest.raises(LockedContentError, match="content-neutral save"):
        assert_locked_content_preserved(original, candidate)


def test_locked_selected_hinge_cannot_be_replaced(traffic_cone_document):
    original = traffic_cone_document.model_copy(deep=True)
    selected = original.inquiry.hinge_candidates[0]
    selected.content.locked = True
    original.inquiry.selected_hinge_id = selected.id
    candidate = original.model_copy(deep=True)
    candidate.inquiry.selected_hinge_id = candidate.inquiry.hinge_candidates[1].id

    with pytest.raises(LockedContentError, match="selected intellectual hinge"):
        assert_locked_content_preserved(original, candidate)


def test_locked_script_element_cannot_be_removed(traffic_cone_document):
    original = traffic_cone_document.model_copy(deep=True)
    beat = _beat(original)
    beat.script = [
        ScriptElement(
            id="specimen-line-001",
            kind=ScriptElementKind.SILENCE,
            duration_seconds=2.0,
            disposition=ContentDisposition.SILENCE,
            locked=True,
        )
    ]
    candidate = original.model_copy(deep=True)
    _beat(candidate).script = []

    with pytest.raises(LockedContentError, match="locked content removed"):
        assert_locked_content_preserved(original, candidate)

