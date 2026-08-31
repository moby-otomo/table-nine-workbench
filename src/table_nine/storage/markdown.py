from __future__ import annotations

from typing import Any

import yaml

from table_nine.domain.models import EpisodeDocument, ScriptElement, ScriptElementKind
from table_nine.storage.migrations import migrate_payload


GENERATED_BODY_NOTICE = (
    "<!-- Generated from YAML frontmatter by Table Nine Script Workbench. -->"
)


class MarkdownDocumentError(ValueError):
    """Raised when a Markdown workbench document is malformed."""


class MarkdownBodyOutOfSyncError(MarkdownDocumentError):
    """Raised when the readable body no longer reflects the frontmatter."""


def _split_frontmatter(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise MarkdownDocumentError("document must begin with YAML frontmatter")

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        raise MarkdownDocumentError("YAML frontmatter is missing its closing delimiter")

    yaml_text = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :]).lstrip("\n")
    return yaml_text, body


def _yaml_payload(document: EpisodeDocument) -> dict[str, Any]:
    raw = document.model_dump(mode="json", exclude_defaults=True, exclude_none=True)
    raw.pop("table_nine_schema", None)

    document_payload = raw.get("document", {})
    document_payload = {
        "revision": document.document.revision,
        **document_payload,
    }
    raw["document"] = document_payload
    return {"table_nine_schema": document.table_nine_schema, **raw}


def _field_value(value: str) -> str:
    return value.strip() or "Not established"


def _render_script_element(element: ScriptElement) -> str:
    if element.kind == ScriptElementKind.DIALOGUE:
        return f"**{element.speaker_id}:** {element.text.strip()}"
    if element.kind == ScriptElementKind.STAGE_DIRECTION:
        return f"[{element.text.strip()}]"
    if element.kind == ScriptElementKind.TRANSITION:
        return f"[transition: {element.text.strip()}]"

    duration = f"{element.duration_seconds:g}"
    label = element.kind.value.replace("_", " ")
    detail = f" - {element.text.strip()}" if element.text.strip() else ""
    return f"[{label} {duration}{detail}]"


def render_episode_body(document: EpisodeDocument) -> str:
    selected_hinge = document.selected_hinge()
    selected_hinge_text = selected_hinge.content.value if selected_hinge else "Not selected"
    title = document.episode.working_title.strip() or document.episode.featured_uncle.strip()
    title = title or "Untitled Table Nine Dispatch"

    lines = [
        GENERATED_BODY_NOTICE,
        "",
        f"# {title}",
        "",
        "## Episode Dossier",
        "",
        f"- Episode ID: `{document.episode.id}`",
        f"- Featured Uncle: {_field_value(document.episode.featured_uncle)}",
        f"- Registry number: {document.episode.registry_number or 'Not assigned'}",
        f"- Status: `{document.episode.status.value}`",
        f"- Observed behaviour: {_field_value(document.episode.observed_behavior.value)}",
        f"- Central artifact: {_field_value(document.episode.central_artifact.value)}",
        f"- Human stakes: {_field_value(document.episode.human_stakes.value)}",
        f"- AI-era problem: {_field_value(document.episode.ai_era_problem.value)}",
        "",
        "## Inquiry",
        "",
        f"- Opening question: {_field_value(document.inquiry.opening_question.value)}",
        f"- Selected hinge: {selected_hinge_text}",
        "",
        "### Hinge Candidates",
        "",
    ]

    if document.inquiry.hinge_candidates:
        lines.extend(
            f"{index}. {candidate.content.value}"
            for index, candidate in enumerate(document.inquiry.hinge_candidates, start=1)
        )
    else:
        lines.append("_No hinge candidates yet._")

    lines.extend(
        [
            "",
            "## Beat Board",
            "",
            "| # | Beat | Status | Locked | Target |",
            "|---:|---|---|:---:|---:|",
        ]
    )
    for beat in document.beat_board.beats:
        order = beat.core_order if beat.is_core else "-"
        locked = "yes" if beat.locked else "no"
        lines.append(
            f"| {order} | {beat.title} | {beat.status.value} | {locked} | "
            f"{beat.target_seconds}s / {beat.target_words} words |"
        )

    scripted_beats = [beat for beat in document.beat_board.beats if beat.script]
    lines.extend(["", "## Script", ""])
    if not scripted_beats:
        lines.append("_No scripted elements yet._")
    else:
        for beat in scripted_beats:
            lines.extend([f"### Beat {beat.core_order}: {beat.title}", ""])
            lines.extend(_render_script_element(element) for element in beat.script)
            lines.append("")
        if lines[-1] == "":
            lines.pop()

    lines.extend(
        [
            "",
            "## Closure",
            "",
            f"- Provisional finding: {_field_value(document.inquiry.provisional_finding.value)}",
            f"- Station assignment: {_field_value(document.closure.station_assignment.value)}",
            f"- Permanent archive addition: "
            f"{_field_value(document.closure.permanent_archive_addition.value)}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def serialize_episode(document: EpisodeDocument) -> str:
    payload = _yaml_payload(document)
    yaml_text = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )
    return f"---\n{yaml_text}---\n\n{render_episode_body(document)}"


def deserialize_episode(text: str) -> EpisodeDocument:
    yaml_text, body = _split_frontmatter(text)
    try:
        payload = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise MarkdownDocumentError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(payload, dict):
        raise MarkdownDocumentError("YAML frontmatter must contain a mapping")

    document = EpisodeDocument.model_validate(migrate_payload(payload))
    expected_body = render_episode_body(document)
    if body != expected_body:
        raise MarkdownBodyOutOfSyncError(
            "Markdown body does not match the structured frontmatter; refusing silent replacement"
        )
    return document

