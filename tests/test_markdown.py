import pytest

from table_nine.storage.markdown import (
    MarkdownBodyOutOfSyncError,
    MarkdownDocumentError,
    deserialize_episode,
    serialize_episode,
)
from table_nine.storage.migrations import SchemaMigrationError


def test_schema_one_traffic_cone_fixture_migrates_and_round_trips(traffic_cone_path):
    text = traffic_cone_path.read_text(encoding="utf-8")
    document = deserialize_episode(text)

    assert document.episode.registry_number == "14222"
    assert document.table_nine_schema == 2
    assert len(document.inquiry.hinge_candidates) == 3
    assert document.inquiry.selected_hinge_id is None
    serialized = serialize_episode(document)
    assert serialized.startswith("---\ntable_nine_schema: 2\n")
    assert deserialize_episode(serialized) == document


def test_body_drift_is_not_silently_overwritten(traffic_cone_path):
    text = traffic_cone_path.read_text(encoding="utf-8")
    drifted = text.replace(
        "# Traffic Cone Uncle - Table Nine Dispatch",
        "# A manual body-only edit",
        1,
    )

    with pytest.raises(MarkdownBodyOutOfSyncError, match="refusing silent replacement"):
        deserialize_episode(drifted)


def test_future_schema_is_rejected(traffic_cone_path):
    text = traffic_cone_path.read_text(encoding="utf-8")
    future = text.replace("table_nine_schema: 1", "table_nine_schema: 99", 1)

    with pytest.raises(SchemaMigrationError, match="newer than supported"):
        deserialize_episode(future)


def test_missing_frontmatter_is_rejected():
    with pytest.raises(MarkdownDocumentError, match="must begin"):
        deserialize_episode("# Not a workbench document\n")
