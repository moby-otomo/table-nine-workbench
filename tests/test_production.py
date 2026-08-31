import hashlib
import io
import zipfile

import pytest
import yaml

from table_nine.domain.models import ApprovalStatus, EpisodeStatus
from table_nine.services.audits import audit_document
from table_nine.services.production import (
    PackageKind,
    PackageNotReadyError,
    build_production_package,
    evaluate_production_readiness,
)
from table_nine.services.script_codec import parse_script_text


SOURCE = "TAXO_No14222-TrafficConeUncle-DispatchWorkbench_UIS_v01.md"


def _prepare_table_read_document(document):
    document.inquiry.selected_hinge_id = document.inquiry.hinge_candidates[0].id
    document.inquiry.provisional_finding.value = "Confidence can become temporary infrastructure."
    document.closure.station_assignment.value = "Traffic routing liaison."
    document.closure.permanent_archive_addition.value = "Authority may be inferred from format."

    for beat in document.beat_board.beats:
        dialogue = (
            "Have you observed anything lately?"
            if beat.id == "observations"
            else "Ready."
        )
        speech_seconds = len(dialogue.rstrip("?").split()) / 2
        silence_seconds = beat.target_seconds - speech_seconds
        beat.script = parse_script_text(
            f"UNCLE_ONE: {dialogue}\n[silence {silence_seconds:g}]",
            beat_id=beat.id,
        )
    return document


def test_development_package_is_deterministic_and_self_describing(traffic_cone_document):
    first = build_production_package(traffic_cone_document, SOURCE)
    second = build_production_package(traffic_cone_document, SOURCE)

    assert first.content == second.content
    assert first.filename.endswith("-DevelopmentPackage_UIS_v01.zip")

    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        names = archive.namelist()
        assert "MANIFEST.yml" in names
        assert "TableNine-EditorialAudit.md" in names
        assert any(name.endswith("-PerformanceScript_UIS_v01.md") for name in names)
        manifest = yaml.safe_load(archive.read("MANIFEST.yml"))
        assert manifest["package_kind"] == "development"
        assert manifest["source_revision"] == 1
        assert manifest["working_state"] == "saved"
        for file_entry in manifest["files"]:
            assert hashlib.sha256(archive.read(file_entry["path"])).hexdigest() == file_entry[
                "sha256"
            ]


def test_incomplete_pilot_cannot_build_gated_packages(traffic_cone_document):
    readiness = evaluate_production_readiness(
        traffic_cone_document,
        audit_document(traffic_cone_document),
    )

    assert readiness.table_read.ready is False
    assert readiness.release.ready is False
    with pytest.raises(PackageNotReadyError, match="table-read package"):
        build_production_package(
            traffic_cone_document,
            SOURCE,
            kind=PackageKind.TABLE_READ,
        )


def test_table_read_and_release_gates_preserve_human_approval(traffic_cone_document):
    document = _prepare_table_read_document(traffic_cone_document)
    table_readiness = evaluate_production_readiness(document, audit_document(document))

    assert table_readiness.table_read.ready is True
    assert table_readiness.release.ready is False
    dirty_readiness = evaluate_production_readiness(
        document,
        audit_document(document),
        has_unsaved_changes=True,
    )
    assert dirty_readiness.table_read.ready is False
    table_package = build_production_package(
        document,
        SOURCE,
        kind=PackageKind.TABLE_READ,
    )
    assert table_package.kind == PackageKind.TABLE_READ

    document.episode.status = EpisodeStatus.APPROVED
    document.selected_hinge().content.approval = ApprovalStatus.HUMAN_APPROVED
    document.inquiry.provisional_finding.approval = ApprovalStatus.HUMAN_APPROVED
    document.closure.station_assignment.approval = ApprovalStatus.HUMAN_APPROVED
    document.closure.permanent_archive_addition.approval = ApprovalStatus.HUMAN_APPROVED
    release_readiness = evaluate_production_readiness(document, audit_document(document))

    assert release_readiness.release.ready is True
    release_package = build_production_package(
        document,
        SOURCE,
        kind=PackageKind.RELEASE,
    )
    assert release_package.filename.endswith("-ReleasePackage_UIS_v01.zip")
