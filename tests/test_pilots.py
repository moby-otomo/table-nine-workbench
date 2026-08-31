import pytest

from table_nine.services.pilots import create_new_pilot, pilot_filename
from table_nine.storage.repository import EpisodeConflictError, EpisodeRepository


def test_pilot_filename_keeps_unregistered_pilots_outside_taxonomy():
    assert (
        pilot_filename("waiting-room-uncle")
        == "PILOT-WaitingRoomUncle-DispatchWorkbench_UIS_v01.md"
    )
    assert (
        pilot_filename("waiting-room-uncle", "15432")
        == "TAXO_No15432-WaitingRoomUncle-DispatchWorkbench_UIS_v01.md"
    )


def test_create_new_pilot_writes_canonical_nine_beat_document(tmp_path):
    repository = EpisodeRepository(tmp_path)

    created = create_new_pilot(
        repository,
        episode_id="waiting-room-uncle",
        working_title="The Waiting Room Uncle",
        featured_uncle="Waiting Room Uncle",
    )

    assert created.document.document.revision == 1
    assert created.document.episode.registry_number is None
    assert len(created.document.beat_board.beats) == 9
    assert repository.load(created.filename) == created.document


def test_create_new_pilot_rejects_duplicate_episode_id(tmp_path):
    repository = EpisodeRepository(tmp_path)
    create_new_pilot(
        repository,
        episode_id="waiting-room-uncle",
        working_title="The Waiting Room Uncle",
        featured_uncle="Waiting Room Uncle",
    )

    with pytest.raises(EpisodeConflictError, match="episode ID already exists"):
        create_new_pilot(
            repository,
            episode_id="waiting-room-uncle",
            working_title="A Different Working Title",
            featured_uncle="Another Uncle",
            registry_number="15432",
        )


def test_create_new_pilot_rejects_duplicate_registry_number(tmp_path):
    repository = EpisodeRepository(tmp_path)
    create_new_pilot(
        repository,
        episode_id="waiting-room-uncle",
        working_title="The Waiting Room Uncle",
        featured_uncle="Waiting Room Uncle",
        registry_number="15432",
    )

    with pytest.raises(EpisodeConflictError, match="registry number already exists"):
        create_new_pilot(
            repository,
            episode_id="clipboard-uncle",
            working_title="The Clipboard Uncle",
            featured_uncle="Clipboard Uncle",
            registry_number="15432",
        )
