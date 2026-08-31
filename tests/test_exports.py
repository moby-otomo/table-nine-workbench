from table_nine.services.exports import build_exports


def test_exports_are_deterministic_and_named_by_document_type(traffic_cone_document):
    source = "TAXO_No14222-TrafficConeUncle-DispatchWorkbench_UIS_v01.md"

    first = build_exports(traffic_cone_document, source)
    second = build_exports(traffic_cone_document, source)

    assert first == second
    assert first.dossier.filename.endswith("-DispatchDossier_UIS_v01.md")
    assert first.beat_board.filename.endswith("-BeatBoard_UIS_v01.md")
    assert first.performance_script.filename.endswith("-PerformanceScript_UIS_v01.md")
    assert first.archive_stub.filename.endswith("-ArchiveStub_UIS_v01.md")


def test_performance_export_keeps_silence_visible(traffic_cone_document):
    from table_nine.services.script_codec import parse_script_text

    beat = traffic_cone_document.beat_board.beats[0]
    beat.script = parse_script_text("[silence 2.5]", beat_id=beat.id)

    exports = build_exports(traffic_cone_document, "traffic-cone.md")

    assert "[silence 2.5]" in exports.performance_script.content
    assert "machine_suggestion" not in exports.performance_script.content

