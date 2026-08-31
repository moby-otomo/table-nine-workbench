from table_nine.domain.models import EpisodeStatus
from table_nine.services.audits import AuditSeverity, audit_document
from table_nine.services.script_codec import parse_script_text


def _codes(report):
    return [finding.code for finding in report.findings]


def test_development_fixture_reports_custody_and_script_coverage(traffic_cone_document):
    report = audit_document(traffic_cone_document)

    assert "custody.hinge_missing" in _codes(report)
    assert "structure.detour_incomplete" in _codes(report)
    assert "structure.comparator_count" in _codes(report)
    assert "evidence.case_evidence_missing" not in _codes(report)
    assert _codes(report).count("structure.beat_unscripted") == 9
    assert report.count(AuditSeverity.ERROR) == 0


def test_missing_case_evidence_is_visible(traffic_cone_document):
    traffic_cone_document.inquiry.case_evidence = []

    assert "evidence.case_evidence_missing" in _codes(
        audit_document(traffic_cone_document)
    )


def test_release_status_promotes_human_custody_failures_to_errors(traffic_cone_document):
    traffic_cone_document.episode.status = EpisodeStatus.APPROVED

    report = audit_document(traffic_cone_document)
    hinge_finding = next(
        finding for finding in report.findings if finding.code == "custody.hinge_missing"
    )

    assert hinge_finding.severity == AuditSeverity.ERROR
    assert report.count(AuditSeverity.ERROR) == 4


def test_voice_audit_detects_unknown_speaker_and_long_monologue(traffic_cone_document):
    beat = traffic_cone_document.beat_board.beats[5]
    long_turn = " ".join(["certain"] * 80)
    beat.script = parse_script_text(f"VISITOR: {long_turn}", beat_id=beat.id)

    report = audit_document(traffic_cone_document)
    beat_codes = [finding.code for finding in report.for_beat(beat.id)]

    assert "voice.unknown_speaker" in beat_codes
    assert "voice.long_turn" in beat_codes
    assert "voice.single_seat_monopoly" not in beat_codes


def test_performance_audit_preserves_timing_but_requires_spoken_argument(
    traffic_cone_document,
):
    beat = traffic_cone_document.beat_board.beats[3]
    beat.script = parse_script_text(
        "[hold on classification card 4]\n[silence 2]",
        beat_id=beat.id,
    )

    report = audit_document(traffic_cone_document)
    beat_codes = [finding.code for finding in report.for_beat(beat.id)]

    assert "performance.audio_argument_missing" in beat_codes
    assert "voice.unknown_speaker" not in beat_codes


def test_observation_ritual_is_checked_only_after_the_beat_is_scripted(
    traffic_cone_document,
):
    beat = traffic_cone_document.beat_board.beats[2]
    beat.script = parse_script_text("UNCLE_ONE: Anything new?", beat_id=beat.id)
    assert "structure.observation_ritual_missing" in _codes(
        audit_document(traffic_cone_document)
    )

    beat.script = parse_script_text(
        "UNCLE_ONE: Have you observed anything lately?",
        beat_id=beat.id,
    )
    assert "structure.observation_ritual_missing" not in _codes(
        audit_document(traffic_cone_document)
    )


def test_locked_unapproved_script_is_visible_to_custody_audit(traffic_cone_document):
    beat = traffic_cone_document.beat_board.beats[0]
    beat.script = parse_script_text("UNCLE_ONE: Keep this provisional.", beat_id=beat.id)
    beat.script[0].locked = True

    report = audit_document(traffic_cone_document)

    assert "custody.locked_unapproved_script" in [
        finding.code for finding in report.for_beat(beat.id)
    ]
