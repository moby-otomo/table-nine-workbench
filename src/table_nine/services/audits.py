from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from table_nine.domain.models import (
    ApprovalStatus,
    EditorialField,
    EpisodeDocument,
    EpisodeStatus,
    Provenance,
    ScriptElementKind,
)
from table_nine.services.pacing import PacingConfig, calculate_episode_pacing, count_words


class AuditSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class AuditCategory(str, Enum):
    CUSTODY = "custody"
    STRUCTURE = "structure"
    PACING = "pacing"
    PERFORMANCE = "performance"
    VOICE = "voice"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class AuditConfig:
    beat_tolerance_ratio: float = 0.25
    minimum_beat_tolerance_seconds: float = 8.0
    long_turn_words: int = 75
    conversation_check_words: int = 40
    standard_runtime_min_seconds: int = 16 * 60
    standard_runtime_max_seconds: int = 18 * 60
    supported_runtime_min_seconds: int = 12 * 60
    supported_runtime_max_seconds: int = 22 * 60


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: AuditSeverity
    category: AuditCategory
    title: str
    detail: str
    beat_id: str | None = None
    evidence: str = ""


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[AuditFinding, ...]

    def count(self, severity: AuditSeverity) -> int:
        return sum(finding.severity == severity for finding in self.findings)

    def for_beat(self, beat_id: str) -> tuple[AuditFinding, ...]:
        return tuple(finding for finding in self.findings if finding.beat_id == beat_id)


def _release_severity(document: EpisodeDocument) -> AuditSeverity:
    if document.episode.status in {EpisodeStatus.APPROVED, EpisodeStatus.ARCHIVED}:
        return AuditSeverity.ERROR
    return AuditSeverity.WARNING


def _custody_findings(document: EpisodeDocument) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    severity = _release_severity(document)
    selected_hinge = document.selected_hinge()
    if selected_hinge is None:
        findings.append(
            AuditFinding(
                code="custody.hinge_missing",
                severity=severity,
                category=AuditCategory.CUSTODY,
                title="No intellectual hinge selected",
                detail="The inquiry still needs a human-selected intellectual hinge.",
            )
        )
    elif selected_hinge.content.approval != ApprovalStatus.HUMAN_APPROVED:
        findings.append(
            AuditFinding(
                code="custody.hinge_unapproved",
                severity=severity,
                category=AuditCategory.CUSTODY,
                title="Selected hinge is not human-approved",
                detail="Selection does not confer approval; the hinge remains under human custody.",
                evidence=selected_hinge.id,
            )
        )

    required_fields = (
        ("finding", "provisional finding", document.inquiry.provisional_finding),
        ("station", "station assignment", document.closure.station_assignment),
        ("archive", "permanent archive addition", document.closure.permanent_archive_addition),
    )
    for code, label, field in required_fields:
        if not field.value.strip():
            findings.append(
                AuditFinding(
                    code=f"custody.{code}_missing",
                    severity=severity,
                    category=AuditCategory.CUSTODY,
                    title=f"{label.title()} is empty",
                    detail=f"The {label} must be supplied by a human before release.",
                )
            )
        elif field.approval != ApprovalStatus.HUMAN_APPROVED:
            findings.append(
                AuditFinding(
                    code=f"custody.{code}_unapproved",
                    severity=severity,
                    category=AuditCategory.CUSTODY,
                    title=f"{label.title()} is not human-approved",
                    detail=f"The {label} remains provisional until a human approves it.",
                )
            )
    return findings


def _editorial_fields(document: EpisodeDocument) -> Iterable[tuple[str, EditorialField]]:
    dossier_fields = (
        ("observed behaviour", document.episode.observed_behavior),
        ("central artifact", document.episode.central_artifact),
        ("human stakes", document.episode.human_stakes),
        ("AI-era problem", document.episode.ai_era_problem),
        ("catch-up observation one", document.catch_up.observation_1),
        ("catch-up observation two", document.catch_up.observation_2),
        ("catch-up bridge", document.catch_up.bridge_observation),
        ("opening question", document.inquiry.opening_question),
        ("productive detour", document.inquiry.productive_detour),
        ("return from detour", document.inquiry.return_from_detour),
        ("provisional finding", document.inquiry.provisional_finding),
        ("station assignment", document.closure.station_assignment),
        ("final button", document.closure.final_button),
        ("permanent archive addition", document.closure.permanent_archive_addition),
    )
    yield from dossier_fields
    for candidate in document.inquiry.hinge_candidates:
        yield f"hinge {candidate.id}", candidate.content
    for index, field in enumerate(document.inquiry.case_evidence, start=1):
        yield f"case evidence {index}", field


def _structure_findings(document: EpisodeDocument) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    value_fields = (
        ("featured Uncle", document.episode.featured_uncle),
        ("observed behaviour", document.episode.observed_behavior.value),
        ("central artifact", document.episode.central_artifact.value),
        ("human stakes", document.episode.human_stakes.value),
        ("AI-era problem", document.episode.ai_era_problem.value),
        ("opening question", document.inquiry.opening_question.value),
    )
    missing = [label for label, value in value_fields if not value.strip()]
    if missing:
        findings.append(
            AuditFinding(
                code="structure.value_contract_incomplete",
                severity=AuditSeverity.WARNING,
                category=AuditCategory.STRUCTURE,
                title="Episode value contract is incomplete",
                detail="Establish the case inputs before treating the inquiry as structurally ready.",
                evidence=", ".join(missing),
            )
        )

    detour = document.inquiry.productive_detour.value.strip()
    return_from_detour = document.inquiry.return_from_detour.value.strip()
    if not detour or not return_from_detour:
        missing_detour_parts = []
        if not detour:
            missing_detour_parts.append("productive detour")
        if not return_from_detour:
            missing_detour_parts.append("return from detour")
        findings.append(
            AuditFinding(
                code="structure.detour_incomplete",
                severity=AuditSeverity.NOTE,
                category=AuditCategory.STRUCTURE,
                title="Designed meandering is incomplete",
                detail="The inquiry needs both a productive detour and an explicit return.",
                evidence=", ".join(missing_detour_parts),
            )
        )

    comparator_count = len(document.closure.comparator_uncles)
    if comparator_count < 3 or comparator_count > 5:
        findings.append(
            AuditFinding(
                code="structure.comparator_count",
                severity=(
                    AuditSeverity.WARNING
                    if document.beat_board.beats[7].script
                    else AuditSeverity.NOTE
                ),
                category=AuditCategory.STRUCTURE,
                title="Comparator set is outside the three-to-five range",
                detail="The Comparative Tolerability Protocol uses three to five provisional sightings.",
                beat_id="comparative-tolerability",
                evidence=f"Current count: {comparator_count}",
            )
        )

    for beat in document.beat_board.beats:
        if not beat.script:
            findings.append(
                AuditFinding(
                    code="structure.beat_unscripted",
                    severity=AuditSeverity.NOTE,
                    category=AuditCategory.STRUCTURE,
                    title="Beat has no script elements",
                    detail="This beat is not yet represented in the performance script.",
                    beat_id=beat.id,
                    evidence=beat.title,
                )
            )
        elif not beat.must_land:
            findings.append(
                AuditFinding(
                    code="structure.must_land_empty",
                    severity=AuditSeverity.NOTE,
                    category=AuditCategory.STRUCTURE,
                    title="Beat has no must-land points",
                    detail="No explicit thought or evidence has been marked as essential for this beat.",
                    beat_id=beat.id,
                    evidence=beat.title,
                )
            )

    observations = next(
        beat for beat in document.beat_board.beats if beat.id == "observations"
    )
    if observations.script:
        spoken = " ".join(
            element.text
            for element in observations.script
            if element.kind == ScriptElementKind.DIALOGUE
        ).casefold()
        if "have you observed anything lately" not in spoken:
            findings.append(
                AuditFinding(
                    code="structure.observation_ritual_missing",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.STRUCTURE,
                    title="Observation ritual is missing",
                    detail='The recurring question "Have you observed anything lately?" is absent.',
                    beat_id=observations.id,
                )
            )
    return findings


def _pacing_findings(
    document: EpisodeDocument,
    pacing_config: PacingConfig,
    audit_config: AuditConfig,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    pacing = calculate_episode_pacing(document, pacing_config)
    pacing_by_beat = {item.beat_id: item for item in pacing.beats}
    for beat in document.beat_board.beats:
        if not beat.script:
            continue
        measured = pacing_by_beat[beat.id]
        tolerance = max(
            audit_config.minimum_beat_tolerance_seconds,
            beat.target_seconds * audit_config.beat_tolerance_ratio,
        )
        if measured.total_seconds < beat.target_seconds - tolerance:
            findings.append(
                AuditFinding(
                    code="pacing.beat_under_target",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.PACING,
                    title="Beat is materially under its timing target",
                    detail="The current spoken and intentional timed elements do not fill the beat target.",
                    beat_id=beat.id,
                    evidence=(
                        f"Estimate {measured.total_seconds:.0f}s; target {beat.target_seconds}s; "
                        f"tolerance {tolerance:.0f}s"
                    ),
                )
            )
        elif measured.total_seconds > beat.target_seconds + tolerance:
            findings.append(
                AuditFinding(
                    code="pacing.beat_over_target",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.PACING,
                    title="Beat is materially over its timing target",
                    detail="The current spoken and intentional timed elements exceed the beat target.",
                    beat_id=beat.id,
                    evidence=(
                        f"Estimate {measured.total_seconds:.0f}s; target {beat.target_seconds}s; "
                        f"tolerance {tolerance:.0f}s"
                    ),
                )
            )

    target_runtime = sum(beat.target_seconds for beat in document.beat_board.beats)
    if not (
        audit_config.supported_runtime_min_seconds
        <= target_runtime
        <= audit_config.supported_runtime_max_seconds
    ):
        findings.append(
            AuditFinding(
                code="pacing.target_outside_supported_range",
                severity=AuditSeverity.ERROR,
                category=AuditCategory.PACING,
                title="Configured target is outside the supported runtime range",
                detail="The proven format supports light, standard, and unusually fertile inquiries from 12 to 22 minutes.",
                evidence=f"Configured target: {target_runtime / 60:.1f} minutes",
            )
        )
    elif not (
        audit_config.standard_runtime_min_seconds
        <= target_runtime
        <= audit_config.standard_runtime_max_seconds
    ):
        findings.append(
            AuditFinding(
                code="pacing.target_outside_standard_range",
                severity=AuditSeverity.NOTE,
                category=AuditCategory.PACING,
                title="Configured target is outside the standard runtime range",
                detail="Confirm that this episode is intentionally light or unusually fertile.",
                evidence=f"Configured target: {target_runtime / 60:.1f} minutes",
            )
        )

    if all(beat.script for beat in document.beat_board.beats):
        if not (
            audit_config.supported_runtime_min_seconds
            <= pacing.total_seconds
            <= audit_config.supported_runtime_max_seconds
        ):
            findings.append(
                AuditFinding(
                    code="pacing.episode_outside_supported_range",
                    severity=AuditSeverity.ERROR,
                    category=AuditCategory.PACING,
                    title="Estimated episode runtime is outside the supported range",
                    detail="The complete script falls outside the proven 12-to-22-minute envelope.",
                    evidence=f"Estimated runtime: {pacing.total_seconds / 60:.1f} minutes",
                )
            )
        elif not (
            audit_config.standard_runtime_min_seconds
            <= pacing.total_seconds
            <= audit_config.standard_runtime_max_seconds
        ):
            findings.append(
                AuditFinding(
                    code="pacing.episode_outside_standard_range",
                    severity=AuditSeverity.NOTE,
                    category=AuditCategory.PACING,
                    title="Estimated episode runtime is outside the standard range",
                    detail="Confirm that the completed episode is intentionally light or unusually fertile.",
                    evidence=f"Estimated runtime: {pacing.total_seconds / 60:.1f} minutes",
                )
            )
    return findings


def _evidence_findings(document: EpisodeDocument) -> list[AuditFinding]:
    if not document.inquiry.case_evidence:
        return [
            AuditFinding(
                code="evidence.case_evidence_missing",
                severity=AuditSeverity.NOTE,
                category=AuditCategory.EVIDENCE,
                title="No case evidence has been recorded",
                detail="The inquiry needs case-specific evidence before its reasoning can be tested.",
            )
        ]

    findings: list[AuditFinding] = []
    for index, field in enumerate(document.inquiry.case_evidence, start=1):
        if not field.value.strip():
            findings.append(
                AuditFinding(
                    code="evidence.case_evidence_empty",
                    severity=AuditSeverity.NOTE,
                    category=AuditCategory.EVIDENCE,
                    title="Case evidence entry is empty",
                    detail="Remove the placeholder or record the actual observation.",
                    evidence=f"Entry {index}",
                )
            )
        elif field.provenance == Provenance.PROVISIONAL_INVENTION:
            findings.append(
                AuditFinding(
                    code="evidence.case_evidence_provisional",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.EVIDENCE,
                    title="Case evidence is marked as provisional invention",
                    detail="Confirm whether this is evidence, testimony, or an invented working premise.",
                    evidence=f"Entry {index}: {field.value}",
                )
            )
    return findings


def _performance_and_voice_findings(
    document: EpisodeDocument,
    audit_config: AuditConfig,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    allowed_speakers = {"uncle_one", "uncle_two", "archivist_robot"}
    episode_speakers: set[str] = set()
    for beat in document.beat_board.beats:
        dialogue = [
            element for element in beat.script if element.kind == ScriptElementKind.DIALOGUE
        ]
        if beat.script and not dialogue:
            findings.append(
                AuditFinding(
                    code="performance.audio_argument_missing",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.PERFORMANCE,
                    title="Scripted beat has no spoken argument",
                    detail="An audio-only listener would receive timing or visuals but no dialogue in this beat.",
                    beat_id=beat.id,
                )
            )

        beat_speakers = {element.speaker_id or "" for element in dialogue}
        episode_speakers.update(beat_speakers)
        unknown = sorted(beat_speakers - allowed_speakers)
        if unknown:
            findings.append(
                AuditFinding(
                    code="voice.unknown_speaker",
                    severity=AuditSeverity.ERROR,
                    category=AuditCategory.VOICE,
                    title="Dialogue uses an unknown seat identifier",
                    detail="Dialogue labels must resolve to one of the three cognitive seats.",
                    beat_id=beat.id,
                    evidence=", ".join(unknown),
                )
            )

        spoken_words = sum(count_words(element.text) for element in dialogue)
        known_beat_speakers = beat_speakers & allowed_speakers
        if (
            spoken_words >= audit_config.conversation_check_words
            and len(known_beat_speakers) == 1
        ):
            findings.append(
                AuditFinding(
                    code="voice.single_seat_monopoly",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.VOICE,
                    title="A substantial beat is carried by one seat",
                    detail="The current passage reads as a monologue rather than a Three-Seat exchange.",
                    beat_id=beat.id,
                    evidence=f"{spoken_words} words by {next(iter(known_beat_speakers))}",
                )
            )

        for element in dialogue:
            word_count = count_words(element.text)
            if word_count > audit_config.long_turn_words:
                findings.append(
                    AuditFinding(
                        code="voice.long_turn",
                        severity=AuditSeverity.WARNING,
                        category=AuditCategory.VOICE,
                        title="Dialogue turn exceeds the provisional performance limit",
                        detail="Inspect this turn for breath, interruption, or division across speakers.",
                        beat_id=beat.id,
                        evidence=f"{element.speaker_id}: {word_count} words",
                    )
                )

        for element in beat.script:
            if element.locked and element.approval != ApprovalStatus.HUMAN_APPROVED:
                findings.append(
                    AuditFinding(
                        code="custody.locked_unapproved_script",
                        severity=AuditSeverity.WARNING,
                        category=AuditCategory.CUSTODY,
                        title="Locked script element is not human-approved",
                        detail="Unlock it for further work or explicitly approve it before treating the lock as final.",
                        beat_id=beat.id,
                        evidence=element.id,
                    )
                )

        if beat.factual_claims:
            findings.append(
                AuditFinding(
                    code="evidence.claims_require_review",
                    severity=AuditSeverity.NOTE,
                    category=AuditCategory.EVIDENCE,
                    title="Beat contains factual claims for source review",
                    detail="The audit records the claims but does not verify them automatically.",
                    beat_id=beat.id,
                    evidence=f"{len(beat.factual_claims)} claim(s)",
                )
            )

    if all(beat.script for beat in document.beat_board.beats):
        missing_speakers = sorted(allowed_speakers - episode_speakers)
        if missing_speakers:
            findings.append(
                AuditFinding(
                    code="voice.seat_absent",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.VOICE,
                    title="A cognitive seat is absent from the complete script",
                    detail="The finished Three-Seat Inquiry should preserve all three cognitive functions.",
                    evidence=", ".join(missing_speakers),
                )
            )

    for label, field in _editorial_fields(document):
        if field.locked and field.approval != ApprovalStatus.HUMAN_APPROVED:
            findings.append(
                AuditFinding(
                    code="custody.locked_unapproved_field",
                    severity=AuditSeverity.WARNING,
                    category=AuditCategory.CUSTODY,
                    title="Locked editorial field is not human-approved",
                    detail="A lock preserves text; it does not convert provisional material into approval.",
                    evidence=label,
                )
            )
    return findings


def audit_document(
    document: EpisodeDocument,
    pacing_config: PacingConfig | None = None,
    audit_config: AuditConfig | None = None,
) -> AuditReport:
    pacing = pacing_config or PacingConfig()
    config = audit_config or AuditConfig()
    findings = [
        *_custody_findings(document),
        *_structure_findings(document),
        *_pacing_findings(document, pacing, config),
        *_evidence_findings(document),
        *_performance_and_voice_findings(document, config),
    ]
    severity_order = {
        AuditSeverity.ERROR: 0,
        AuditSeverity.WARNING: 1,
        AuditSeverity.NOTE: 2,
    }
    beat_order = {
        beat.id: index for index, beat in enumerate(document.beat_board.beats)
    }
    findings.sort(
        key=lambda finding: (
            severity_order[finding.severity],
            beat_order.get(finding.beat_id or "", -1),
            finding.code,
        )
    )
    return AuditReport(findings=tuple(findings))
