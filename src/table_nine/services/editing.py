from __future__ import annotations

from typing import Any

from table_nine.domain.models import EpisodeDocument
from table_nine.storage.repository import EpisodeRepository


class LockedContentError(ValueError):
    """Raised when a candidate revision changes content that was locked on disk."""


def _contains_locked_node(value: Any) -> bool:
    if isinstance(value, dict):
        return value.get("locked") is True or any(
            _contains_locked_node(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_locked_node(item) for item in value)
    return False


def _assert_locked_nodes_preserved(
    original: Any,
    candidate: Any,
    *,
    path: str = "document",
) -> None:
    if isinstance(original, dict):
        if not isinstance(candidate, dict):
            raise LockedContentError(f"locked content changed at {path}")

        if original.get("locked") is True:
            if candidate == original:
                return
            if candidate.get("locked") is False:
                relocked = {**candidate, "locked": True}
                if relocked == original:
                    return
            raise LockedContentError(
                f"unlock {path} in a content-neutral save before editing it"
            )

        for key, original_value in original.items():
            if key in candidate:
                _assert_locked_nodes_preserved(
                    original_value,
                    candidate[key],
                    path=f"{path}.{key}",
                )
        return

    if isinstance(original, list):
        if not isinstance(candidate, list):
            raise LockedContentError(f"locked content changed at {path}")

        original_has_ids = all(
            isinstance(item, dict) and isinstance(item.get("id"), str) for item in original
        )
        candidate_has_ids = all(
            isinstance(item, dict) and isinstance(item.get("id"), str) for item in candidate
        )
        if original_has_ids and candidate_has_ids:
            candidate_by_id = {item["id"]: item for item in candidate}
            for original_value in original:
                item_id = original_value["id"]
                if item_id not in candidate_by_id:
                    if _contains_locked_node(original_value):
                        raise LockedContentError(f"locked content removed at {path}.{item_id}")
                    continue
                _assert_locked_nodes_preserved(
                    original_value,
                    candidate_by_id[item_id],
                    path=f"{path}.{item_id}",
                )
            return

        for index, original_value in enumerate(original):
            if index >= len(candidate):
                if _contains_locked_node(original_value):
                    raise LockedContentError(f"locked content removed at {path}[{index}]")
                continue
            _assert_locked_nodes_preserved(
                original_value,
                candidate[index],
                path=f"{path}[{index}]",
            )


def assert_locked_content_preserved(
    original: EpisodeDocument,
    candidate: EpisodeDocument,
) -> None:
    original_data = original.model_dump(mode="json")
    candidate_data = candidate.model_dump(mode="json")
    _assert_locked_nodes_preserved(original_data, candidate_data)

    selected = original.selected_hinge()
    if (
        selected is not None
        and selected.content.locked
        and candidate.inquiry.selected_hinge_id != original.inquiry.selected_hinge_id
    ):
        raise LockedContentError(
            "unlock the selected intellectual hinge before selecting a different one"
        )


def save_episode(
    repository: EpisodeRepository,
    relative_path: str,
    original: EpisodeDocument,
    candidate: EpisodeDocument,
) -> EpisodeDocument:
    assert_locked_content_preserved(original, candidate)
    return repository.save(
        relative_path,
        candidate,
        expected_revision=original.document.revision,
    )
