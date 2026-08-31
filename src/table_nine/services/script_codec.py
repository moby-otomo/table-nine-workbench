from __future__ import annotations

import re

from table_nine.domain.models import (
    ApprovalStatus,
    ContentDisposition,
    Provenance,
    ScriptElement,
    ScriptElementKind,
)


DISPOSITION_PREFIX = re.compile(
    r"^\[(structural|canonical|performance-flexible|optional)\]\s*(.*)$",
    re.IGNORECASE,
)
DIALOGUE = re.compile(r"^([A-Z][A-Z0-9_ -]*):\s*(.+)$")
SIMPLE_TIMING = re.compile(r"^\[(pause|beat|silence)\s+([0-9]+(?:\.[0-9]+)?)\]$", re.I)
ROBOT_PROCESSING = re.compile(r"^\[robot processing\s+([0-9]+(?:\.[0-9]+)?)\]$", re.I)
VISUAL_HOLD = re.compile(
    r"^\[hold on\s+(.+?)\s+([0-9]+(?:\.[0-9]+)?)\]$",
    re.I,
)
NO_SPEECH = re.compile(
    r"^\[(.+?)\s+(?:-|\u2014)\s+no speech for\s+([0-9]+(?:\.[0-9]+)?)\]$",
    re.I,
)
TRANSITION = re.compile(r"^\[transition:\s*(.+)\]$", re.I)
STAGE_DIRECTION = re.compile(r"^\[(.+)\]$")


class ScriptParseError(ValueError):
    def __init__(self, line_number: int, message: str) -> None:
        super().__init__(f"line {line_number}: {message}")
        self.line_number = line_number


def _disposition(value: str | None) -> ContentDisposition:
    if value is None:
        return ContentDisposition.STRUCTURAL
    return ContentDisposition(value.lower().replace("-", "_"))


def parse_script_text(
    text: str,
    *,
    beat_id: str,
    provenance: Provenance = Provenance.HUMAN_OBSERVATION,
    approval: ApprovalStatus = ApprovalStatus.DRAFT,
) -> list[ScriptElement]:
    elements: list[ScriptElement] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        disposition_name: str | None = None
        prefix_match = DISPOSITION_PREFIX.match(line)
        if prefix_match:
            disposition_name, line = prefix_match.groups()
            line = line.strip()
            if not line:
                raise ScriptParseError(line_number, "content marker has no script element")

        element_id = f"{beat_id}-line-{len(elements) + 1:03d}"
        common = {
            "id": element_id,
            "provenance": provenance,
            "approval": approval,
        }

        if match := DIALOGUE.match(line):
            speaker, dialogue = match.groups()
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.DIALOGUE,
                    speaker_id=speaker.lower().replace(" ", "_").replace("-", "_"),
                    text=dialogue,
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        if match := SIMPLE_TIMING.match(line):
            timing_kind, duration = match.groups()
            kind = (
                ScriptElementKind.SILENCE
                if timing_kind.lower() == "silence"
                else ScriptElementKind.PAUSE
            )
            disposition = (
                ContentDisposition.SILENCE
                if kind == ScriptElementKind.SILENCE
                else _disposition(disposition_name)
            )
            elements.append(
                ScriptElement(
                    **common,
                    kind=kind,
                    duration_seconds=float(duration),
                    disposition=disposition,
                )
            )
            continue

        if match := ROBOT_PROCESSING.match(line):
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.VISUAL_HOLD,
                    text="robot processing",
                    duration_seconds=float(match.group(1)),
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        if match := VISUAL_HOLD.match(line):
            detail, duration = match.groups()
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.VISUAL_HOLD,
                    text=detail,
                    duration_seconds=float(duration),
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        if match := NO_SPEECH.match(line):
            detail, duration = match.groups()
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.VISUAL_HOLD,
                    text=detail,
                    duration_seconds=float(duration),
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        if match := TRANSITION.match(line):
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.TRANSITION,
                    text=match.group(1),
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        if match := STAGE_DIRECTION.match(line):
            elements.append(
                ScriptElement(
                    **common,
                    kind=ScriptElementKind.STAGE_DIRECTION,
                    text=match.group(1),
                    disposition=_disposition(disposition_name),
                )
            )
            continue

        raise ScriptParseError(
            line_number,
            "use SPEAKER: dialogue or a bracketed performance direction",
        )
    return elements


def _duration(value: float | None) -> str:
    if value is None:
        raise ValueError("timed script element is missing its duration")
    return f"{value:g}"


def render_script_text(elements: list[ScriptElement]) -> str:
    lines: list[str] = []
    for element in elements:
        prefix = ""
        if element.disposition not in {ContentDisposition.STRUCTURAL, ContentDisposition.SILENCE}:
            prefix = f"[{element.disposition.value.replace('_', '-')}] "

        if element.kind == ScriptElementKind.DIALOGUE:
            line = f"{element.speaker_id.upper()}: {element.text}"
        elif element.kind == ScriptElementKind.PAUSE:
            line = f"[pause {_duration(element.duration_seconds)}]"
        elif element.kind == ScriptElementKind.SILENCE:
            line = f"[silence {_duration(element.duration_seconds)}]"
        elif element.kind == ScriptElementKind.VISUAL_HOLD:
            line = f"[hold on {element.text or 'visual'} {_duration(element.duration_seconds)}]"
        elif element.kind == ScriptElementKind.TRANSITION:
            line = f"[transition: {element.text}]"
        else:
            line = f"[{element.text}]"
        lines.append(prefix + line)
    return "\n".join(lines)
