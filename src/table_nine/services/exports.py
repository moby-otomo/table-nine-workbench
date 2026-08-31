from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from table_nine.domain.models import EpisodeDocument
from table_nine.services.script_codec import render_script_text
from table_nine.storage.markdown import serialize_episode


@dataclass(frozen=True)
class ExportFile:
    filename: str
    content: str


@dataclass(frozen=True)
class ExportBundle:
    dossier: ExportFile
    beat_board: ExportFile
    performance_script: ExportFile
    archive_stub: ExportFile


def _field(value: str) -> str:
    return value.strip() or "Not established"


def _export_name(source_filename: str, document_type: str) -> str:
    stem = Path(source_filename).stem
    if "-DispatchWorkbench" in stem:
        stem = stem.replace("-DispatchWorkbench", f"-{document_type}", 1)
    else:
        stem = f"{stem}-{document_type}"
    return f"{stem}.md"


def export_dossier(document: EpisodeDocument) -> str:
    selected_hinge = document.selected_hinge()
    lines = [
        f"# {document.episode.working_title or document.episode.featured_uncle}",
        "",
        "## Episode Dossier",
        "",
        f"- Featured Uncle: {_field(document.episode.featured_uncle)}",
        f"- Registry number: {document.episode.registry_number or 'Not assigned'}",
        f"- Observed behaviour: {_field(document.episode.observed_behavior.value)}",
        f"- Central artifact: {_field(document.episode.central_artifact.value)}",
        f"- Human stakes: {_field(document.episode.human_stakes.value)}",
        f"- AI-era problem: {_field(document.episode.ai_era_problem.value)}",
        "",
        "## Inquiry Architecture",
        "",
        f"- Opening question: {_field(document.inquiry.opening_question.value)}",
        f"- Selected hinge: {_field(selected_hinge.content.value) if selected_hinge else 'Not selected'}",
        f"- Productive detour: {_field(document.inquiry.productive_detour.value)}",
        f"- Return from detour: {_field(document.inquiry.return_from_detour.value)}",
        f"- Provisional finding: {_field(document.inquiry.provisional_finding.value)}",
        "",
        "## Closure",
        "",
        f"- Station assignment: {_field(document.closure.station_assignment.value)}",
        f"- Final button: {_field(document.closure.final_button.value)}",
        f"- Permanent archive addition: {_field(document.closure.permanent_archive_addition.value)}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def export_performance_script(document: EpisodeDocument) -> str:
    lines = [
        f"# {document.episode.working_title or document.episode.featured_uncle}",
        "",
        "*Table Nine performance script*",
        "",
    ]
    for beat in document.beat_board.beats:
        lines.extend([f"## {beat.core_order}. {beat.title}", ""])
        script_text = render_script_text(beat.script)
        lines.append(script_text or "_To be drafted._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_archive_stub(document: EpisodeDocument) -> str:
    selected_hinge = document.selected_hinge()
    lines = [
        "# Archival Output Stub",
        "",
        f"- Featured Uncle: {_field(document.episode.featured_uncle)}",
        f"- Registry number: {document.episode.registry_number or 'Not assigned'}",
        f"- Selected hinge: {_field(selected_hinge.content.value) if selected_hinge else 'Not selected'}",
        f"- Provisional finding: {_field(document.inquiry.provisional_finding.value)}",
        f"- Station assignment: {_field(document.closure.station_assignment.value)}",
        f"- Permanent archive addition: {_field(document.closure.permanent_archive_addition.value)}",
        "",
        "## Comparator Sightings",
        "",
    ]
    if document.closure.comparator_uncles:
        lines.extend(
            f"- {comparator.name} (`{comparator.status.value}`): {_field(comparator.observation)}"
            for comparator in document.closure.comparator_uncles
        )
    else:
        lines.append("_No comparator sightings recorded._")
    return "\n".join(lines).rstrip() + "\n"


def build_exports(document: EpisodeDocument, source_filename: str) -> ExportBundle:
    return ExportBundle(
        dossier=ExportFile(
            _export_name(source_filename, "DispatchDossier"),
            export_dossier(document),
        ),
        beat_board=ExportFile(
            _export_name(source_filename, "BeatBoard"),
            serialize_episode(document),
        ),
        performance_script=ExportFile(
            _export_name(source_filename, "PerformanceScript"),
            export_performance_script(document),
        ),
        archive_stub=ExportFile(
            _export_name(source_filename, "ArchiveStub"),
            export_archive_stub(document),
        ),
    )

