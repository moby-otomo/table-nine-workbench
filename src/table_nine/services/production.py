from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from table_nine.domain.models import EpisodeDocument, EpisodeStatus
from table_nine.services.audits import AuditReport, AuditSeverity, audit_document
from table_nine.services.exports import ExportFile, build_exports
from table_nine.services.pacing import PacingConfig


class PackageKind(str, Enum):
    DEVELOPMENT = "development"
    TABLE_READ = "table_read"
    RELEASE = "release"


@dataclass(frozen=True)
class GateCheck:
    code: str
    label: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ProductionGate:
    name: str
    checks: tuple[GateCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.passed for check in self.checks)


@dataclass(frozen=True)
class ProductionReadiness:
    table_read: ProductionGate
    release: ProductionGate


@dataclass(frozen=True)
class ProductionPackage:
    filename: str
    content: bytes
    kind: PackageKind


class PackageNotReadyError(ValueError):
    """Raised when a gated production package is requested prematurely."""


def evaluate_production_readiness(
    document: EpisodeDocument,
    report: AuditReport,
    *,
    has_unsaved_changes: bool = False,
) -> ProductionReadiness:
    scripted_count = sum(bool(beat.script) for beat in document.beat_board.beats)
    audit_errors = report.count(AuditSeverity.ERROR)
    selected_hinge = document.selected_hinge()
    table_checks = (
        GateCheck(
            code="table_read.working_state_saved",
            label="Working state is saved",
            passed=not has_unsaved_changes,
            detail="Unsaved changes" if has_unsaved_changes else "Saved",
        ),
        GateCheck(
            code="table_read.all_beats_scripted",
            label="All constitutional beats are scripted",
            passed=scripted_count == 9,
            detail=f"{scripted_count} / 9 scripted",
        ),
        GateCheck(
            code="table_read.hinge_selected",
            label="Intellectual hinge is selected",
            passed=selected_hinge is not None,
            detail=selected_hinge.id if selected_hinge else "No hinge selected",
        ),
        GateCheck(
            code="table_read.finding_present",
            label="Provisional finding is present",
            passed=bool(document.inquiry.provisional_finding.value.strip()),
            detail="Present" if document.inquiry.provisional_finding.value.strip() else "Empty",
        ),
        GateCheck(
            code="table_read.station_present",
            label="Station assignment is present",
            passed=bool(document.closure.station_assignment.value.strip()),
            detail="Present" if document.closure.station_assignment.value.strip() else "Empty",
        ),
        GateCheck(
            code="table_read.archive_present",
            label="Permanent archive addition is present",
            passed=bool(document.closure.permanent_archive_addition.value.strip()),
            detail=(
                "Present"
                if document.closure.permanent_archive_addition.value.strip()
                else "Empty"
            ),
        ),
        GateCheck(
            code="table_read.no_audit_errors",
            label="Editorial audit has no errors",
            passed=audit_errors == 0,
            detail=f"{audit_errors} error(s)",
        ),
    )
    table_read = ProductionGate(name="Table read", checks=table_checks)

    custody_issues = document.readiness_issues()
    release_checks = (
        GateCheck(
            code="release.table_read_ready",
            label="Table-read gate is clear",
            passed=table_read.ready,
            detail="Ready" if table_read.ready else "Blocked",
        ),
        GateCheck(
            code="release.status_approved",
            label="Episode status is approved",
            passed=document.episode.status == EpisodeStatus.APPROVED,
            detail=document.episode.status.value,
        ),
        GateCheck(
            code="release.human_custody_clear",
            label="Human-custody fields are approved",
            passed=not custody_issues,
            detail="Clear" if not custody_issues else f"{len(custody_issues)} issue(s)",
        ),
    )
    return ProductionReadiness(
        table_read=table_read,
        release=ProductionGate(name="Release", checks=release_checks),
    )


def export_audit_report(
    document: EpisodeDocument,
    report: AuditReport,
) -> str:
    lines = [
        "# Table Nine Editorial Audit",
        "",
        f"- Episode: {document.episode.working_title or document.episode.featured_uncle}",
        f"- Episode ID: `{document.episode.id}`",
        f"- Source revision: {document.document.revision}",
        f"- Errors: {report.count(AuditSeverity.ERROR)}",
        f"- Warnings: {report.count(AuditSeverity.WARNING)}",
        f"- Notes: {report.count(AuditSeverity.NOTE)}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("_No deterministic findings._")
    for finding in report.findings:
        location = finding.beat_id or "episode"
        lines.extend(
            [
                f"### {finding.severity.value.upper()}: {finding.title}",
                "",
                f"- Code: `{finding.code}`",
                f"- Category: `{finding.category.value}`",
                f"- Location: `{location}`",
                f"- Diagnostic: {finding.detail}",
            ]
        )
        if finding.evidence:
            lines.append(f"- Evidence: {finding.evidence}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _package_name(source_filename: str, kind: PackageKind) -> str:
    stem = Path(source_filename).stem
    label = {
        PackageKind.DEVELOPMENT: "DevelopmentPackage",
        PackageKind.TABLE_READ: "TableReadPackage",
        PackageKind.RELEASE: "ReleasePackage",
    }[kind]
    if "-DispatchWorkbench" in stem:
        stem = stem.replace("-DispatchWorkbench", f"-{label}", 1)
    else:
        stem = f"{stem}-{label}"
    return f"{stem}.zip"


def _manifest(
    document: EpisodeDocument,
    source_filename: str,
    kind: PackageKind,
    files: list[ExportFile],
    has_unsaved_changes: bool,
) -> str:
    payload = {
        "table_nine_package": 1,
        "package_kind": kind.value,
        "source_document": source_filename,
        "source_revision": document.document.revision,
        "working_state": "unsaved" if has_unsaved_changes else "saved",
        "episode_id": document.episode.id,
        "files": [
            {
                "path": item.filename,
                "sha256": hashlib.sha256(item.content.encode("utf-8")).hexdigest(),
            }
            for item in files
        ],
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def _deterministic_zip(files: list[ExportFile]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(files, key=lambda value: value.filename):
            info = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, item.content.encode("utf-8"))
    return buffer.getvalue()


def build_production_package(
    document: EpisodeDocument,
    source_filename: str,
    *,
    kind: PackageKind = PackageKind.DEVELOPMENT,
    pacing_config: PacingConfig | None = None,
    has_unsaved_changes: bool = False,
) -> ProductionPackage:
    report = audit_document(document, pacing_config)
    readiness = evaluate_production_readiness(
        document,
        report,
        has_unsaved_changes=has_unsaved_changes,
    )
    if kind == PackageKind.TABLE_READ and not readiness.table_read.ready:
        raise PackageNotReadyError("table-read package is blocked by the production gate")
    if kind == PackageKind.RELEASE and not readiness.release.ready:
        raise PackageNotReadyError("release package is blocked by the production gate")

    exports = build_exports(document, source_filename)
    files = [
        exports.dossier,
        exports.beat_board,
        exports.performance_script,
        exports.archive_stub,
        ExportFile(
            filename="TableNine-EditorialAudit.md",
            content=export_audit_report(document, report),
        ),
    ]
    files.append(
        ExportFile(
            filename="MANIFEST.yml",
            content=_manifest(
                document,
                source_filename,
                kind,
                files,
                has_unsaved_changes,
            ),
        )
    )
    return ProductionPackage(
        filename=_package_name(source_filename, kind),
        content=_deterministic_zip(files),
        kind=kind,
    )
