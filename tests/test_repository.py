from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from table_nine.storage.markdown import serialize_episode
from table_nine.storage.repository import (
    ConcurrentModificationError,
    EpisodeRepository,
    RevisionRequiredError,
    UnsafePathError,
)


def test_repository_creates_and_revises_with_history(tmp_path, traffic_cone_document):
    times = iter(
        [
            datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
        ]
    )
    repository = EpisodeRepository(tmp_path, clock=lambda: next(times))

    saved_v1 = repository.save("traffic-cone.md", traffic_cone_document)
    assert saved_v1.document.revision == 1

    original_v1 = saved_v1.model_copy(deep=True)
    saved_v1.episode.working_title = "Traffic Cone Uncle - Revised Working Title"
    saved_v2 = repository.save("traffic-cone.md", saved_v1, expected_revision=1)

    history_path = (
        tmp_path
        / ".table-nine-history"
        / "traffic-cone"
        / "revision-0001.md"
    )
    assert saved_v2.document.revision == 2
    assert history_path.read_text(encoding="utf-8") == serialize_episode(original_v1)
    assert repository.load("traffic-cone.md") == saved_v2


def test_existing_file_requires_expected_revision(tmp_path, traffic_cone_document):
    now = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
    repository = EpisodeRepository(tmp_path, clock=lambda: now)
    repository.save("traffic-cone.md", traffic_cone_document)

    with pytest.raises(RevisionRequiredError, match="expected_revision"):
        repository.save("traffic-cone.md", traffic_cone_document)


def test_stale_revision_is_rejected(tmp_path, traffic_cone_document):
    start = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
    repository = EpisodeRepository(tmp_path, clock=lambda: start)
    repository.save("traffic-cone.md", traffic_cone_document)

    with pytest.raises(ConcurrentModificationError, match="expected revision 9"):
        repository.save("traffic-cone.md", traffic_cone_document, expected_revision=9)


def test_repository_rejects_paths_outside_root(tmp_path, traffic_cone_document):
    repository = EpisodeRepository(tmp_path)

    with pytest.raises(UnsafePathError, match="inside the configured root"):
        repository.save("../outside.md", traffic_cone_document)


def test_document_timestamps_remain_ordered(tmp_path, traffic_cone_document):
    after_creation = traffic_cone_document.document.created_at + timedelta(hours=1)
    repository = EpisodeRepository(tmp_path, clock=lambda: after_creation)

    saved = repository.save("traffic-cone.md", traffic_cone_document)

    assert saved.document.updated_at >= saved.document.created_at


def test_invalid_replacement_has_no_history_side_effect(tmp_path, traffic_cone_document):
    valid_time = traffic_cone_document.document.created_at + timedelta(hours=1)
    repository = EpisodeRepository(tmp_path, clock=lambda: valid_time)
    repository.save("traffic-cone.md", traffic_cone_document)

    invalid_time = traffic_cone_document.document.created_at - timedelta(hours=1)
    invalid_repository = EpisodeRepository(tmp_path, clock=lambda: invalid_time)

    with pytest.raises(ValidationError, match="cannot precede"):
        invalid_repository.save(
            "traffic-cone.md",
            traffic_cone_document,
            expected_revision=1,
        )

    assert not (tmp_path / ".table-nine-history").exists()
