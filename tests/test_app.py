from pathlib import Path
from shutil import copy2

from streamlit.testing.v1 import AppTest

from table_nine.storage.markdown import deserialize_episode


APP_PATH = Path(__file__).resolve().parents[1] / "src" / "table_nine" / "app.py"


def test_streamlit_workbench_loads_traffic_cone_fixture():
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()

    assert not app.exception
    assert app.title[0].value == "Table Nine Script Workbench"
    assert [tab.label for tab in app.tabs] == [
        "Dossier",
        "Inquiry",
        "Beats",
        "Audits",
        "Assist",
        "Handoff",
    ]
    assert any("Traffic Cone Uncle" in caption.value for caption in app.caption)
    assert any(metric.label == "Audit errors" for metric in app.metric)
    assert any(button.label == "Development package" for button in app.download_button)


def test_streamlit_manual_edit_and_save_round_trip(
    tmp_path,
    traffic_cone_path,
    monkeypatch,
):
    target = tmp_path / traffic_cone_path.name
    copy2(traffic_cone_path, target)
    monkeypatch.setenv("TABLE_NINE_SCRIPTS_ROOT", str(tmp_path))
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()

    working_title = next(item for item in app.text_input if item.label == "Working title")
    app = working_title.set_value("Traffic Cone Uncle - Manual Pilot").run()
    script = next(item for item in app.text_area if item.label == "Script elements")
    app = script.set_value("UNCLE_ONE: Is that cone authorized?\n[silence 1.5]").run()
    save = next(item for item in app.button if item.label == "Save episode")

    assert not save.disabled
    app = save.click().run()
    assert not app.exception

    saved = deserialize_episode(target.read_text(encoding="utf-8"))
    assert saved.document.revision == 2
    assert saved.episode.working_title == "Traffic Cone Uncle - Manual Pilot"
    assert len(saved.beat_board.beats[0].script) == 2
    assert (tmp_path / ".table-nine-history" / target.stem / "revision-0001.md").exists()


def test_streamlit_mock_assistance_requires_review_before_application():
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()

    generate = next(item for item in app.button if item.label == "Generate suggestions")
    app = generate.click().run()

    assert not app.exception
    assert len([item for item in app.button if item.label == "Add as candidate"]) == 3
    assert any(caption.value == "Unsaved changes" for caption in app.caption)


def test_streamlit_new_pilot_workflow_starts_from_an_empty_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("TABLE_NINE_SCRIPTS_ROOT", str(tmp_path))
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()

    app = next(item for item in app.text_input if item.label == "Episode ID").set_value(
        "waiting-room-uncle"
    ).run()
    app = next(item for item in app.text_input if item.label == "Pilot title").set_value(
        "The Waiting Room Uncle"
    ).run()
    app = next(item for item in app.text_input if item.label == "Featured Uncle").set_value(
        "Waiting Room Uncle"
    ).run()
    create = next(item for item in app.button if item.label == "Create pilot")
    app = create.click().run()

    assert not app.exception
    target = tmp_path / "PILOT-WaitingRoomUncle-DispatchWorkbench_UIS_v01.md"
    created = deserialize_episode(target.read_text(encoding="utf-8"))
    assert created.document.revision == 1
    assert created.episode.id == "waiting-room-uncle"
    assert created.episode.registry_number is None
    assert len(created.beat_board.beats) == 9
    assert any("Waiting Room Uncle" in caption.value for caption in app.caption)
