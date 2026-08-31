from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CORE_BEAT_IDS = (
    "cold-open",
    "compact-introductions",
    "observations",
    "file-arrival",
    "specimen-examination",
    "deeper-inquiry",
    "return-and-finding",
    "comparative-tolerability",
    "station-assignment",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EpisodeStatus(str, Enum):
    DEVELOPMENT = "development"
    INQUIRY = "inquiry"
    DRAFTING = "drafting"
    TABLE_READ = "table_read"
    APPROVED = "approved"
    ARCHIVED = "archived"


class BeatStatus(str, Enum):
    PLANNED = "planned"
    DRAFTING = "drafting"
    DRAFTED = "drafted"
    REVISED = "revised"
    APPROVED = "approved"


class Provenance(str, Enum):
    HUMAN_OBSERVATION = "human_observation"
    CANONICAL_ARCHIVE = "canonical_archive"
    MACHINE_SUGGESTION = "machine_suggestion"
    VERIFIED_REFERENCE = "verified_reference"
    PROVISIONAL_INVENTION = "provisional_invention"
    HUMAN_APPROVED = "human_approved"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    SUGGESTED = "suggested"
    HUMAN_APPROVED = "human_approved"
    REJECTED = "rejected"


class ContentDisposition(str, Enum):
    STRUCTURAL = "structural"
    CANONICAL = "canonical"
    PERFORMANCE_FLEXIBLE = "performance_flexible"
    OPTIONAL = "optional"
    SILENCE = "silence"


class ScriptElementKind(str, Enum):
    DIALOGUE = "dialogue"
    STAGE_DIRECTION = "stage_direction"
    PAUSE = "pause"
    VISUAL_HOLD = "visual_hold"
    TRANSITION = "transition"
    SILENCE = "silence"


class ConversationalTemperature(str, Enum):
    SOCIALLY_WARM = "socially_warm"
    CURIOUS = "curious"
    TAXONOMICALLY_DRY = "taxonomically_dry"
    MILDLY_DISPUTATIOUS = "mildly_disputatious"
    ABSTRACT = "abstract"
    QUIETLY_SINCERE = "quietly_sincere"
    PROCEDURAL = "procedural"
    COMIC_RELEASE = "comic_release"


class ComparatorStatus(str, Enum):
    PROVISIONAL_SIGHTING = "provisional_behavioural_sighting"
    UNVERIFIED_COMPARATOR = "unverified_comparator"
    TAXONOMIC_CANDIDATE = "taxonomic_candidate"
    INSUFFICIENTLY_DOCUMENTED = "insufficiently_documented_uncle"
    PENDING_RECURRENCE = "possible_uncle_pending_recurrence"


class SuggestionKind(str, Enum):
    HINGE_CANDIDATES = "hinge_candidates"
    BEAT_DRAFT = "beat_draft"
    BEAT_REVISION = "beat_revision"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    PARTIALLY_APPLIED = "partially_applied"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class EditorialField(StrictModel):
    value: str = ""
    provenance: Provenance = Provenance.PROVISIONAL_INVENTION
    approval: ApprovalStatus = ApprovalStatus.DRAFT
    locked: bool = False


class DocumentMetadata(StrictModel):
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("document timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def updated_not_before_created(self) -> DocumentMetadata:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        return self


class EpisodeDossier(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    working_title: str = ""
    featured_uncle: str = ""
    registry_number: str | None = Field(default=None, pattern=r"^1\d{4}$")
    observed_behavior: EditorialField = Field(default_factory=EditorialField)
    central_artifact: EditorialField = Field(default_factory=EditorialField)
    human_stakes: EditorialField = Field(default_factory=EditorialField)
    ai_era_problem: EditorialField = Field(default_factory=EditorialField)
    status: EpisodeStatus = EpisodeStatus.DEVELOPMENT


class CastMember(StrictModel):
    seat_id: Literal["uncle_one", "uncle_two", "archivist_robot"]
    display_name: str
    character_id: str | None = None
    registry_number: str | None = Field(default=None, pattern=r"^1\d{4}$")
    cognitive_function: str


class Cast(StrictModel):
    seated_uncle_1: CastMember
    seated_uncle_2: CastMember
    archivist_robot: CastMember

    @model_validator(mode="after")
    def seats_match_fields(self) -> Cast:
        expected = {
            "seated_uncle_1": "uncle_one",
            "seated_uncle_2": "uncle_two",
            "archivist_robot": "archivist_robot",
        }
        for field_name, seat_id in expected.items():
            if getattr(self, field_name).seat_id != seat_id:
                raise ValueError(f"{field_name} must use seat_id {seat_id!r}")
        return self


class CatchUp(StrictModel):
    observation_1: EditorialField = Field(default_factory=EditorialField)
    observation_2: EditorialField = Field(default_factory=EditorialField)
    bridge_observation: EditorialField = Field(default_factory=EditorialField)


class HingeCandidate(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    content: EditorialField


class Inquiry(StrictModel):
    opening_question: EditorialField = Field(default_factory=EditorialField)
    hinge_candidates: list[HingeCandidate] = Field(default_factory=list)
    selected_hinge_id: str | None = None
    case_evidence: list[EditorialField] = Field(default_factory=list)
    productive_detour: EditorialField = Field(default_factory=EditorialField)
    return_from_detour: EditorialField = Field(default_factory=EditorialField)
    provisional_finding: EditorialField = Field(default_factory=EditorialField)

    @model_validator(mode="after")
    def selected_hinge_exists(self) -> Inquiry:
        candidate_ids = [candidate.id for candidate in self.hinge_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("hinge candidate ids must be unique")
        if self.selected_hinge_id and self.selected_hinge_id not in candidate_ids:
            raise ValueError("selected_hinge_id must identify a hinge candidate")
        return self


class ComparatorUncle(StrictModel):
    name: str
    observation: str = ""
    status: ComparatorStatus = ComparatorStatus.UNVERIFIED_COMPARATOR


class Closure(StrictModel):
    comparator_uncles: list[ComparatorUncle] = Field(default_factory=list)
    station_assignment: EditorialField = Field(default_factory=EditorialField)
    final_button: EditorialField = Field(default_factory=EditorialField)
    permanent_archive_addition: EditorialField = Field(default_factory=EditorialField)


class ScriptElement(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    kind: ScriptElementKind
    speaker_id: str | None = None
    text: str = ""
    duration_seconds: float | None = Field(default=None, gt=0)
    disposition: ContentDisposition = ContentDisposition.STRUCTURAL
    provenance: Provenance = Provenance.PROVISIONAL_INVENTION
    approval: ApprovalStatus = ApprovalStatus.DRAFT
    locked: bool = False

    @model_validator(mode="after")
    def validate_kind_requirements(self) -> ScriptElement:
        if self.kind == ScriptElementKind.DIALOGUE:
            if not self.speaker_id or not self.text.strip():
                raise ValueError("dialogue requires speaker_id and text")
        elif self.speaker_id is not None:
            raise ValueError("only dialogue elements may specify speaker_id")

        if self.kind in {ScriptElementKind.STAGE_DIRECTION, ScriptElementKind.TRANSITION}:
            if not self.text.strip():
                raise ValueError(f"{self.kind.value} requires text")

        timed = {
            ScriptElementKind.PAUSE,
            ScriptElementKind.VISUAL_HOLD,
            ScriptElementKind.SILENCE,
        }
        if self.kind in timed and self.duration_seconds is None:
            raise ValueError(f"{self.kind.value} requires duration_seconds")
        if self.kind not in timed and self.duration_seconds is not None:
            raise ValueError(f"{self.kind.value} cannot specify duration_seconds")

        if self.kind == ScriptElementKind.SILENCE:
            if self.disposition != ContentDisposition.SILENCE:
                raise ValueError("silence elements must use the silence disposition")
        elif self.disposition == ContentDisposition.SILENCE:
            raise ValueError("only silence elements may use the silence disposition")
        return self


class Beat(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str
    purpose: str
    status: BeatStatus = BeatStatus.PLANNED
    locked: bool = False
    is_core: bool = True
    core_order: int | None = Field(default=None, ge=0, le=8)
    parent_beat_id: str | None = None
    leading_speaker: str = ""
    must_land: list[str] = Field(default_factory=list)
    target_seconds: int = Field(gt=0)
    target_words: int = Field(ge=0)
    temperature: ConversationalTemperature | None = None
    artifact_or_visual: str = ""
    callback_planted: str = ""
    callback_resolved: str = ""
    factual_claims: list[str] = Field(default_factory=list)
    handoff_line: str = ""
    script: list[ScriptElement] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_position(self) -> Beat:
        if self.is_core:
            if self.core_order is None or self.parent_beat_id is not None:
                raise ValueError("core beats require core_order and no parent_beat_id")
        elif self.core_order is not None or self.parent_beat_id is None:
            raise ValueError("optional sub-beats require parent_beat_id and no core_order")
        element_ids = [element.id for element in self.script]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("script element ids must be unique within a beat")
        return self


class BeatBoard(StrictModel):
    template_id: Literal["three-seat-inquiry-v1"] = "three-seat-inquiry-v1"
    beats: list[Beat]

    core_beat_ids: ClassVar[tuple[str, ...]] = CORE_BEAT_IDS

    @model_validator(mode="after")
    def preserve_constitution(self) -> BeatBoard:
        beat_ids = [beat.id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("beat ids must be unique")

        core_beats = [beat for beat in self.beats if beat.is_core]
        if tuple(beat.id for beat in core_beats) != self.core_beat_ids:
            raise ValueError("the nine constitutional beats must exist in order")
        if [beat.core_order for beat in core_beats] != list(range(9)):
            raise ValueError("constitutional core_order values must be 0 through 8")

        core_ids = set(self.core_beat_ids)
        for beat in self.beats:
            if not beat.is_core and beat.parent_beat_id not in core_ids:
                raise ValueError("optional sub-beats must belong to a constitutional beat")
        return self


class CharacterCard(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str
    registry_number: str | None = Field(default=None, pattern=r"^1\d{4}$")
    worldview: str = ""
    relationship_to_evidence: str = ""
    default_conversational_move: str = ""
    sentence_length: str = "short-medium"
    certainty_profile: str = ""
    characteristic_misunderstanding: str = ""
    association_style: str = ""
    emotional_blind_spot: str = ""
    unexpected_sensitivity: str = ""
    relationship_to_robot: str = ""
    humor_mechanism: str = ""
    forbidden_habits: list[str] = Field(default_factory=list)
    overused_phrases: list[str] = Field(default_factory=list)
    preferred_turn_word_range: tuple[int, int] = (8, 55)

    @field_validator("preferred_turn_word_range")
    @classmethod
    def validate_word_range(cls, value: tuple[int, int]) -> tuple[int, int]:
        lower, upper = value
        if lower < 0 or upper <= lower:
            raise ValueError("preferred turn word range must increase from a non-negative value")
        return value


class SuggestionOption(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str
    content: str
    rationale: str = ""


class MachineSuggestion(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    kind: SuggestionKind
    provider: str
    model: str
    created_at: datetime
    target_beat_id: str | None = None
    instruction: str = ""
    options: list[SuggestionOption] = Field(min_length=1)
    applied_option_ids: list[str] = Field(default_factory=list)
    status: SuggestionStatus = SuggestionStatus.PENDING

    @field_validator("created_at")
    @classmethod
    def require_created_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("suggestion timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_suggestion(self) -> MachineSuggestion:
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("suggestion option ids must be unique")
        if not set(self.applied_option_ids).issubset(option_ids):
            raise ValueError("applied option ids must identify suggestion options")

        is_beat_operation = self.kind in {
            SuggestionKind.BEAT_DRAFT,
            SuggestionKind.BEAT_REVISION,
        }
        if is_beat_operation and self.target_beat_id is None:
            raise ValueError("beat suggestions require target_beat_id")
        if not is_beat_operation and self.target_beat_id is not None:
            raise ValueError("hinge suggestions cannot target a beat")
        return self


class EpisodeDocument(StrictModel):
    table_nine_schema: Literal[2] = 2
    document: DocumentMetadata
    episode: EpisodeDossier
    cast: Cast
    catch_up: CatchUp = Field(default_factory=CatchUp)
    inquiry: Inquiry = Field(default_factory=Inquiry)
    closure: Closure = Field(default_factory=Closure)
    beat_board: BeatBoard
    suggestions: list[MachineSuggestion] = Field(default_factory=list)

    def selected_hinge(self) -> HingeCandidate | None:
        if self.inquiry.selected_hinge_id is None:
            return None
        return next(
            candidate
            for candidate in self.inquiry.hinge_candidates
            if candidate.id == self.inquiry.selected_hinge_id
        )

    def readiness_issues(self) -> list[str]:
        issues: list[str] = []
        selected_hinge = self.selected_hinge()
        if selected_hinge is None:
            issues.append("No intellectual hinge has been selected.")
        elif selected_hinge.content.approval != ApprovalStatus.HUMAN_APPROVED:
            issues.append("The selected intellectual hinge requires human approval.")

        required_fields = (
            ("provisional finding", self.inquiry.provisional_finding),
            ("station assignment", self.closure.station_assignment),
            ("permanent archive addition", self.closure.permanent_archive_addition),
        )
        for label, field in required_fields:
            if not field.value.strip():
                issues.append(f"The {label} is empty.")
            elif field.approval != ApprovalStatus.HUMAN_APPROVED:
                issues.append(f"The {label} requires human approval.")
        return issues
